"""Build per-class CSVs for Omeka S CSV Import module.

One CSV per primary item_class so each import run can be configured with a
single resource_template + item_set in the UI. Composite-class rows go to
their primary class CSV; their extra item_set must be added by hand after
import (list emitted to composite_extras.tsv).

Classes not in class_map.json fall through to the MISC bucket.

Output: data/omeka-audit/csv-import/<slug>.csv
"""
from __future__ import annotations
import csv, json, re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TSV = ROOT / "data/JeckeArchive/Jecke-items.tsv"
MISSING = ROOT / "data/omeka-audit/open_records_missing_from_omeka.txt"
CLASS_MAP_FILE = ROOT / "data/omeka-audit/class_map.json"
OUT_DIR = ROOT / "data/omeka-audit/csv-import"

HEADERS = [
    "dcterms:identifier",
    "dcterms:isPartOf",
    "dcterms:title",
    "description_he",
    "description_de",
    "description_en",
    "ric-o:hasOrHadLanguage",
    "ric-o:hasDocumentaryFormType",
    "ric-o:hasProductionTechniqueType",
    "ric-o:hasRecordState",
    "ric-o:hasOrHadMainSubject",
    "ric-o:hasCreationDate",
    "ric-o:hasPublicationDate",
    "arkivo:creationPlace",
    "bibo:numPages",
]

TSV_TO_HEADER = {
    "item_id":                    "dcterms:identifier",
    "parent":                     "dcterms:isPartOf",
    "title":                      "dcterms:title",
    "item_description":           "description_he",
    "german_translation":         "description_de",
    "english_translation":        "description_en",
    "language":                   "ric-o:hasOrHadLanguage",
    "document_type":              "ric-o:hasDocumentaryFormType",
    "production_technique_type":  "ric-o:hasProductionTechniqueType",
    "record_state":               "ric-o:hasRecordState",
    "main_subject":               "ric-o:hasOrHadMainSubject",
    "creation_date":              "ric-o:hasCreationDate",
    "publication_date":           "ric-o:hasPublicationDate",
    "creation_place":             "arkivo:creationPlace",
    "number_of_pages":            "bibo:numPages",
}


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def main():
    class_map = json.loads(CLASS_MAP_FILE.read_text())
    missing = set(MISSING.read_text().splitlines())
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    buckets: dict[str, list[dict]] = defaultdict(list)
    composite_extras: list[tuple[str, str, int]] = []  # (item_id, primary, extra_set_id)
    unmapped: list[tuple[str, str]] = []               # (item_id, raw_class)

    with TSV.open(encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            if row["item_id"] not in missing:
                continue
            raw = (row.get("item_class") or "").strip()
            parts = [p.strip() for p in raw.split("|") if p.strip()]
            primary = None
            extras: list[int] = []
            for p in parts:
                if p in class_map:
                    if primary is None:
                        primary = p
                    else:
                        extras.append(class_map[p]["item_set_id"])
            if primary is None:
                unmapped.append((row["item_id"], raw))
                primary = "MISC"
            for x in extras:
                composite_extras.append((row["item_id"], primary, x))

            out_row = {h: "" for h in HEADERS}
            for tsv_col, hdr in TSV_TO_HEADER.items():
                v = (row.get(tsv_col) or "").strip()
                if v:
                    out_row[hdr] = v
            buckets[primary].append(out_row)

    manifest = []
    for cls, rows in sorted(buckets.items()):
        spec = class_map[cls]
        path = OUT_DIR / f"{slug(cls)}.csv"
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=HEADERS, quoting=csv.QUOTE_MINIMAL)
            w.writeheader()
            w.writerows(rows)
        manifest.append({
            "class": cls,
            "file": path.relative_to(ROOT).as_posix(),
            "rows": len(rows),
            "template_id": spec["template_id"],
            "item_set_id": spec["item_set_id"],
            "resource_class_id": spec.get("resource_class_id"),
            "label": spec["label"],
        })

    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2))

    if composite_extras:
        p = OUT_DIR / "composite_extras.tsv"
        with p.open("w", encoding="utf-8") as f:
            f.write("item_id\tprimary_class\textra_item_set_id\n")
            for r in composite_extras:
                f.write(f"{r[0]}\t{r[1]}\t{r[2]}\n")

    if unmapped:
        p = OUT_DIR / "unmapped_classes.tsv"
        with p.open("w", encoding="utf-8") as f:
            f.write("item_id\traw_item_class\n")
            for r in unmapped:
                f.write(f"{r[0]}\t{r[1]}\n")

    total = sum(m["rows"] for m in manifest)
    print(f"Wrote {len(manifest)} CSVs covering {total} rows -> {OUT_DIR}")
    print(f"Composite extras: {len(composite_extras)}")
    print(f"Unmapped (routed to MISC): {len(unmapped)}")


if __name__ == "__main__":
    main()
