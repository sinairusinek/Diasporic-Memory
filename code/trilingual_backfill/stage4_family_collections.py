#!/usr/bin/env python3
"""Stage 4: add EN titles to Family Collection items, derived from
archive_folders.tsv (col `artist_en`).

For each Family Collection in the DB (identifier like IL-MTFN-001-G-F-NNNN
or G-F-NNNN), find the most common `artist_en` value across its child
folder rows in archive_folders.tsv. If found AND no en-tagged title yet
exists, insert one.

Strategy:
  - Parse archive_folders.tsv: collect artist_en values per family id
    G-F-NNNN (derived from accession_id "G-F-NNNN-N").
  - Map DB identifiers ending in "-NNNN" to family ids.
  - INSERT en title for matched families with no existing en title.
"""
import csv
import re
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ARCHIVE_FOLDERS = REPO / "data" / "hecht" / "archive_folders.tsv"

IDENT_MAP_PATH = Path("/tmp/identifier_map.tsv")
TITLE_STATE_PATH = Path("/tmp/title_state.tsv")
OUT_SQL = Path("/tmp/stage4_inserts.sql")

PROP_TITLE = 1

def sql_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace("'", "''")


# Family id from accession_id:
#   "G-F-0001-1" → "G-F-0001" (folder-level row)
#   "G-F-0004"   → "G-F-0004" (family-level row, direct hit)
def family_id_from_accession(acc: str):
    parts = acc.split("-")
    if len(parts) < 3:
        return None
    return "-".join(parts[:3])


# Build: family_id → Counter of artist_en strings
family_en_artists = defaultdict(Counter)
with open(ARCHIVE_FOLDERS, newline="") as f:
    reader = csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE)
    header = next(reader)
    # Indices: 0=accession_id, 3=artist, 4=artist_en
    for row in reader:
        if len(row) < 5:
            continue
        acc = row[0].strip()
        en = row[3].strip()
        if not acc or not en:
            continue
        fid = family_id_from_accession(acc)
        if fid:
            family_en_artists[fid][en] += 1

# Identifier map → resource_id
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

# rids that already have an en-tagged title
has_en_title = set()
with open(TITLE_STATE_PATH) as f:
    for line in f:
        parts = line.rstrip("\n").split("\t", 3)
        if len(parts) < 4:
            continue
        _vid, rid, lang, _text = parts
        if lang.lower() == "en":
            has_en_title.add(int(rid))

# Build the inserts. The DB identifier is like "IL-MTFN-001-G-F-0001"
# (no trailing -NNN) for family collections. Match by suffix "-G-F-NNNN".
inserts = []
matched = 0
no_en = 0
already_has_en = 0
for ident, rid in identifier_to_rid.items():
    m = re.search(r"G-F-(\d+)$", ident)
    if not m:
        continue
    fid = f"G-F-{m.group(1)}"
    counter = family_en_artists.get(fid)
    if not counter:
        no_en += 1
        continue
    matched += 1
    if rid in has_en_title:
        already_has_en += 1
        continue
    # Most common artist_en
    en_name = counter.most_common(1)[0][0]
    en_title = f"{en_name} Family Collection"
    inserts.append(
        f"INSERT INTO value (resource_id, property_id, type, lang, value, is_public) "
        f"VALUES ({rid}, {PROP_TITLE}, 'literal', 'en', '{sql_escape(en_title)}', 1);"
    )

with open(OUT_SQL, "w") as f:
    f.write("-- Stage 4: family-collection EN titles\n")
    f.write("START TRANSACTION;\n")
    for line in inserts:
        f.write(line + "\n")
    f.write("COMMIT;\n")

print(f"Family-id (G-F-NNNN) families with archive_folders EN names: {len(family_en_artists)}")
print(f"DB family-collection identifiers matched to a family id:    {matched}")
print(f"  of which already had an EN title:                         {already_has_en}")
print(f"  no EN name in source TSV:                                 {no_en}")
print(f"Inserts queued:                                             {len(inserts)}")
print(f"Wrote: {OUT_SQL}")
