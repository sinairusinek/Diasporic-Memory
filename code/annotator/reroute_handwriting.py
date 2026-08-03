#!/usr/bin/env python3
"""Send to Transkribus the pages Gemini turned out to be unable to read.

triage_pages.py decides from a thumbnail, and on one distinction it is not
reliable: a page of printed letterhead with a handwritten letter under it looks
like the same `mixed` as a printed article with a pencilled date on it. The
first needs HTR and the second does not, and after the routing rule was
tightened, ten of the first kind were sent to Gemini.

Gemini's own output settles it. It was told to write [handschriftlich] rather
than transcribe a hand, so a page that comes back as little else is a page
whose content nothing has read. That is a measurement rather than a guess,
which makes it a better basis for the routing than the thumbnail was.

Run after reocr_gemini.py, then re-run transkribus_upload.py to pick up the
pages this moves.
"""
import argparse
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DOCS = REPO / "data/annotator/docs"
REOCR = REPO / "data/annotator/reocr"

# Below this much printed text, whatever else is on the page, the page is its
# handwriting. Set from the observed split: the pages that need HTR come back
# with 0-281 characters of print, the ones that do not run to thousands.
PRINT_FLOOR = 400


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--floor", type=int, default=PRINT_FLOOR)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    moved = 0
    for f in sorted(DOCS.glob("*.json")):
        doc = json.loads(f.read_text(encoding="utf-8"))
        changed = False
        for p in (doc["panes"]["source"].get("pages") or []):
            t = p.get("triage") or {}
            if t.get("engine") != "gemini":
                continue
            out = REOCR / doc["doc_id"] / f"{p['page_no']}.txt"
            if not out.exists():
                continue
            text = out.read_text(encoding="utf-8")
            if "[handschriftlich]" not in text:
                continue
            rest = re.sub(r"\[handschriftlich\]", "", text).strip()
            if len(rest) >= args.floor:
                continue
            print(f"  {doc['doc_id']:24} p{p['page_no']:<5} "
                  f"{len(rest):4} chars of print -> transkribus "
                  f"({t.get('hand_kind') or 'hand unrecorded'})")
            moved += 1
            if args.dry_run:
                continue
            t["engine"] = "transkribus"
            t["why"] = (f"Gemini returned only {len(rest)} chars of print; "
                        "the page is its handwriting")
            t["rerouted_from"] = "gemini"
            p["triage"] = t
            changed = True
        if changed and not args.dry_run:
            f.write_text(json.dumps(doc, ensure_ascii=False, indent=1),
                         encoding="utf-8")

    print(f"\n{moved} page(s) rerouted to Transkribus"
          + (" (dry run, nothing written)" if args.dry_run else ""))


if __name__ == "__main__":
    main()
