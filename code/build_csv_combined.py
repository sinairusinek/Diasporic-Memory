"""Build ONE combined CSV for Omeka S CSV Import.

Per-row template/item_set/resource_class columns let the importer assign each
row independently. Skips the Academic Paper class (already imported manually).

Output: data/omeka-audit/csv-import/combined_all.csv
"""
from __future__ import annotations
import csv, json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TSV = ROOT / "data/JeckeArchive/Jecke-items.tsv"
MISSING = ROOT / "data/omeka-audit/open_records_missing_from_omeka.txt"
CLASS_MAP_FILE = ROOT / "data/omeka-audit/class_map.json"
OUT = ROOT / "data/omeka-audit/csv-import/combined_all.csv"

EXCLUDE_CLASSES = {"Academic Paper"}

CLASS_ID_TO_TERM = {
    35: "bibo:AcademicArticle",
    36: "bibo:Article",
    26: "dctype:Image",
    32: "dctype:PhysicalObject",
    64: "bibo:LegalDocument",
    72: "bibo:Newspaper",
    1016: "arkivo:Certificate",
    1019: "arkivo:Creative_Fiction",
    1024: "arkivo:EgoDocument",
    1025: "arkivo:Ephemera",
    1027: "arkivo:Financial_Document",
    1037: "arkivo:Medical_Document",
    1039: "arkivo:Meta_Document",
    1041: "arkivo:Organization_Papertrail",
    1047: "arkivo:Report",
}

HEADERS = [
    # Resource-level fields (map to Omeka internals in CSV Import UI)
    "resource_template_label",
    "item_set_id",
    "resource_class_term",
    "is_public",
    # Property values
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


def main():
    class_map = json.loads(CLASS_MAP_FILE.read_text())
    missing = set(MISSING.read_text().splitlines())

    rows_out: list[dict] = []
    skipped_excluded = 0
    composite_extras: list[tuple[str, str, int]] = []
    unmapped: list[tuple[str, str]] = []

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
            if primary in EXCLUDE_CLASSES:
                skipped_excluded += 1
                continue
            for x in extras:
                composite_extras.append((row["item_id"], primary, x))

            spec = class_map[primary]
            out_row = {h: "" for h in HEADERS}
            out_row["resource_template_label"] = spec["label"]
            out_row["item_set_id"]             = spec["item_set_id"]
            cid = spec.get("resource_class_id")
            out_row["resource_class_term"]     = CLASS_ID_TO_TERM.get(cid, "") if cid else ""
            out_row["is_public"]               = "true"
            for tsv_col, hdr in TSV_TO_HEADER.items():
                v = (row.get(tsv_col) or "").strip()
                if v:
                    out_row[hdr] = v
            rows_out.append(out_row)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=HEADERS, quoting=csv.QUOTE_MINIMAL)
        w.writeheader()
        w.writerows(rows_out)

    # Re-emit a combined-only composite extras list
    if composite_extras:
        p = ROOT / "data/omeka-audit/csv-import/composite_extras_combined.tsv"
        with p.open("w", encoding="utf-8") as f:
            f.write("item_id\tprimary_class\textra_item_set_id\n")
            for r in composite_extras:
                f.write(f"{r[0]}\t{r[1]}\t{r[2]}\n")

    print(f"Wrote {OUT} with {len(rows_out)} rows")
    print(f"Skipped (excluded classes {EXCLUDE_CLASSES}): {skipped_excluded}")
    print(f"Composite extras in combined CSV: {len(composite_extras)}")
    print(f"Unmapped routed to MISC: {len(unmapped)}")


if __name__ == "__main__":
    main()
