"""Bulk-ingest missing Jecke records into Omeka S.

Reads:
  data/omeka-audit/open_records_missing_from_omeka.txt   (target item_ids)
  data/JeckeArchive/Jecke-items.tsv                      (source rows)

Usage:
  python code/ingest_jecke.py --dry-run --limit 3       # print payloads, no POST
  python code/ingest_jecke.py --limit 1                 # POST one item
  python code/ingest_jecke.py                           # POST all missing

Field mapping (TSV column -> Omeka property):
  item_id              -> dcterms:identifier (10)
  parent               -> dcterms:isPartOf   (33)
  title                -> dcterms:title      (1)
  item_description     -> dcterms:description (4) @language he
  german_translation   -> dcterms:description (4) @language de
  english_translation  -> dcterms:description (4)
  format               -> dcterms:format     (9)
  language             -> dcterms:language   (12)
  document_type        -> dcterms:type       (8)
  main_subject         -> dcterms:subject    (3)
  record_state         -> bibo:status        (81)
  item_class           -> selects resource_template + item_set
"""
from __future__ import annotations
import argparse, csv, json, sys
from pathlib import Path
from omeka import Omeka

ROOT = Path(__file__).resolve().parent.parent
TSV = ROOT / "data/JeckeArchive/Jecke-items.tsv"
MISSING = ROOT / "data/omeka-audit/open_records_missing_from_omeka.txt"
SITE_ID = 1

# item_class -> (resource_template_id, item_set_id)
CLASS_MAP = {
    "Communication Document": (7, 6826),
}

PROPS = {
    "dcterms:identifier":  10,
    "dcterms:isPartOf":    33,
    "dcterms:title":       1,
    "dcterms:description": 4,
    "dcterms:format":      9,
    "dcterms:language":    12,
    "dcterms:type":        8,
    "dcterms:subject":     3,
    "bibo:status":         81,
}


def lit(value: str, prop: str, lang: str | None = None) -> dict:
    out = {"type": "literal", "property_id": PROPS[prop], "@value": value}
    if lang:
        out["@language"] = lang
    return out


def build_payload(row: dict) -> dict | None:
    cls = (row.get("item_class") or "").strip()
    mapping = CLASS_MAP.get(cls)
    if not mapping:
        return None  # caller will log/skip
    template_id, item_set_id = mapping

    payload: dict = {
        "@type": "o:Item",
        "o:is_public": True,
        "o:resource_template": {"o:id": template_id},
        "o:item_set":         [{"o:id": item_set_id}],
        "o:site":             [{"o:id": SITE_ID}],
    }

    def add(prop: str, value: str | None, lang: str | None = None):
        v = (value or "").strip()
        if not v:
            return
        payload.setdefault(prop, []).append(lit(v, prop, lang))

    add("dcterms:identifier", row["item_id"])
    add("dcterms:isPartOf",   row.get("parent"))
    add("dcterms:title",      row.get("title"))
    add("dcterms:description", row.get("item_description"),    "he")
    add("dcterms:description", row.get("german_translation"),  "de")
    add("dcterms:description", row.get("english_translation"))
    add("dcterms:format",     row.get("format"))
    add("dcterms:language",   row.get("language"))
    add("dcterms:type",       row.get("document_type"))
    add("dcterms:subject",    row.get("main_subject"))
    add("bibo:status",        row.get("record_state"))
    return payload


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="print payloads, don't POST")
    ap.add_argument("--limit", type=int, default=None, help="stop after N items")
    args = ap.parse_args()

    missing = set(MISSING.read_text().splitlines())
    by_id: dict[str, dict] = {}
    with TSV.open(encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            if row["item_id"] in missing:
                by_id[row["item_id"]] = row

    not_in_tsv = missing - by_id.keys()
    if not_in_tsv:
        print(f"WARN {len(not_in_tsv)} ids missing from TSV (skipped)", file=sys.stderr)

    om = Omeka() if not args.dry_run else None
    stats = {"posted": 0, "skipped_class": 0, "errors": 0}

    for i, (iid, row) in enumerate(sorted(by_id.items())):
        if args.limit and i >= args.limit:
            break
        payload = build_payload(row)
        if payload is None:
            stats["skipped_class"] += 1
            print(f"SKIP {iid}: item_class={row.get('item_class')!r} not in CLASS_MAP")
            continue
        if args.dry_run:
            print(f"--- DRY-RUN payload for {iid} ---")
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            continue
        try:
            r = om.post("items", payload)
            stats["posted"] += 1
            print(f"OK   {iid} -> o:id={r['o:id']}")
        except Exception as e:
            stats["errors"] += 1
            print(f"ERR  {iid}: {e}", file=sys.stderr)

    print("\n", stats)
    return 0 if stats["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
