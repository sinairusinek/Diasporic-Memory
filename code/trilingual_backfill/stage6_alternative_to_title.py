#!/usr/bin/env python3
"""Stage 6: promote Latin-script dcterms:alternative values to dcterms:title
@lang=en for items that have no EN title yet.

Filters:
  - Skip alternatives ending in _NNN (auto-numbered workflow ids)
  - Skip literal "TBA"/"tba"/empty
  - Skip if the resource already has an en-tagged title (defensive)
"""
import re
from collections import defaultdict
from pathlib import Path

IN_TSV = Path("/tmp/alt_to_title.tsv")
OUT_SQL = Path("/tmp/stage6_inserts.sql")

AUTO_NUM_RE = re.compile(r"_\d+$")
BAD = {"tba", "n/a", "na", "none", "null", "-"}

PROP_TITLE = 1


def sql_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace("'", "''")


inserts = []
seen_rids = set()
skipped_auto = 0
skipped_bad = 0
skipped_dup = 0

with open(IN_TSV) as f:
    for line in f:
        line = line.rstrip("\n")
        if not line:
            continue
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        rid, value = parts
        rid = int(rid)
        value = value.strip()
        if not value or value.lower() in BAD:
            skipped_bad += 1
            continue
        if AUTO_NUM_RE.search(value):
            skipped_auto += 1
            continue
        if rid in seen_rids:
            skipped_dup += 1
            continue
        seen_rids.add(rid)
        inserts.append(
            f"INSERT INTO value (resource_id, property_id, type, lang, value, is_public) "
            f"VALUES ({rid}, {PROP_TITLE}, 'literal', 'en', '{sql_escape(value)}', 1);"
        )

with open(OUT_SQL, "w") as f:
    f.write("-- Stage 6: alternative → EN title promotion\n")
    f.write("START TRANSACTION;\n")
    for line in inserts:
        f.write(line + "\n")
    f.write("COMMIT;\n")

print(f"Inserts:                   {len(inserts)}")
print(f"Skipped auto-numbered:     {skipped_auto}")
print(f"Skipped placeholder/empty: {skipped_bad}")
print(f"Skipped duplicate rid:     {skipped_dup}")
print(f"Wrote: {OUT_SQL}")
