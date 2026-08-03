#!/usr/bin/env python3
"""Stamp Drive full-transcript links into existing oral bundles.

Reads data/israelkorpus/drive_links.json (event_id -> Drive URL, written by
hand or by the assistant from the Drive folder listing) and sets
meta.full_text_url on every data/annotator/docs/IS_E_*__w*.json bundle.

A patch, not a rebuild: build_oral.py regenerates panes and windows, which
would orphan nothing but is slower and touches files the PI may have open.
build_oral.py reads the same mapping, so full rebuilds stay consistent.
"""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LINKS = REPO / "data/israelkorpus/drive_links.json"
DOCS = REPO / "data/annotator/docs"


def main():
    links = json.loads(LINKS.read_text())
    patched = missing = 0
    for path in sorted(DOCS.glob("IS_E_*__w*.json")):
        d = json.loads(path.read_text())
        event_id = d["meta"].get("event_id")
        url = links.get(event_id, "")
        if not url:
            missing += 1
            print(f"  ! no link for {event_id} ({path.name})")
            continue
        if d["meta"].get("full_text_url") != url:
            d["meta"]["full_text_url"] = url
            path.write_text(json.dumps(d, ensure_ascii=False, indent=1))
            patched += 1
    print(f"{patched} bundle(s) patched, {missing} without a link")


if __name__ == "__main__":
    main()
