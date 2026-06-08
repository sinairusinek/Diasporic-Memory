"""For each record in candidates / return_or_born_german.tsv, fetch the full
Encoded Archival Description record via OAI-PMH GetRecord, parse the rich
biographical and scope fields, and produce an enriched TSV.

Adds columns: bioghist (truncated), scopecontent (truncated), subjects,
geognames, languages, creator_birth_year, creator_death_year, period_jecke
(creator born 1870-1930), and a manual_keep recommendation that combines
the rule outputs.
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlencode

import requests
from lxml import etree as LET

ENDPOINT = "https://archives.cjh.org/oai"
USER_AGENT = "Mozilla/5.0 (compatible; JeckeArchive-OAI/0.1; +contact: edit-me@example.com)"

EAD_NS = "urn:isbn:1-931666-22-9"
OAI_NS = "http://www.openarchives.org/OAI/2.0/"
NS = {"o": OAI_NS, "ead": EAD_NS}

# Reused from score_cjh.py — keep in sync if those evolve.
PAT_GERMAN_PLACE = re.compile(
    r"\b(german(y|s)?|deutschland|austria|österreich|"
    r"berlin|frankfurt|hamburg|munich|münchen|wien|vienna|"
    r"breslau|wrocław|leipzig|dresden|cologne|köln|stuttgart|"
    r"prague|prag|praha|bohemia|moravia|silesia|sudeten|"
    r"bavaria|bayern|saxony|sachsen|hesse|hessen|württemberg|"
    r"alsace|elsass|baden|swabia|schwaben|"
    r"galicia|bukovina|"
    r"baltic states|riga|königsberg|danzig|gdańsk|memel|kaunas|kovno)\b", re.I)

PAT_RETURN_VERB = re.compile(
    r"\b(return(ed|ing)?|revisit(ed|ing)?|visit(ed|ing)?|trip|journey|"
    r"travelled|traveled|went back|pilgrimage)\b", re.I)


def fetch_ead(session, identifier: str) -> bytes:
    params = {"verb": "GetRecord", "metadataPrefix": "oai_ead",
              "identifier": identifier}
    for attempt in range(3):
        try:
            r = session.get(ENDPOINT, params=params, timeout=60)
            r.raise_for_status()
            return r.content
        except requests.RequestException:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def text_of(elements) -> str:
    parts = []
    for e in elements:
        # itertext drops markup, preserving the prose
        parts.append(" ".join(t.strip() for t in e.itertext() if t.strip()))
    return "\n".join(p for p in parts if p)


def parse_ead(body: bytes) -> dict:
    parser = LET.XMLParser(recover=True, huge_tree=True)
    root = LET.fromstring(body, parser=parser)
    ead = root.find(".//{%s}ead" % EAD_NS)
    if ead is None:
        return {}
    archdesc = ead.find("{%s}archdesc" % EAD_NS)
    if archdesc is None:
        return {}

    def find_all(xpath):
        return archdesc.findall(xpath, namespaces={"ead": EAD_NS})

    return {
        "bioghist":     text_of(find_all(".//ead:bioghist")),
        "scopecontent": text_of(find_all(".//ead:scopecontent")),
        "abstract":     text_of(find_all(".//ead:did/ead:abstract")),
        "langmaterial": text_of(find_all(".//ead:did/ead:langmaterial")),
        "subjects":     " | ".join(text_of([e]) for e in find_all(".//ead:controlaccess/ead:subject")),
        "geognames":    " | ".join(text_of([e]) for e in find_all(".//ead:controlaccess/ead:geogname")),
        "persnames":    " | ".join(text_of([e]) for e in find_all(".//ead:controlaccess/ead:persname")),
        "corpnames":    " | ".join(text_of([e]) for e in find_all(".//ead:controlaccess/ead:corpname")),
        "genreform":    " | ".join(text_of([e]) for e in find_all(".//ead:controlaccess/ead:genreform")),
    }


def extract_birth_death(creator: str):
    """From 'Lorch, Adolf, 1883-1971' style strings."""
    m = re.search(r"(\d{4})\s*[-–]\s*(\d{4})", creator)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"\b(\d{4})\s*[-–]\s*$", creator)
    if m:
        return int(m.group(1)), None
    m = re.search(r"\bb\.?\s*(\d{4})", creator)
    if m:
        return int(m.group(1)), None
    return None, None


def return_to_german_in_text(text: str) -> int:
    hits = 0
    for m in PAT_RETURN_VERB.finditer(text):
        window = text[max(0, m.start() - 40): m.end() + 120]
        if PAT_GERMAN_PLACE.search(window):
            hits += 1
    return hits


def enrich(in_path: Path, out_path: Path, delay: float, cache_dir: Path):
    cache_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    in_rows = list(csv.DictReader(in_path.open(encoding="utf-8"), delimiter="\t"))
    print(f"enriching {len(in_rows)} records from {in_path.name}")

    out_rows = []
    for i, r in enumerate(in_rows, 1):
        ident = f"oai:archivesspace:/repositories/{r['repo_id']}/resources/{r['resource_id']}"
        cache = cache_dir / f"repo-{r['repo_id']}-resource-{r['resource_id']}.xml"
        if cache.exists():
            body = cache.read_bytes()
        else:
            print(f"  [{i:3}/{len(in_rows)}] fetching {ident}")
            body = fetch_ead(session, ident)
            cache.write_bytes(body)
            time.sleep(delay)
        ead = parse_ead(body)
        if not ead:
            print(f"    no EAD body parsed", file=sys.stderr)
            continue

        bioghist = ead.get("bioghist", "")
        scope    = ead.get("scopecontent", "")
        combined = "\n".join([bioghist, scope, ead.get("abstract", "")])

        birth, death = extract_birth_death(r.get("creator", ""))
        # Jecke working definition: born 1870-1930 in German-speaking territory.
        period_jecke = bool(birth and 1870 <= birth <= 1930)

        # Re-do the return-to-German check on the full EAD prose (much more text
        # than DC description; should catch hits the title-only scan missed).
        ret_ead = return_to_german_in_text(combined)

        # Pull a 240-char snippet around the strongest evidence for human review.
        snippet = ""
        for pat in [
            re.compile(r"[^.]*\b(return|revisit|visit|trip|journey)\b[^.]*\b("
                       + PAT_GERMAN_PLACE.pattern.strip("\\b()") + r")\b[^.]*\.", re.I),
            re.compile(r"[^.]*\bborn\b[^.]{0,80}\b("
                       + PAT_GERMAN_PLACE.pattern.strip("\\b()") + r")\b[^.]*\.", re.I),
        ]:
            m = pat.search(combined)
            if m:
                snippet = m.group(0).strip().replace("\t", " ").replace("\n", " ")[:300]
                break

        out_rows.append({
            **r,
            "birth": birth or "",
            "death": death or "",
            "period_jecke": int(period_jecke),
            "ret_ead": ret_ead,
            "bioghist_len": len(bioghist),
            "scope_len": len(scope),
            "snippet": snippet,
            "geognames": ead.get("geognames", "")[:300],
            "subjects": ead.get("subjects", "")[:300],
            "langmaterial": ead.get("langmaterial", "")[:120],
        })

    cols = list(in_rows[0].keys()) + ["birth", "death", "period_jecke",
                                       "ret_ead", "bioghist_len", "scope_len",
                                       "snippet", "geognames", "subjects",
                                       "langmaterial"]
    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, delimiter="\t", extrasaction="ignore")
        w.writeheader()
        w.writerows(out_rows)
    print(f"wrote {len(out_rows)} enriched rows to {out_path}")


def main():
    p = argparse.ArgumentParser()
    base = Path(__file__).parent.parent / "data" / "cjh-oai"
    p.add_argument("--in", dest="in_path",
                   default=str(base / "return_or_born_german.tsv"))
    p.add_argument("--out", default=str(base / "hot_enriched.tsv"))
    p.add_argument("--cache", default=str(base / "records" / "oai_ead_on_demand"))
    p.add_argument("--delay", type=float, default=1.0)
    args = p.parse_args()
    enrich(Path(args.in_path), Path(args.out), args.delay, Path(args.cache))


if __name__ == "__main__":
    main()
