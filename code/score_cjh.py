"""Score the harvested CJH Dublin Core records against the diasporic-memory
project signals (see memory/project_what_we_are_looking_for.md).

Reads data/cjh-oai/records/oai_dc/repo-*/resource-*.xml, applies a small
rubric, and writes data/cjh-oai/candidates.tsv ranked by score, plus a
breakdown of subscores per record so a human can spot-check.

Signals:
  - GENRE:    dc:type or description mentions memoir/correspondence/diary/oral history
  - GERMAN:   subjects, coverage, or description mention Germany / Austria / Central Europe
              (Jecke focus: pre-1939 German-speaking world)
  - EMIGRE:   subjects or description mention emigration/refugees/exile/Holocaust
  - RETURN:   description mentions return/visit/Heimat (rare but high-value)
  - PERSONAL: dc:type "Personal papers" / family collection / Nachlass
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

NS = {"dc": "http://purl.org/dc/elements/1.1/",
      "oai_dc": "http://www.openarchives.org/OAI/2.0/oai_dc/"}

# Patterns: keep them narrow; ranking already aggregates many cheap signals.
PAT_GENRE = re.compile(
    r"\b(memoir|memoirs|memoiren|erinnerung|autobiograph|"
    r"correspondenc|letters?|briefe?|diar(y|ies)|tagebuch|"
    r"oral histor|interview|reminiscenc)\b", re.I)

PAT_GERMAN_PLACE = re.compile(
    r"\b(german(y|s)?|deutschland|austria|österreich|"
    r"berlin|frankfurt|hamburg|munich|münchen|wien|vienna|"
    r"breslau|wrocław|leipzig|dresden|cologne|köln|stuttgart|"
    r"prague|prag|praha|bohemia|moravia|silesia|sudeten|"
    r"bavaria|bayern|saxony|sachsen|hesse|hessen|württemberg|"
    r"alsace|elsass|baden|swabia|schwaben|"
    r"galicia|bukovina|"  # adjacent German-speaking-Jewish geographies
    r"baltic states|riga|königsberg|danzig|gdańsk|memel|kaunas|kovno)\b", re.I)

PAT_GERMAN_LANG = re.compile(r"\b(german|deutsch|yiddish|jiddisch)\b", re.I)

PAT_EMIGRE = re.compile(
    r"\b(emigrat|émigré|emigré|exile|exiled|refugee|displaced|"
    r"holocaust|shoah|nazi|nazis|kristallnacht|"
    r"flight from|fled|escaped from|deport)\b", re.I)

PAT_RETURN = re.compile(
    r"\b(return(ed)? to|revisit|visit(ed)? (to|her|his|their) (home|former)|"
    r"trip to (germany|austria|berlin|vienna|hamburg|frankfurt|breslau)|"
    r"reunion|reunited|heimat|hometown|home town|former home|"
    r"pilgrimage|search for roots|trace.*roots)\b", re.I)

# Tight: a return/visit verb appearing within ~120 chars of a German place name.
# This is the project's defining signal — émigré reunion with hometown.
PAT_RETURN_VERB = re.compile(
    r"\b(return(ed|ing)?|revisit(ed|ing)?|visit(ed|ing)?|trip|journey|"
    r"travelled|traveled|went back|pilgrimage)\b", re.I)


def return_to_german_place_hits(text: str) -> int:
    """Count co-occurrences of a return/visit verb and a German place
    within a 120-character window."""
    hits = 0
    for m in PAT_RETURN_VERB.finditer(text):
        window = text[max(0, m.start() - 40): m.end() + 120]
        if PAT_GERMAN_PLACE.search(window):
            hits += 1
    return hits


# Born-in-German-place: the strongest "Jecke" biographical anchor.
PAT_BORN_GERMAN = re.compile(
    r"\bborn (in|on \d+\s+\w+\s+\d{4} in)?\s*[^.]{0,40}?\b("
    r"german(y|s)?|austria|berlin|frankfurt|hamburg|munich|münchen|"
    r"wien|vienna|breslau|leipzig|dresden|köln|cologne|prag|prague|"
    r"bohemia|moravia|silesia|sudeten|königsberg|danzig|"
    r"baden|bayern|bavaria|hesse|hessen|alsace|elsass)\b", re.I)


# Personal-papers heuristic: title ends with "Papers" / "Collection" AND
# creator has a "Lastname, Firstname, YYYY-YYYY" pattern (= a person, not org).
PAT_PERSONAL_TITLE = re.compile(
    r"\b(papers|collection|family papers|family collection|nachlass|"
    r"memoirs?|autobiograph|diaries|correspondence|letters)\b", re.I)
PAT_PERSON_CREATOR = re.compile(r"^[^,]+, [^,]+, \d{4}", re.M)

PAT_PERSONAL = re.compile(
    r"\b(personal papers|family papers|family collection|familiensammlung|"
    r"nachlass|nachlaß|private collection|papers, [12]\d{3})\b", re.I)

# Bonus: explicit hometown-tied geography phrasing
PAT_HOMETOWN_TIE = re.compile(
    r"\b(born in (germany|austria|berlin|vienna|wien|frankfurt|hamburg|"
    r"munich|münchen|breslau|prague|prag)|"
    r"native of|grew up in|childhood in)\b", re.I)


def gather_text(root) -> dict:
    """Pull out the Dublin Core fields we care about."""
    def all_text(tag):
        return [e.text or "" for e in root.findall(f".//dc:{tag}", NS)]
    return {
        "title":       " | ".join(all_text("title")),
        "creator":     " | ".join(all_text("creator")),
        "description": "\n".join(all_text("description")),
        "subject":     " | ".join(all_text("subject")),
        "coverage":    " | ".join(all_text("coverage")),
        "type":        " | ".join(all_text("type")),
        "language":    " | ".join(all_text("language")),
        "date":        " | ".join(all_text("date")),
        "identifier":  " | ".join(all_text("identifier")),
        "publisher":   " | ".join(all_text("publisher")),
    }


def count_hits(pattern, text):
    return len(pattern.findall(text)) if text else 0


def score_record(fields):
    blob = "\n".join(fields[k] for k in
                     ("title", "subject", "coverage", "type", "description"))

    # Curator-assigned genre type (Correspondence, Diaries, Memoirs etc).
    type_genre = bool(PAT_GENRE.search(fields["type"]))

    # Is it a personal-papers collection (vs. organizational records)?
    is_personal = bool(PAT_PERSONAL_TITLE.search(fields["title"])) and \
                  bool(PAT_PERSON_CREATOR.search(fields["creator"]))

    german_places = len(set(m.group(0).lower()
                            for m in PAT_GERMAN_PLACE.finditer(blob)))
    glang   = count_hits(PAT_GERMAN_LANG,
                         fields["language"] + " " + fields["subject"])
    emigre  = count_hits(PAT_EMIGRE, blob)
    return_to_german = return_to_german_place_hits(blob)
    born_german = count_hits(PAT_BORN_GERMAN, blob)
    home    = count_hits(PAT_HOMETOWN_TIE, blob)

    def sat(n, cap=3):
        return min(n, cap)

    # Hard preconditions for the project's focus:
    # - must touch the German-speaking world somehow
    # - must be a personal/memoir/correspondence-genre record (or personal-papers)
    if german_places == 0:
        return 0, {}
    if not (type_genre or is_personal):
        return 0, {}

    score = (
        15 * sat(return_to_german) +   # the project-defining signal
        10 * sat(born_german) +        # strong Jecke biographical anchor
        6  * sat(home) +
        5  * (1 if type_genre else 0) +
        5  * (1 if is_personal else 0) +
        2  * sat(german_places, cap=5) +
        2  * sat(glang) +
        1  * sat(emigre, cap=2)
    )
    return score, {
        "type_genre": int(type_genre),
        "is_personal": int(is_personal),
        "german_places": german_places,
        "glang": glang,
        "emigre": emigre,
        "return_to_german": return_to_german,
        "born_german": born_german,
        "home": home,
    }


def main():
    root_dir = Path(__file__).parent.parent / "data" / "cjh-oai" / "records" / "oai_dc"
    if not root_dir.exists():
        print(f"no records at {root_dir}", file=sys.stderr); sys.exit(1)

    out_path = Path(__file__).parent.parent / "data" / "cjh-oai" / "candidates.tsv"
    rows = []
    for repo_dir in sorted(root_dir.glob("repo-*")):
        repo_id = repo_dir.name.split("-", 1)[1]
        for xml_path in sorted(repo_dir.glob("resource-*.xml")):
            try:
                root = ET.parse(xml_path).getroot()
            except ET.ParseError:
                continue
            fields = gather_text(root)
            score, sub = score_record(fields)
            if score == 0:
                continue
            rows.append({
                "score": score,
                "repo_id": repo_id,
                "repo": fields["publisher"],
                "resource_id": xml_path.stem.split("-", 1)[1],
                "title": fields["title"][:160],
                "creator": fields["creator"][:120],
                "date": fields["date"][:80],
                "is_personal": sub["is_personal"],
                "type_genre": sub["type_genre"],
                "return_to_german": sub["return_to_german"],
                "born_german": sub["born_german"],
                "home": sub["home"],
                "german_places": sub["german_places"],
                "glang": sub["glang"],
                "emigre": sub["emigre"],
                "type": fields["type"][:120],
                "language": fields["language"],
                "url": (f"https://archives.cjh.org/repositories/{repo_id}"
                        f"/resources/{xml_path.stem.split('-', 1)[1]}"),
            })

    rows.sort(key=lambda r: r["score"], reverse=True)
    cols = ["score", "repo_id", "repo", "resource_id", "title", "creator",
            "date", "is_personal", "type_genre", "return_to_german",
            "born_german", "home", "german_places", "glang", "emigre",
            "type", "language", "url"]
    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, delimiter="\t",
                            extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} candidates to {out_path}")

    # Project-defining slice: explicit return-to-Germany or born-in-Germany hits.
    hot_rows = [r for r in rows if r["return_to_german"] >= 1 or r["born_german"] >= 1]
    hot_path = out_path.with_name("return_or_born_german.tsv")
    with hot_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, delimiter="\t",
                            extrasaction="ignore")
        w.writeheader()
        w.writerows(hot_rows)
    print(f"wrote {len(hot_rows)} hot (return/born-in-German) candidates to {hot_path}")

    print("\nTop 25 by composite score:")
    for r in rows[:25]:
        print(f"  {r['score']:3} [{r['repo'][:5]}/{r['resource_id']:>5}] "
              f"P{r['is_personal']}T{r['type_genre']} "
              f"ret→DE:{r['return_to_german']} born→DE:{r['born_german']} "
              f"home:{r['home']} | {r['title'][:80]}")
    print("\nReturn-to-German or born-in-German (top 25):")
    for r in hot_rows[:25]:
        print(f"  {r['score']:3} ret:{r['return_to_german']} born:{r['born_german']}"
              f" home:{r['home']} | {r['title'][:90]}")


if __name__ == "__main__":
    main()
