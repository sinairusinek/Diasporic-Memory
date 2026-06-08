"""Score harvested EAD records against the diasporic-memory project rules.

Operates on data/cjh-oai/records/oai_ead/repo-*/resource-*.xml (per-record
EAD files written by harvest_cjh.py --prefix oai_ead). Falls back to the
on-demand cache at records/oai_ead_on_demand/ for records not yet covered
by the full harvest.

Rules (see memory/project_what_we_are_looking_for.md):
  1. Must mention German-speaking Central European geography.
  2. Must show personal-memory genre signal (memoir, correspondence, diary,
     oral history, or be a personal-papers structure).
  3. **Date filter**: max 4-digit year found in dates + prose must be >= 1933.
     Drop undated items (revisit case-by-case).
  4. **Palestine-vector exclusion**: if the only return/visit signal points
     to Palestine/Israel and there is no memoir/Heimat/correspondence cue,
     drop — the leaving-Europe vector is out of scope.
  5. Multilingual: search English, German, and Hebrew prose.

Output: data/cjh-oai/ead_candidates.tsv, ranked.
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

from lxml import etree as LET

EAD_NS = "urn:isbn:1-931666-22-9"


# --- vocabulary ---------------------------------------------------------------

# Central European geography (Jecke proper + adjacent German-speaking Jewish world)
PAT_GERMAN_PLACE = re.compile(
    r"\b(german(y|s)?|deutschland|austria|österreich|"
    r"berlin|frankfurt|hamburg|munich|münchen|wien|vienna|"
    r"breslau|wrocław|leipzig|dresden|cologne|köln|stuttgart|"
    r"prague|prag|praha|bohemia|moravia|silesia|sudeten|"
    r"bavaria|bayern|saxony|sachsen|hesse|hessen|württemberg|"
    r"alsace|elsass|baden|swabia|schwaben|"
    r"galicia|bukovina|"
    r"riga|königsberg|danzig|gdańsk|memel|kaunas|kovno|"
    # Hebrew / Yiddish renderings of common German-speaking-Jewish places
    r"גרמניה|ברלין|פרנקפורט|המבורג|מינכן|וינה|פראג|לייפציג|דרזדן|"
    r"קלן|שטוטגרט|ברסלאו|בוהמיה|מורביה)\b", re.I | re.UNICODE)

# Genre cues — memoirs, correspondence, diaries, oral history
PAT_GENRE = re.compile(
    r"\b(memoir|memoirs|memoiren|erinnerung(en)?|autobiograph|"
    r"correspondenc|letters?|briefe|brief|"
    r"diar(y|ies)|tagebuch|"
    r"oral histor|interview|reminiscenc|"
    # Hebrew
    r"זכרונות|זיכרונות|יומן|התכתבות|מכתב(ים)?|אוטוביוגרפיה|ראיון|ריאיון)\b",
    re.I | re.UNICODE)

# Curator-assigned EAD genreform values to recognize as personal-memory genres
PAT_GENREFORM_PERSONAL = re.compile(
    r"\b(memoir|diar|correspondenc|letters|autobiograph|oral histor|"
    r"reminiscenc|personal papers|family papers|journal)\b", re.I)

# Heimat / hometown / return-visit phrasing (rare, high-value)
PAT_RETURN_VERB = re.compile(
    r"\b(return(ed|ing)?|revisit(ed|ing)?|visit(ed|ing)?|trip|journey|"
    r"travelled|traveled|went back|"
    # German
    r"rückkehr|rückreise|zurück nach|wiedersehen|besuch(te|ten|en)?|"
    # Hebrew
    r"ביקור|נסיעה|חזרה|שיבה|חזר ל|ביקר ב)\b",
    re.I | re.UNICODE)

PAT_HEIMAT = re.compile(
    r"\b(heimat|heimatstadt|geburtsort|hometown|home town|former home|"
    r"מולדת|עיר הולדת|ארץ מולדת)\b", re.I | re.UNICODE)

PAT_BORN_GERMAN = re.compile(
    r"\bborn\b.{0,80}?\b("
    r"german(y|s)?|austria|berlin|frankfurt|hamburg|munich|münchen|"
    r"wien|vienna|breslau|leipzig|dresden|köln|cologne|prag|prague|"
    r"bohemia|moravia|silesia|sudeten|königsberg|danzig|"
    r"baden|bayern|bavaria|hesse|hessen|alsace|elsass|wertheim)\b",
    re.I | re.DOTALL)

# --- Birthplace gate ----------------------------------------------------------
# Goal: if bioghist states a birthplace, use it as a hard discriminator.
# - Core German-speaking birthplace → confirmed Jecke, big bonus.
# - Explicit non-German birthplace → reject (the German-place hits later in
#   the record are about professional subject matter, not biography).
# Tighter than PAT_GERMAN_PLACE: excludes Galicia / Bukovina (Yiddish-majority
# under Habsburg rule; not Jecke proper for birthplace purposes).

# 110 chars after "born" — that's the "born in X on Y date" phrase, before
# the bio drifts into education / later life mentions of other places.
# "St. Louis" with its abbreviation period still fits comfortably.
PAT_BIRTH_EXCERPT = re.compile(r"\bborn\b.{0,110}", re.I | re.UNICODE | re.DOTALL)

PAT_CORE_GERMAN_BIRTH = re.compile(
    r"\b(germany|deutschland|austria|österreich|"
    r"berlin|frankfurt|hamburg|munich|münchen|wien|vienna|"
    r"breslau|wrocław|leipzig|dresden|cologne|köln|stuttgart|nuremberg|nürnberg|"
    r"prague|prag|praha|bohemia|moravia|silesia|sudeten|"
    r"bavaria|bayern|saxony|sachsen|hesse|hessen|württemberg|"
    r"alsace|elsass|baden|swabia|schwaben|"
    r"königsberg|danzig|memel|"
    r"גרמניה|ברלין|פרנקפורט|המבורג|מינכן|וינה|פראג|לייפציג)\b",
    re.I | re.UNICODE)

PAT_NON_GERMAN_BIRTH = re.compile(
    r"(\b("
    r"russia|russian empire|soviet|ussr|ukraine|ukrainian|belarus|"
    r"poland|polish|lithuania|lithuanian|latvia|latvian|estonia|estonian|"
    r"romania|romanian|bessarabia|moldova|moldovan|galicia|galician|bukovina|"
    # Habsburg-era Galician phrasing — "Austria" appears but it's Galicia
    r"austria-hungary|austria/poland|austrian poland|austrian galicia|"
    r"austro-hungarian|"
    # Galician / Polish / Ukrainian towns commonly stated as birthplace
    r"krakow|kraków|cracow|"
    r"lwów|lvov|lviv|lemberg|"
    r"stanisławów|stanislawow|"
    r"tarnów|tarnow|tarnopol|"
    r"białystok|bialystok|łódź|lodz|warsaw|warszawa|"
    r"vilnius|wilno|vilna|"
    r"odessa|kyiv|kiev|minsk|"
    r"monasterzyska|przemyśl|przemysl|brody|kolomyia|kolomea|"
    r"ottoman|turkey|turkish|"
    r"hungary|hungarian|budapest|"
    r"new york|united states|u\.s\.a|usa|america|american|"
    r"chicago|boston|philadelphia|baltimore|cincinnati|"
    r"england|britain|british|london|france|french|paris|"
    r"netherlands|holland|dutch|amsterdam|"
    r"morocco|algeria|tunisia|egypt|"
    r"palestine|israel|jerusalem|tel aviv"
    r")\b|st\. louis|saint louis)",
    re.I | re.UNICODE)


def classify_birthplace(bioghist: str) -> str:
    """Return 'german' / 'non_german' / 'unknown' from the first 'born' phrase.
    When both a German and a non-German place appear in the window, the earlier
    one wins — that's the actual birthplace, the later one is subsequent bio
    (education, exile, immigration)."""
    m = PAT_BIRTH_EXCERPT.search(bioghist or "")
    if not m:
        return "unknown"
    excerpt = m.group(0)
    core_m = PAT_CORE_GERMAN_BIRTH.search(excerpt)
    non_m = PAT_NON_GERMAN_BIRTH.search(excerpt)
    if core_m and not non_m:
        return "german"
    if non_m and not core_m:
        return "non_german"
    if core_m and non_m:
        # Whichever comes first is the actual birthplace.
        return "german" if core_m.start() < non_m.start() else "non_german"
    return "unknown"

PAT_EMIGRE = re.compile(
    r"\b(emigrat|émigré|emigré|exile|exiled|refugee|displaced|"
    r"holocaust|shoah|nazi|nazis|kristallnacht|"
    r"flight from|fled|escaped from|deport|"
    r"auswander|flüchtling|emigrant|"
    r"שואה|פליט(ים|ה)?|מהגר|הגירה)\b", re.I | re.UNICODE)

# Palestine / Israel destination markers (the leaving vector — out of scope)
PAT_PALESTINE_VECTOR = re.compile(
    r"\b(nach palästina|to palestine|nach israel|to israel|"
    r"לפלשתינה|לארץ ישראל|לארץ-ישראל|"
    r"aliy(ah|a)|עליה|עלייה|"
    r"reisetagebuch nach palästina|journey to palestine)\b",
    re.I | re.UNICODE)

# But if any of these are present, the Palestine exclusion does NOT apply
# (a Heimat/return/correspondence signal beats a Palestine destination cue).
PAT_RETURN_TO_CENTRAL_EUROPE = re.compile(
    r"\b(return(ed)? to (germany|austria|berlin|vienna|wien|frankfurt|"
    r"hamburg|munich|münchen|breslau|prague|prag)|"
    r"rückkehr nach (deutschland|österreich|berlin|wien)|"
    r"zurück nach (deutschland|österreich)|"
    r"visited (her|his|their) (former|childhood|home)|"
    r"חזר(ה|ו)? ל(גרמניה|וינה|ברלין|פראג|פרנקפורט))\b",
    re.I | re.UNICODE)

YEAR_PAT = re.compile(r"\b(18\d{2}|19\d{2}|20\d{2})\b")


# --- extraction ---------------------------------------------------------------

def ead_text(path: Path) -> dict:
    """Extract the prose fields we need from one EAD record."""
    try:
        parser = LET.XMLParser(recover=True, huge_tree=True)
        tree = LET.parse(str(path), parser)
    except Exception:
        return {}
    root = tree.getroot()
    # Some files start at <ead>, others at <archdesc>; normalize.
    archdesc = root if root.tag.endswith("archdesc") else \
               root.find(".//{%s}archdesc" % EAD_NS)
    if archdesc is None:
        return {}

    def joined(xpath):
        els = archdesc.findall(xpath, namespaces={"ead": EAD_NS})
        out = []
        for e in els:
            txt = " ".join(t.strip() for t in e.itertext() if t.strip())
            if txt:
                out.append(txt)
        return "\n".join(out)

    def joined_attrs(xpath):
        els = archdesc.findall(xpath, namespaces={"ead": EAD_NS})
        return " | ".join(" ".join(t.strip() for t in e.itertext() if t.strip())
                          for e in els)

    # Only the COLLECTION-level did, not series-level dids further down.
    # Origination type — persname vs corpname — is THE discriminator between
    # personal papers and organizational records. Captured separately so the
    # scorer can hard-filter on it.
    orig_persnames = archdesc.findall("ead:did/ead:origination/ead:persname",
                                       namespaces={"ead": EAD_NS})
    orig_corpnames = archdesc.findall("ead:did/ead:origination/ead:corpname",
                                       namespaces={"ead": EAD_NS})
    orig_type = ("persname" if orig_persnames and not orig_corpnames else
                 "corpname" if orig_corpnames and not orig_persnames else
                 "both" if orig_persnames and orig_corpnames else "unknown")

    return {
        "title":        joined("ead:did/ead:unittitle"),
        "unitdate":     joined_attrs("ead:did/ead:unitdate"),
        "abstract":     joined("ead:did/ead:abstract"),
        "langmaterial": joined("ead:did/ead:langmaterial"),
        "origination":  joined_attrs("ead:did/ead:origination"),
        "orig_type":    orig_type,
        "bioghist":     joined(".//ead:bioghist"),
        "scopecontent": joined(".//ead:scopecontent"),
        "subjects":     joined_attrs(".//ead:controlaccess/ead:subject"),
        "geognames":    joined_attrs(".//ead:controlaccess/ead:geogname"),
        "persnames":    joined_attrs(".//ead:controlaccess/ead:persname"),
        "corpnames":    joined_attrs(".//ead:controlaccess/ead:corpname"),
        "genreform":    joined_attrs(".//ead:controlaccess/ead:genreform"),
    }


def extract_birth_death(origination: str):
    m = re.search(r"(\d{4})\s*[-–]\s*(\d{4})", origination)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"\bb\.?\s*(\d{4})", origination)
    if m:
        return int(m.group(1)), None
    return None, None


def max_year(*texts) -> int:
    years = []
    for t in texts:
        years.extend(int(y) for y in YEAR_PAT.findall(t or ""))
    return max(years) if years else 0


# --- scoring -----------------------------------------------------------------

def count_hits(pattern, text):
    return len(pattern.findall(text or "")) if text else 0


def return_in_german_proximity(text: str) -> int:
    hits = 0
    for m in PAT_RETURN_VERB.finditer(text):
        window = text[max(0, m.start() - 60): m.end() + 160]
        if PAT_GERMAN_PLACE.search(window):
            hits += 1
    return hits


def score(ead: dict, prose_blob: str, all_text: str) -> tuple[int, dict, str]:
    if not ead:
        return 0, {}, "no_ead"

    # Hard filter 1: must mention Central European geography somewhere.
    if not PAT_GERMAN_PLACE.search(all_text):
        return 0, {}, "no_german_place"

    # Hard filter: organizational records vs. personal papers.
    # Two complementary signals:
    #  (a) EAD origination type. corpname-only → organizational.
    #  (b) Title pattern. Many institutional collections have no usable
    #      origination element, so we also reject by title pattern.
    title = (ead.get("title") or "")
    title_l = title.lower().strip()
    if ead.get("orig_type") == "corpname":
        return 0, {}, "organizational"
    if re.match(r"^(records of|files of|records,? |"
                r"papers of (the|an?)\s)", title_l):
        return 0, {}, "organizational"
    # Topical "X (Y) Collection" / "Collection of X" — curator-assembled,
    # not personal.
    if re.match(
        r"^("
        # countries — match both noun and adjective forms.
        r"germany|german|austria|austrian|poland|polish|france|french|"
        r"hungary|hungarian|romania|romanian|russia|russian|"
        r"lithuania|lithuanian|"
        r"czechoslovakia|czechoslovakian|czech|slovak|"
        r"netherlands|dutch|italy|italian|switzerland|swiss|"
        r"ukraine|ukrainian|belarus|belarusian|"
        # cities — when a city name is the leading word of a "X Collection"
        # title, the collection is a geographic/topical aggregation
        r"berlin|vienna|wien|frankfurt|hamburg|prague|prag|warsaw|"
        # topical descriptors
        r"holocaust|shoah|territorial|karaites|genealogy|"
        r"eyewitness|displaced person|displaced persons|refugee|refugees|"
        r"sound archive|"
        # institutional acronyms
        r"yivo|hias|hicem|jdc|joint)\b.*\bcollection\b", title_l):
        return 0, {}, "organizational"
    if re.match(r"^(collection of|eyewitness accounts|"
                r"genealogy and family|sound archive)\b", title_l):
        return 0, {}, "organizational"
    # HIAS / HICEM / etc. office filings — title pattern like
    # "HIAS and HICEM Main Offices, New York: ..."
    if re.match(r"^(hias|hicem|jdc|joint|ort|yivo|aja)\b.*\b(office|main)", title_l):
        return 0, {}, "organizational"
    # Trailing "... Records" or "... Administration Records".
    if re.search(r"\b(administration records|administrative records|"
                 r"office (records|files)|"
                 r"records$|records of\b)", title_l):
        return 0, {}, "organizational"
    # Org-noun titles without personal-papers structure.
    if re.search(r"\b(committee|council|society|federation|conference|"
                 r"association|congress|service|aid|fund|organization|"
                 r"agency|institute|board|administration|synagog|hospital|"
                 r"benevolent|congregation)\b", title_l) and \
       not re.search(r"\bpapers\b", title_l):
        return 0, {}, "organizational"

    # Genre signals
    type_genre = bool(PAT_GENREFORM_PERSONAL.search(ead.get("genreform", "")))
    genre_in_prose = count_hits(PAT_GENRE, prose_blob)

    if not (type_genre or genre_in_prose):
        return 0, {}, "no_genre"

    # Birthplace gate. If the bioghist says "born in [non-German place]",
    # the German-place hits later are about professional/topical content,
    # not biography — drop. Previously surfaced false positives like
    # Schwarzbard (Bessarabia), Razovsky (St. Louis), Moe Berg (New York),
    # Lemkin (Poland), Jacob Cohen (New York) all fail this gate.
    birthplace = classify_birthplace(ead.get("bioghist", ""))
    if birthplace == "non_german":
        return 0, {}, "non_german_birthplace"

    # Date filter: max year >= 1933. Use only the EAD <unitdate>, which is the
    # archival convention for the material's date span. Years in bioghist/scope
    # text are usually about processing or biographical context, not material date.
    my = max_year(ead.get("unitdate", ""))
    if my == 0:
        return 0, {}, "undated"
    if my < 1933:
        return 0, {}, f"pre_1933 ({my})"

    # Palestine-vector exclusion
    palestine_hit = bool(PAT_PALESTINE_VECTOR.search(all_text))
    central_eu_return_hit = bool(PAT_RETURN_TO_CENTRAL_EUROPE.search(all_text))
    heimat_hit = bool(PAT_HEIMAT.search(all_text))

    # If only Palestine destination signals and no Central-European return,
    # memoir, Heimat, or correspondence-genreform — drop.
    if palestine_hit and not central_eu_return_hit and not heimat_hit:
        # A correspondence genreform is enough to keep it (letters might be
        # between émigré and people back home).
        has_correspondence = bool(re.search(r"correspondenc|letters|brief|התכתבות",
                                            ead.get("genreform", ""), re.I))
        has_memoir = bool(re.search(r"memoir|autobiograph|reminiscenc|זכרונות",
                                    ead.get("genreform", ""), re.I))
        if not (has_correspondence or has_memoir):
            # Check the title and prose: maybe the only visit signal is Palestine.
            non_palestine_visit = False
            for m in PAT_RETURN_VERB.finditer(prose_blob):
                window = prose_blob[max(0, m.start() - 40): m.end() + 200]
                if PAT_GERMAN_PLACE.search(window) and \
                   not PAT_PALESTINE_VECTOR.search(window):
                    non_palestine_visit = True; break
            if not non_palestine_visit:
                return 0, {}, "palestine_vector"

    # Sub-scores
    def sat(n, cap=3): return min(n, cap)

    ret_de = return_in_german_proximity(prose_blob)
    born_de = count_hits(PAT_BORN_GERMAN, prose_blob)
    heimat = count_hits(PAT_HEIMAT, all_text)
    german_places = len(set(m.group(0).lower()
                            for m in PAT_GERMAN_PLACE.finditer(all_text)))
    emigre = count_hits(PAT_EMIGRE, all_text)

    s = (
        15 * sat(ret_de) +
        10 * sat(born_de) +
        8  * sat(heimat) +
        6  * (1 if type_genre else 0) +
        4  * sat(genre_in_prose) +
        3  * sat(german_places, cap=5) +
        2  * sat(emigre, cap=2) +
        (3 if central_eu_return_hit else 0) +
        (-5 if palestine_hit and not central_eu_return_hit and not heimat_hit else 0) +
        (12 if birthplace == "german" else 0)
    )

    # Snippet for human review
    snippet = ""
    for pat in [PAT_RETURN_TO_CENTRAL_EUROPE, PAT_HEIMAT, PAT_BORN_GERMAN]:
        m = pat.search(prose_blob)
        if m:
            start = max(0, m.start() - 80); end = min(len(prose_blob), m.end() + 200)
            snippet = prose_blob[start:end].replace("\t", " ").replace("\n", " ").strip()[:380]
            break

    return s, {
        "type_genre": int(type_genre),
        "genre_prose": genre_in_prose,
        "german_places": german_places,
        "ret_de": ret_de,
        "born_de": born_de,
        "heimat": heimat,
        "emigre": emigre,
        "palestine_hit": int(palestine_hit),
        "ce_return_hit": int(central_eu_return_hit),
        "birthplace": birthplace,
        "max_year": my,
        "snippet": snippet,
    }, "kept"


# --- driver ------------------------------------------------------------------

def iter_ead_paths(root_dirs):
    """Deduplicate by (repo_id, resource_id), preferring the full-harvest copy."""
    seen = set()
    for d in root_dirs:
        if not d.exists():
            continue
        for p in sorted(d.glob("**/*.xml")):
            name = p.name
            if name.startswith("repo-"):
                m = re.match(r"repo-(\d+)-resource-(\d+)\.xml", name)
                if not m:
                    continue
                key = (m.group(1), m.group(2))
            else:
                key = (p.parent.name.split("-", 1)[1],
                       name.replace("resource-", "").replace(".xml", ""))
            if key in seen:
                continue
            seen.add(key)
            yield p


def main():
    base = Path(__file__).parent.parent / "data" / "cjh-oai"
    dirs = [base / "records" / "oai_ead",            # full harvest output
            base / "records" / "oai_ead_on_demand"]  # enrich_hot cache

    rows = []
    rejects = {"no_ead": 0, "no_german_place": 0, "organizational": 0,
               "no_genre": 0, "non_german_birthplace": 0, "undated": 0,
               "pre_1933": 0, "palestine_vector": 0, "kept": 0}
    for path in iter_ead_paths(dirs):
        # Path layout: .../repo-{N}/resource-{ID}.xml  OR
        #              .../oai_ead_on_demand/repo-{N}-resource-{ID}.xml
        name = path.name  # resource-{ID}.xml  or repo-{N}-resource-{ID}.xml
        if name.startswith("repo-"):
            m = re.match(r"repo-(\d+)-resource-(\d+)\.xml", name)
            repo_id, resource_id = (m.group(1), m.group(2)) if m else ("", "")
        else:
            repo_id = path.parent.name.split("-", 1)[1]
            resource_id = name.replace("resource-", "").replace(".xml", "")

        ead = ead_text(path)
        prose_blob = "\n".join(ead.get(k, "") for k in
                               ("bioghist", "scopecontent", "abstract"))
        all_text = "\n".join(ead.get(k, "") for k in
                             ("title", "unitdate", "abstract", "langmaterial",
                              "origination", "bioghist", "scopecontent",
                              "subjects", "geognames", "genreform"))

        sc, sub, reason = score(ead, prose_blob, all_text)
        if reason.startswith("pre_1933"):
            rejects["pre_1933"] += 1
        else:
            rejects[reason] = rejects.get(reason, 0) + 1
        if sc <= 0:
            continue

        birth, death = extract_birth_death(ead.get("origination", ""))
        rows.append({
            "score": sc,
            "repo_id": repo_id,
            "resource_id": resource_id,
            "title": (ead.get("title") or "")[:180],
            "origination": (ead.get("origination") or "")[:140],
            "birth": birth or "",
            "death": death or "",
            "max_year": sub["max_year"],
            "birthplace": sub["birthplace"],
            "type_genre": sub["type_genre"],
            "genre_prose": sub["genre_prose"],
            "ret_de": sub["ret_de"],
            "born_de": sub["born_de"],
            "heimat": sub["heimat"],
            "palestine_hit": sub["palestine_hit"],
            "ce_return_hit": sub["ce_return_hit"],
            "german_places": sub["german_places"],
            "emigre": sub["emigre"],
            "langmaterial": (ead.get("langmaterial") or "")[:120],
            "geognames": (ead.get("geognames") or "")[:240],
            "genreform": (ead.get("genreform") or "")[:200],
            "snippet": sub["snippet"],
            "url": f"https://archives.cjh.org/repositories/{repo_id}/resources/{resource_id}",
        })

    rows.sort(key=lambda r: r["score"], reverse=True)
    cols = ["score", "repo_id", "resource_id", "title", "origination",
            "birth", "death", "max_year", "birthplace", "type_genre",
            "genre_prose", "ret_de", "born_de", "heimat", "palestine_hit",
            "ce_return_hit", "german_places", "emigre", "langmaterial",
            "geognames", "genreform", "snippet", "url"]
    out_path = base / "ead_candidates.tsv"
    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, delimiter="\t", extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    print(f"scored {sum(rejects.values())} records; kept {len(rows)}")
    print("rejection breakdown:")
    for k, v in sorted(rejects.items(), key=lambda kv: -kv[1]):
        print(f"  {k:20} {v}")
    print(f"wrote {out_path}")
    print("\nTop 25:")
    for r in rows[:25]:
        print(f"  {r['score']:3} [{r['repo_id']}/{r['resource_id']}] "
              f"y{r['max_year']} b{r['birth'] or '?'} bp:{r['birthplace'][:3]} "
              f"ret:{r['ret_de']} born:{r['born_de']} hei:{r['heimat']} "
              f"P:{r['palestine_hit']}/CE:{r['ce_return_hit']} | "
              f"{r['title'][:80]}")


if __name__ == "__main__":
    main()
