"""Bulk-ingest missing Jecke records into Omeka S.

Reads:
  data/omeka-audit/open_records_missing_from_omeka.txt   (target item_ids)
  data/JeckeArchive/Jecke-items.tsv                      (source rows)
  data/omeka-audit/class_map.json                        (class -> template/item_set)

Usage:
  python code/ingest_jecke.py --dry-run --sample-per-class    # one payload per class
  python code/ingest_jecke.py --limit 1                       # POST one item live
  python code/ingest_jecke.py                                 # POST all missing
"""
from __future__ import annotations
import argparse, csv, json, sys
from pathlib import Path
from omeka import Omeka

ROOT = Path(__file__).resolve().parent.parent
TSV = ROOT / "data/JeckeArchive/Jecke-items.tsv"
MISSING = ROOT / "data/omeka-audit/open_records_missing_from_omeka.txt"
CLASS_MAP_FILE = ROOT / "data/omeka-audit/class_map.json"
LOG = ROOT / "data/omeka-audit/ingest_log.tsv"
SITE_ID = 1

# Property IDs (must match create_templates.py)
PROPS = {
    "dcterms:identifier":              10,
    "dcterms:isPartOf":                33,
    "dcterms:title":                   1,
    "ric-o:title":                     3541,
    "ric-o:generalDescription":        3502,
    "ric-o:hasAuthor":                 3139,
    "ric-o:hasOrHadLanguage":          3201,
    "ric-o:hasDocumentaryFormType":    3163,
    "ric-o:hasProductionTechniqueType":3240,
    "ric-o:hasRecordState":            3245,
    "ric-o:hasOrHadMainSubject":       3205,
    "ric-o:hasCreationDate":           3150,
    "ric-o:hasPublicationDate":        3241,
    "arkivo:creationPlace":            1663,
    "bibo:numPages":                   106,
}


def lit(prop: str, value: str, lang: str | None = None) -> dict:
    out = {"type": "literal", "property_id": PROPS[prop], "@value": value}
    if lang:
        out["@language"] = lang
    return out


def build_payload(row: dict, class_map: dict) -> tuple[dict, list[int]] | None:
    """Returns (payload, [extra item_set_ids for composite classes]) or None."""
    raw_class = (row.get("item_class") or "").strip()
    if not raw_class:
        return None
    # Composite class: take all valid components and use first as template
    parts = [p.strip() for p in raw_class.split("|") if p.strip()]
    primary, extras = None, []
    for p in parts:
        if p in class_map:
            if primary is None:
                primary = p
            else:
                extras.append(class_map[p]["item_set_id"])
    if primary is None:
        primary = "MISC"
        if primary not in class_map:
            return None
    spec = class_map[primary]
    item_sets = [{"o:id": spec["item_set_id"]}] + [{"o:id": x} for x in extras]

    payload: dict = {
        "@type": "o:Item",
        "o:is_public": True,
        "o:resource_template": {"o:id": spec["template_id"]},
        "o:item_set":         item_sets,
        "o:site":             [{"o:id": SITE_ID}],
    }
    if spec.get("resource_class_id"):
        payload["o:resource_class"] = {"o:id": spec["resource_class_id"]}

    def add(prop: str, value: str | None, lang: str | None = None):
        v = (value or "").strip()
        if v:
            payload.setdefault(prop, []).append(lit(prop, v, lang))

    add("dcterms:identifier",          row["item_id"])
    add("dcterms:isPartOf",            row.get("parent"))
    add("dcterms:title",               row.get("title"))
    add("ric-o:generalDescription",    row.get("item_description"),    "he")
    add("ric-o:generalDescription",    row.get("german_translation"),  "de")
    add("ric-o:generalDescription",    row.get("english_translation"))
    add("ric-o:hasOrHadLanguage",      row.get("language"))
    add("ric-o:hasDocumentaryFormType",row.get("document_type"))
    add("ric-o:hasProductionTechniqueType", row.get("production_technique_type"))
    add("ric-o:hasRecordState",        row.get("record_state"))
    add("ric-o:hasOrHadMainSubject",   row.get("main_subject"))
    add("ric-o:hasCreationDate",       row.get("creation_date"))
    add("ric-o:hasPublicationDate",    row.get("publication_date"))
    add("arkivo:creationPlace",        row.get("creation_place"))
    add("bibo:numPages",               row.get("number_of_pages"))
    return payload


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--sample-per-class", action="store_true",
                    help="dry-run mode: one payload per class")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    class_map = json.loads(CLASS_MAP_FILE.read_text())
    missing = set(MISSING.read_text().splitlines())
    rows: dict[str, dict] = {}
    with TSV.open(encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            if row["item_id"] in missing:
                rows[row["item_id"]] = row
    print(f"Missing IDs: {len(missing)}, matched in TSV: {len(rows)}")

    if args.sample_per_class:
        args.dry_run = True
        # one row per primary class
        seen = set()
        sampled = {}
        for iid, row in sorted(rows.items()):
            cls = (row.get("item_class") or "").split("|")[0].strip()
            if cls and cls not in seen:
                seen.add(cls); sampled[iid] = row
        rows = sampled
        print(f"sample-per-class: {len(rows)} payloads")

    om = Omeka() if not args.dry_run else None
    stats = {"posted": 0, "skipped": 0, "errors": 0}
    log_rows = []

    for i, (iid, row) in enumerate(sorted(rows.items())):
        if args.limit and stats["posted"] + stats["errors"] >= args.limit:
            break
        result = build_payload(row, class_map)
        if result is None:
            stats["skipped"] += 1
            print(f"SKIP {iid}: no class match for {row.get('item_class')!r}")
            continue
        payload = result
        if args.dry_run:
            print(f"\n--- {iid}  class={row.get('item_class')!r} ---")
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            continue
        try:
            r = om.post("items", payload)
            stats["posted"] += 1
            print(f"OK   {iid} -> o:id={r['o:id']}")
            log_rows.append((iid, r["o:id"], ""))
        except Exception as e:
            stats["errors"] += 1
            print(f"ERR  {iid}: {e}", file=sys.stderr)
            log_rows.append((iid, "", str(e)[:200]))

    if log_rows:
        new = not LOG.exists()
        with LOG.open("a") as f:
            if new:
                f.write("item_id\tomeka_id\terror\n")
            for r in log_rows:
                f.write("\t".join(str(x) for x in r) + "\n")

    print("\n", stats)
    return 0 if stats["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
