"""Extract structured records from the Hecht archive accession register PDF text.

Input : data/hecht/raw.txt   (produced by `pdftotext -layout`)
Output: data/hecht/accession_register.tsv

Each record is keyed by accession_id (e.g. G-F-0001-1, G-F-0004).
Records span one primary page plus an optional continuation page (notes / extra
donor info). Continuation pages don't repeat the accession number, so we carry
the most recent one forward.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

RAW = Path("data/hecht/raw.txt")
OUT = Path("data/hecht/accession_register.tsv")

BIDI = re.compile(r"[‎‏‪-‮⁦-⁩]")

# Right-edge Hebrew labels. Order matters only for the FIELD_ORDER output.
LABELS = {
    "מס' אוסף":              "accession",
    "שם האמן":               "artist",
    "שם היצירה":             "work_title",
    "טכניקה / חומר":         "technique",
    "תיאור היצירה":          "description",
    "סוג פריט":              "item_type",
    "מידות":                 "dimensions",
    "שנים":                  "years",
    "נושא מצומצם":           "subject_narrow",
    "נושא מורחב":            "subject_broad",
    "מוצא":                  "origin",
    "ביוגרפיה / כרונולוגיה": "bio_chrono",
    "קטגוריה":               "category",
    "מיקום":                 "location",
    "מצב החפץ":              "condition",
    "שם הרשם":               "registrar",
    "ערך לביטוח":            "insurance_value",
    "מס' תרומה":             "donation_no",
    "תאריך רכישה / תרומה":   "acquisition_date",
    "פרטי תורם":             "donor",
    "הערות":                 "notes",
}

# Some labels appear with slightly different spacing around the slash.
LABEL_VARIANTS = {
    "טכניקה/חומר": "technique",
    "ביוגרפיה/כרונולוגיה": "bio_chrono",
    "תאריך רכישה/תרומה": "acquisition_date",
}

ALL_LABELS = {**LABELS, **LABEL_VARIANTS}

# Pre-build a whitespace-collapsed lookup so labels match regardless of whether the
# PDF rendered "טכניקה / חומר", "טכניקה  /חומר", or "טכניקה/חומר".
_WS = re.compile(r"\s+")


def _normalize_label_form(s: str) -> str:
    """Normalize a label or candidate trailing-string to a canonical form so that
    'טכניקה / חומר', 'טכניקה  /חומר', and 'טכניקה/חומר' all compare equal."""
    s = s.replace("/", " / ")
    return _WS.sub(" ", s).strip()


NORMALIZED_LABELS = {_normalize_label_form(k): v for k, v in ALL_LABELS.items()}
# Sort longest-first so e.g. "תאריך רכישה / תרומה" matches before just "תרומה".
NORMALIZED_LABEL_ORDER = sorted(NORMALIZED_LABELS, key=len, reverse=True)

# Fields whose values are also rendered in English on a separate line (we keep both).
BILINGUAL = {"technique", "item_type", "origin", "artist", "work_title"}

FIELD_ORDER = [
    "accession_id", "accession_raw",
    "artist", "artist_en",
    "work_title", "work_title_en",
    "technique", "technique_en",
    "description",
    "item_type", "item_type_en",
    "dimensions", "years",
    "subject_narrow", "subject_broad",
    "origin", "origin_en",
    "bio_chrono", "category",
    "location", "condition", "registrar",
    "insurance_value", "donation_no", "acquisition_date",
    "donor", "notes",
    "source_pages",
]

ACCESSION_RE = re.compile(
    r"([GHEF])\s*\.?\s*([BF])\s*\.?\s*(\d{3,5})\s*(?:/\s*(\d+))?"
)


def strip_bidi(s: str) -> str:
    s = BIDI.sub("", s)
    # Bidi marks acted as visual separators; without them digits and Hebrew letters
    # collide (".1פעילות" should read ".1 פעילות"). Re-insert a space at those boundaries.
    s = re.sub(r"(\d)([֐-׿])", r"\1 \2", s)
    s = re.sub(r"([֐-׿])(\d)", r"\1 \2", s)
    return s


def normalize_accession(raw: str) -> str | None:
    m = ACCESSION_RE.search(raw)
    if not m:
        return None
    a, b, main, piece = m.groups()
    base = f"{a}-{b}-{int(main):04d}"
    return base + (f"-{int(piece)}" if piece else "")


def label_at_end(line: str) -> tuple[str, str] | None:
    """If the line ends with a known Hebrew label, return (field_key, value_before).

    Labels are matched on whitespace-collapsed form so layout-varied renderings
    (one space / two spaces / no space around '/') all map to the same key.
    """
    clean = strip_bidi(line).rstrip()
    normalized = _normalize_label_form(clean)
    for label in NORMALIZED_LABEL_ORDER:
        if normalized.endswith(label):
            key = NORMALIZED_LABELS[label]
            # Compute value by stripping the trailing N tokens that make up the label.
            label_tokens = label.split(" ")
            value_tokens = normalized.split(" ")[: -len(label_tokens)]
            value = " ".join(value_tokens).strip()
            return key, value
    return None


def parse_page(page_lines: list[str]) -> tuple[dict, str | None]:
    """Parse one page → dict of field→value plus the accession id seen on it (if any)."""
    record: dict[str, str] = {}
    accession_id: str | None = None
    accession_raw: str | None = None

    # First pass: gather labeled values; also detect English equivalent lines (left-aligned,
    # short, no Hebrew labels, immediately following a bilingual field).
    pending_en_field: str | None = None
    description_lines: list[str] = []
    in_description = False
    notes_lines: list[str] = []
    in_notes = False

    for raw_line in page_lines:
        labeled = label_at_end(raw_line)
        if labeled:
            key, val = labeled
            if key == "accession":
                accession_raw = val
                accession_id = normalize_accession(val)
                in_description = in_notes = False
                pending_en_field = None
                continue
            if key == "description":
                in_description = True
                in_notes = False
                # value on same line is usually empty; categories list follows
                if val:
                    description_lines.append(val)
                pending_en_field = None
                continue
            if key == "notes":
                in_notes = True
                in_description = False
                if val:
                    notes_lines.append(val)
                pending_en_field = None
                continue

            in_description = in_notes = False
            record[key] = val
            pending_en_field = key if key in BILINGUAL else None
            continue

        clean = strip_bidi(raw_line).strip()
        if not clean:
            pending_en_field = None
            continue

        # Skip page chrome
        if clean in {"ספר האוסף", "Accession Register", "No Image"}:
            continue
        if clean.startswith("עמוד ") and "מתוך" in clean:
            continue

        if in_description:
            description_lines.append(clean)
        elif in_notes:
            notes_lines.append(clean)
        elif pending_en_field:
            # English equivalent line — usually pure ASCII / latin
            if re.match(r"^[A-Za-z0-9'’\"().,\- /]+$", clean):
                record[f"{pending_en_field}_en"] = clean
            pending_en_field = None

    if description_lines:
        record["description"] = " | ".join(description_lines)
    if notes_lines:
        record["notes"] = " | ".join(notes_lines)
    if accession_raw:
        record["accession_raw"] = accession_raw
    if accession_id:
        record["accession_id"] = accession_id

    return record, accession_id


def merge(into: dict, src: dict) -> None:
    for k, v in src.items():
        if not v:
            continue
        if k in into and into[k]:
            if v not in into[k]:
                into[k] = f"{into[k]} | {v}"
        else:
            into[k] = v


def main() -> None:
    text = RAW.read_text()
    pages = text.split("\f")
    print(f"pages: {len(pages)}")

    records: dict[str, dict] = {}
    current_id: str | None = None
    pages_by_record: dict[str, list[int]] = {}

    for page_no, page in enumerate(pages, 1):
        lines = page.split("\n")
        parsed, found_id = parse_page(lines)
        rec_id = found_id or current_id
        if not rec_id:
            continue  # cover/blank page before first record
        current_id = rec_id
        records.setdefault(rec_id, {})
        merge(records[rec_id], parsed)
        pages_by_record.setdefault(rec_id, []).append(page_no)

    for rid, pgs in pages_by_record.items():
        records[rid]["source_pages"] = ",".join(str(p) for p in pgs)
        records[rid].setdefault("accession_id", rid)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELD_ORDER, delimiter="\t",
                           extrasaction="ignore")
        w.writeheader()
        for rid in sorted(records):
            w.writerow(records[rid])

    print(f"wrote {len(records)} records → {OUT}")


if __name__ == "__main__":
    main()
