"""Left-join the existing item-level catalogue with the Hecht folder-level register.

Inputs
------
data/Documents2024-12-13.tsv           item-level catalogue (1 row per piece)
data/hecht/accession_register.tsv      folder-level register (1 row per G.X.XXXX/Y)

Outputs
-------
data/hecht/catalogue_with_hecht.tsv    catalogue rows + hecht_* enrichment columns
data/hecht/unmatched_hecht.tsv         Hecht records with NO catalogue folder match
data/hecht/unmatched_catalogue_folders.tsv
                                       Catalogue folders with NO Hecht record
data/hecht/merge_summary.txt           plain-text counts
"""

from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from pathlib import Path

CATALOGUE = Path("data/Documents2024-12-13.tsv")
HECHT = Path("data/hecht/archive_folders.tsv")
OUT_JOINED = Path("data/hecht/catalogue_with_hecht.tsv")
OUT_HECHT_ONLY = Path("data/hecht/unmatched_hecht_folders.tsv")
OUT_CAT_ONLY = Path("data/hecht/unmatched_catalogue_folders.tsv")
OUT_SUMMARY = Path("data/hecht/merge_summary.txt")

FOLDER_RE = re.compile(r"IL-MTFN-\d+-([A-Z])-([A-Z])-(\d{3,5})(?:-(\d{1,4}))?")

# Only carry fields that the ADLIB catalogue does NOT already have at the item level.
# Per-item descriptions (artist/work_title/item_type/description) are skipped because
# the Hecht record describes the FOLDER as a whole, and duplicating it across every
# item in the folder would be misleading.
HECHT_ENRICHMENT_FIELDS = [
    "donor",
    "acquisition_date",
    "donation_no",
    "registrar",
    "origin",
    "bio_chrono",
    "subject_narrow",
    "subject_broad",
    "category",
    "condition",
    "location",
    "notes",
    "source_pages",
]


def catalogue_folder_key(item_id: str) -> str | None:
    m = FOLDER_RE.match(item_id)
    if not m:
        return None
    a, b, main, sub = m.groups()
    base = f"{a}-{b}-{int(main):04d}"
    return base + (f"-{int(sub)}" if sub else "")


def hecht_folder_key(accession_id: str) -> str:
    # Map single-piece Hecht ids (e.g. G-F-0004) to catalogue's -1 convention.
    if accession_id.count("-") == 2:
        return f"{accession_id}-1"
    return accession_id


def main() -> None:
    hecht_records: dict[str, dict] = {}
    with HECHT.open() as f:
        for row in csv.DictReader(f, delimiter="\t"):
            hecht_records[row["accession_id"]] = row

    hecht_by_folder_key: dict[str, dict] = {}
    for aid, rec in hecht_records.items():
        hecht_by_folder_key[hecht_folder_key(aid)] = rec

    cat_rows: list[dict] = []
    cat_folder_keys: set[str] = set()
    cat_folder_to_rows: dict[str, list[dict]] = defaultdict(list)
    with CATALOGUE.open() as f:
        reader = csv.DictReader(f, delimiter="\t")
        cat_fields = list(reader.fieldnames or [])
        for row in reader:
            cat_rows.append(row)
            k = catalogue_folder_key((row.get("item_id") or "").strip())
            if k:
                cat_folder_keys.add(k)
                cat_folder_to_rows[k].append(row)

    matched_folders = cat_folder_keys & set(hecht_by_folder_key)
    hecht_only = set(hecht_by_folder_key) - cat_folder_keys
    cat_only = cat_folder_keys - set(hecht_by_folder_key)

    out_fields = cat_fields + ["hecht_folder_key", "hecht_accession_id"] + [
        f"hecht_{f}" for f in HECHT_ENRICHMENT_FIELDS
    ]
    enriched_items = 0
    with OUT_JOINED.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=out_fields, delimiter="\t",
                           extrasaction="ignore")
        w.writeheader()
        for row in cat_rows:
            k = catalogue_folder_key((row.get("item_id") or "").strip())
            out = dict(row)
            h = hecht_by_folder_key.get(k) if k else None
            if h:
                out["hecht_folder_key"] = k
                out["hecht_accession_id"] = h["accession_id"]
                for fld in HECHT_ENRICHMENT_FIELDS:
                    out[f"hecht_{fld}"] = h.get(fld, "")
                enriched_items += 1
            w.writerow(out)

    with OUT_HECHT_ONLY.open("w", newline="") as f:
        sample = next(iter(hecht_records.values()))
        w = csv.DictWriter(f, fieldnames=list(sample.keys()), delimiter="\t",
                           extrasaction="ignore")
        w.writeheader()
        for aid in sorted(hecht_records):
            if hecht_folder_key(aid) in hecht_only:
                w.writerow(hecht_records[aid])

    with OUT_CAT_ONLY.open("w", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["folder_key", "item_count", "sample_item_id"])
        for k in sorted(cat_only):
            items = cat_folder_to_rows[k]
            w.writerow([k, len(items), items[0].get("item_id", "")])

    hecht_prefix_counts = Counter(
        aid.split("-")[0] + "-" + aid.split("-")[1]
        for aid in hecht_records
    )
    hecht_only_prefix = Counter(
        aid.split("-")[0] + "-" + aid.split("-")[1]
        for aid in hecht_records
        if hecht_folder_key(aid) in hecht_only
    )

    with OUT_SUMMARY.open("w") as f:
        f.write("Hecht ↔ catalogue merge summary\n")
        f.write("================================\n\n")
        f.write(f"Catalogue items                  : {len(cat_rows)}\n")
        f.write(f"Catalogue distinct folders       : {len(cat_folder_keys)}\n")
        f.write(f"Hecht records                    : {len(hecht_records)}\n")
        f.write("\nHecht records by collection:\n")
        for p, c in hecht_prefix_counts.most_common():
            f.write(f"  {p}: {c}\n")
        f.write(f"\nFolders matched (Hecht ↔ cat)    : {len(matched_folders)}\n")
        f.write(f"Catalogue items enriched         : {enriched_items}\n")
        f.write(f"\nHecht-only folders (new content) : {len(hecht_only)}\n")
        for p, c in hecht_only_prefix.most_common():
            f.write(f"  {p}: {c}\n")
        f.write(f"\nCatalogue-only folders (no Hecht record): {len(cat_only)}\n")

    print(OUT_SUMMARY.read_text())


if __name__ == "__main__":
    main()
