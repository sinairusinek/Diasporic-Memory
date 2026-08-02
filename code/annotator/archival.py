#!/usr/bin/env python3
"""Where a document physically sits: archive, collection, folder.

A bundle carries a bare folder id — `0276-6`, meaning the sixth folder of
accession G-F-0276. That is a locator, not a context: on its own it says
nothing about which archive holds the paper, whose papers they are, or what the
folder was called when it was catalogued. Annotating out of that context means
reading a letter with no idea whose life it belongs to.

Names come from the Tefen accession register (data/hecht/archive_folders.tsv),
`artist` being the collection and `work_title` the folder. Both are Hebrew and
stay Hebrew: `work_title_en` is empty for every folder in this corpus, so an
English title here would be ours rather than the archive's.

Not every folder has a register card. G-F-0113 was accessioned as a collection
and never itemised, so its subfolders resolve to a collection name and no
folder title — which is the true state of the catalogue, and better shown than
papered over.
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path
from typing import Dict, Optional

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "data" / "hecht" / "archive_folders.tsv"

# The holding institution for every G-F folder in this corpus.
AGSJI = "Archive for the German-speaking Jewry in Israel (AGSJI)"
AGSJI_SHORT = "AGSJI"

# The oral half of the corpus is not held at Tefen at all.
ISRAELKORPUS = {
    "archive": "Israelkorpus (Anne Betten) — Datenbank für Gesprochenes "
               "Deutsch, IDS Mannheim",
    "archive_short": "Israelkorpus / DGD",
    "collection": "IS — Emigrantendeutsch in Israel",
    "collection_id": "IS",
    "folder_title": "",
    "folder_id": "",
    "folder_ref": "",
    "title_lang": "",
}

_register = None  # type: Optional[Dict[str, dict]]


def register():
    global _register
    if _register is None:
        if not REGISTER.exists():
            print(f"  ! no accession register at {REGISTER} — "
                  f"documents will show folder ids only", file=sys.stderr)
            _register = {}
        else:
            with REGISTER.open(encoding="utf-8", newline="") as fh:
                _register = {
                    r["accession_id"]: r
                    for r in csv.DictReader(fh, delimiter="\t")
                    if r.get("accession_id")
                }
    return _register


def reference_code(collection: str, sub: str) -> str:
    """The folder's ISAD(G) reference, as the catalogue writes it.

    Formulaic — G-F-0047-2 is IL-MTFN-001-G-F-0047-002 — so it is derived
    rather than looked up, and is therefore available even for the folders the
    register never carded.
    """
    return f"IL-MTFN-001-G-F-{collection}-{int(sub):03d}"


def context_for(folder: str, event_id: str = "") -> dict:
    """Resolve a bundle's `meta.folder` into displayable archival context."""
    if folder == "israelkorpus":
        return {**ISRAELKORPUS,
                "folder_id": event_id,
                "folder_ref": event_id}

    m = re.fullmatch(r"(\d{4})-(\d+)", folder)
    if not m:
        return {"archive": AGSJI, "archive_short": AGSJI_SHORT,
                "collection": "", "collection_id": "", "folder_title": "",
                "folder_id": folder, "folder_ref": "", "title_lang": ""}

    coll, sub = m.group(1), m.group(2)
    reg = register()
    row = reg.get(f"G-F-{coll}-{sub}") or {}
    parent = reg.get(f"G-F-{coll}") or {}
    # A carded folder names its own collection; an uncarded one borrows the
    # collection's card, which is the only place the name survives.
    collection = (row.get("artist") or parent.get("artist") or "").strip()
    folder_title = (row.get("work_title") or "").strip()

    return {
        "archive": AGSJI,
        "archive_short": AGSJI_SHORT,
        "collection": collection,
        "collection_id": f"G-F-{coll}",
        "folder_title": folder_title,
        "folder_id": f"G-F-{coll}-{sub}",
        "folder_ref": reference_code(coll, sub),
        # The register is Hebrew throughout; the panes need to know so they can
        # set direction rather than guess it.
        "title_lang": "he" if (collection or folder_title) else "",
    }


if __name__ == "__main__":
    for f in sys.argv[1:] or ["0047-2", "0113-41", "0185-2", "0276-6",
                              "0422-3", "0444-3", "israelkorpus"]:
        ctx = context_for(f, event_id="IS_E_00127")
        print(f"{f:14} {ctx['archive_short']:18} {ctx['collection_id']:10} "
              f"{ctx['collection']}  /  {ctx['folder_title'] or '—'}")
