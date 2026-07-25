"""Split the unified Hecht accession register into its two latent corpora:

  1. archive_folders.tsv  — 958 G-F folder-level provenance records (Heinrich
                             Hecht's archival collection)
  2. library.tsv          — 5,374 G-B / H-B / E-B / F-B book records (a Jecke
                             book library; columns renamed to book semantics)

Inputs : data/hecht/accession_register.tsv
Outputs: data/hecht/archive_folders.tsv, data/hecht/library.tsv
"""

from __future__ import annotations

import csv
from pathlib import Path

SRC = Path("data/hecht/accession_register.tsv")
OUT_ARCHIVE = Path("data/hecht/archive_folders.tsv")
OUT_LIBRARY = Path("data/hecht/library.tsv")

LANG_BY_PREFIX = {"G-B": "de", "H-B": "he", "E-B": "en", "F-B": "fr"}

ARCHIVE_FIELDS = [
    "accession_id", "accession_raw",
    "artist", "artist_en",
    "work_title", "work_title_en",
    "item_type", "item_type_en",
    "technique", "technique_en",
    "description",
    "dimensions", "years",
    "subject_narrow", "subject_broad",
    "origin", "origin_en",
    "bio_chrono", "category",
    "location", "condition", "registrar",
    "insurance_value", "donation_no", "acquisition_date",
    "donor", "notes",
    "source_pages",
]

LIBRARY_FIELDS = [
    "accession_id", "language",
    "author", "title", "title_en",
    "year", "pages",
    "description", "subject_narrow", "subject_broad",
    "origin", "bio_chrono", "category",
    "location", "condition", "registrar",
    "donation_no", "acquisition_date",
    "donor", "notes",
    "source_pages",
]


def main() -> None:
    archive: list[dict] = []
    library: list[dict] = []

    with SRC.open() as f:
        for row in csv.DictReader(f, delimiter="\t"):
            aid = row["accession_id"]
            prefix = "-".join(aid.split("-")[:2])
            if prefix == "G-F":
                archive.append(row)
            elif prefix in LANG_BY_PREFIX:
                lib = {
                    "accession_id": aid,
                    "language": LANG_BY_PREFIX[prefix],
                    "author": row.get("artist", ""),
                    "title": (row.get("work_title") or "").strip()
                              or (row.get("artist_en") if not row.get("work_title_en") else ""),
                    "title_en": row.get("work_title_en", ""),
                    "year": row.get("years", ""),
                    "pages": row.get("dimensions", ""),
                    "description": row.get("description", ""),
                    "subject_narrow": row.get("subject_narrow", ""),
                    "subject_broad": row.get("subject_broad", ""),
                    "origin": row.get("origin", ""),
                    "bio_chrono": row.get("bio_chrono", ""),
                    "category": row.get("category", ""),
                    "location": row.get("location", ""),
                    "condition": row.get("condition", ""),
                    "registrar": row.get("registrar", ""),
                    "donation_no": row.get("donation_no", ""),
                    "acquisition_date": row.get("acquisition_date", ""),
                    "donor": row.get("donor", ""),
                    "notes": row.get("notes", ""),
                    "source_pages": row.get("source_pages", ""),
                }
                # If title is still empty but title_en exists, that's fine; the row
                # came from a German book where the printout only shows the German title
                # in the work_title_en slot.
                library.append(lib)

    with OUT_ARCHIVE.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=ARCHIVE_FIELDS, delimiter="\t",
                           extrasaction="ignore")
        w.writeheader()
        w.writerows(archive)

    with OUT_LIBRARY.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LIBRARY_FIELDS, delimiter="\t",
                           extrasaction="ignore")
        w.writeheader()
        w.writerows(library)

    print(f"archive_folders.tsv: {len(archive)} rows")
    print(f"library.tsv        : {len(library)} rows")
    # Distribution by language
    from collections import Counter
    langs = Counter(r["language"] for r in library)
    print(f"  by language: {dict(langs)}")


if __name__ == "__main__":
    main()
