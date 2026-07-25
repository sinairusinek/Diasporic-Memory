#!/usr/bin/env python3
"""Stage 3b: backfill Folder dcterms:description from Subseries Records TSV
and split bilingual titles into he/en tagged values.

Reads:
  - /tmp/identifier_map.tsv       value→resource_id
  - /tmp/desc_state.tsv           resource_id, lang (for dcterms:description)
  - /tmp/title_state.tsv          value_id, resource_id, lang, value (for dcterms:title)
  - data/Subseries Records2024-12-13.tsv
      col 0 = identifier
      col 6 = bilingual title (245$a10 כותרת)
      col 7 = German Summary
      col 8 = English Summary
      col 9 = HE description part 1
      col 10 = HE description part 2

Writes:
  - /tmp/stage3_inserts.sql

Title splitting strategy:
  Bilingual title like "Asch Bruno, אש ברונו 1890-1940"
  → english = text before first Hebrew char (strip trailing comma/space)
  → hebrew  = text from first Hebrew char onward
  If only Hebrew → english = None
  If only Latin  → hebrew = None
"""
import csv
import re
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SUBSERIES_TSV = REPO / "data" / "Subseries Records2024-12-13.tsv"

IDENT_MAP_PATH = Path("/tmp/identifier_map.tsv")
DESC_STATE_PATH = Path("/tmp/desc_state.tsv")
TITLE_STATE_PATH = Path("/tmp/title_state.tsv")
OUT_SQL = Path("/tmp/stage3_inserts.sql")

PROP_TITLE = 1
PROP_DESC = 4

HEBREW_RE = re.compile(r"[֐-׿]")
LATIN_RE = re.compile(r"[A-Za-z]")


def sql_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace("'", "''")


def is_meaningful(s: str) -> bool:
    if not s:
        return False
    s = s.strip()
    if len(s) < 3:
        return False
    return s.lower() not in {"n/a", "na", "none", "null", "tbd", "pending", "-"}


def split_bilingual_title(title: str):
    """Return (english_part, hebrew_part). Either may be None."""
    title = title.strip()
    if not title:
        return (None, None)
    m = HEBREW_RE.search(title)
    has_hebrew = m is not None
    has_latin = LATIN_RE.search(title) is not None
    if has_hebrew and not has_latin:
        return (None, title)
    if has_latin and not has_hebrew:
        return (title, None)
    if not has_hebrew and not has_latin:
        return (None, None)
    # Mixed: split at first Hebrew char.
    en_part = title[: m.start()].rstrip(" ,-:;\t")
    he_part = title[m.start():].lstrip(" ,-:;\t")
    if not en_part:
        en_part = None
    if not he_part:
        he_part = None
    return (en_part, he_part)


# Load identifier map
identifier_to_rid = {}
with open(IDENT_MAP_PATH) as f:
    for line in f:
        parts = line.rstrip("\n").split("\t", 1)
        if len(parts) != 2:
            continue
        ident, rid = parts[0].strip(), parts[1]
        if ident in ("", "NULL"):
            continue
        identifier_to_rid[ident] = int(rid)

# Load current description langs per resource
desc_langs = defaultdict(set)
with open(DESC_STATE_PATH) as f:
    for line in f:
        parts = line.rstrip("\n").split("\t")
        rid = int(parts[0])
        lang = (parts[1] if len(parts) > 1 else "").lower()
        desc_langs[rid].add(lang)

# Load current titles per resource (with their value_ids)
title_rows = defaultdict(list)  # rid → list of (value_id, lang, text)
with open(TITLE_STATE_PATH) as f:
    for line in f:
        parts = line.rstrip("\n").split("\t", 3)
        if len(parts) < 4:
            continue
        vid, rid, lang, text = parts
        title_rows[int(rid)].append((int(vid), lang.lower(), text))


stats = {"matched": 0, "unmatched": 0,
         "desc_inserted": {"he": 0, "de": 0, "en": 0},
         "title_split_inserted_en": 0, "title_split_relabeled_he": 0,
         "title_split_skipped": 0}

inserts = []
updates = []

with open(SUBSERIES_TSV, newline="") as f:
    reader = csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE)
    rows = list(reader)

# Skip first two rows (header + comments row)
for row in rows[2:]:
    if len(row) < 11:
        continue
    ident = row[0].strip()
    if not ident:
        continue
    rid = identifier_to_rid.get(ident)
    if not rid:
        stats["unmatched"] += 1
        continue
    stats["matched"] += 1

    # --- DESCRIPTIONS ---
    he_parts = [p.strip() for p in (row[9], row[10]) if is_meaningful(p)]
    he_desc = "\n\n".join(he_parts) if he_parts else None
    de_desc = row[7].strip() if is_meaningful(row[7]) else None
    en_desc = row[8].strip() if is_meaningful(row[8]) else None

    present = desc_langs.get(rid, set())
    for lang, text in (("he", he_desc), ("de", de_desc), ("en", en_desc)):
        if not text or lang in present:
            continue
        inserts.append(
            f"INSERT INTO value (resource_id, property_id, type, lang, value, is_public) "
            f"VALUES ({rid}, {PROP_DESC}, 'literal', '{lang}', '{sql_escape(text)}', 1);"
        )
        stats["desc_inserted"][lang] += 1
        present.add(lang)
    desc_langs[rid] = present

    # --- TITLES ---
    bilingual = row[6].strip()
    if not bilingual:
        continue
    en_part, he_part = split_bilingual_title(bilingual)

    existing_titles = title_rows.get(rid, [])
    # If we already have an EN title for this rid, skip.
    has_en = any(lang == "en" for (_vid, lang, _t) in existing_titles)
    has_he = any(lang == "he" for (_vid, lang, _t) in existing_titles)

    # Find the untagged title that matches the bilingual string, to retag as 'he'
    # (so the bilingual mess doesn't show in every locale).
    untagged_matching = [
        (vid, t) for (vid, lang, t) in existing_titles
        if lang == "" and t.strip() == bilingual
    ]

    if en_part and not has_en:
        inserts.append(
            f"INSERT INTO value (resource_id, property_id, type, lang, value, is_public) "
            f"VALUES ({rid}, {PROP_TITLE}, 'literal', 'en', '{sql_escape(en_part)}', 1);"
        )
        stats["title_split_inserted_en"] += 1

    if he_part and untagged_matching and not has_he:
        # Re-label the existing untagged bilingual as he, replacing value with the
        # hebrew-only part so EN locale (which renders untagged neutrally and our
        # new EN-tagged title) doesn't get the mixed string.
        vid = untagged_matching[0][0]
        updates.append(
            f"UPDATE value SET lang='he', value='{sql_escape(he_part)}' WHERE id={vid};"
        )
        stats["title_split_relabeled_he"] += 1
    elif he_part and not has_he and not untagged_matching:
        # No bilingual-untagged title to relabel; insert a he-tagged title.
        inserts.append(
            f"INSERT INTO value (resource_id, property_id, type, lang, value, is_public) "
            f"VALUES ({rid}, {PROP_TITLE}, 'literal', 'he', '{sql_escape(he_part)}', 1);"
        )
        stats["title_split_relabeled_he"] += 1
    else:
        stats["title_split_skipped"] += 1


with open(OUT_SQL, "w") as f:
    f.write("-- Stage 3: Folder descriptions + bilingual title split\n")
    f.write("START TRANSACTION;\n")
    for line in updates:
        f.write(line + "\n")
    for line in inserts:
        f.write(line + "\n")
    f.write("COMMIT;\n")

print(f"Matched Subseries rows:    {stats['matched']}")
print(f"Unmatched identifiers:     {stats['unmatched']}")
print(f"Descriptions inserted:     {stats['desc_inserted']}")
print(f"Title splits inserted en:  {stats['title_split_inserted_en']}")
print(f"Title splits relabel he:   {stats['title_split_relabeled_he']}")
print(f"Title splits skipped:      {stats['title_split_skipped']}")
print(f"SQL statements: {len(updates)} UPDATEs + {len(inserts)} INSERTs")
print(f"Wrote: {OUT_SQL}")
