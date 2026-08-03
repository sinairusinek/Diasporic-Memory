#!/usr/bin/env python3
"""Replace the Tesseract source text with the re-transcribed pages.

reocr_gemini.py and transkribus_upload.py wrote their results beside the corpus
rather than into it, so that the new text could be read before anything was
committed to. This is the step that commits.

It is not additive, and three things downstream of the source pane stop being
true the moment a page changes:

  * the Hebrew translation. Its `source_sha256` will no longer match, which is
    exactly the gate translate_he.py uses — the affected documents will
    re-translate on the next run and the rest will not.
  * the pre-highlights. Their offsets point into the old text; at best they
    would move, at worst they would land mid-word in unrelated prose. They are
    dropped for changed documents, to be regenerated.
  * the page regions. Same reason, plus region_overrides.tsv records absolute
    offsets, so those need re-deriving too.

Dropping them is the honest option. Keeping stale spans would leave marks that
look authoritative and point at the wrong words.

Pages with no new transcription keep the text they had, so a document is only
disturbed to the extent it was actually re-read.

  python code/annotator/merge_reocr.py --dry-run
  python code/annotator/merge_reocr.py --skip-hebrew   # hold back one model
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from textnorm import join_pages, sha256_text

REPO = Path(__file__).resolve().parents[2]
DOCS = REPO / "data/annotator/docs"
REOCR = REPO / "data/annotator/reocr"
HTR = REPO / "data/transkribus/annotator"


def new_text_for(doc_id, page_no):
    """The re-transcription of one page, and where it came from."""
    g = REOCR / doc_id / f"{page_no}.txt"
    t = HTR / doc_id / f"{page_no}.txt"
    if t.exists():
        meta = HTR / doc_id / f"{page_no}.json"
        model = ""
        if meta.exists():
            model = json.loads(meta.read_text(encoding="utf-8")).get("model", "")
        return t.read_text(encoding="utf-8"), "transkribus", model
    if g.exists():
        return g.read_text(encoding="utf-8"), "gemini", "gemini-3-flash-preview"
    return None, None, None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--docs", nargs="*")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-hebrew", action="store_true",
                    help="leave pages transcribed by the Hebrew HTR model alone")
    args = ap.parse_args()

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    changed_docs = 0
    changed_pages = 0
    dropped_ph = dropped_rg = 0
    shrank = []

    for f in sorted(DOCS.glob("*.json")):
        doc = json.loads(f.read_text(encoding="utf-8"))
        if args.docs and not any(d in doc["doc_id"] for d in args.docs):
            continue
        src = doc["panes"]["source"]
        pages = src.get("pages") or []
        if not pages:
            continue

        raw, touched = [], 0
        for p in pages:
            text, engine, model = new_text_for(doc["doc_id"], p["page_no"])
            old_len = p["end"] - p["start"]
            if text is None or (args.skip_hebrew and "Hebrew" in (model or "")):
                raw.append((p["page_no"], src["text"][p["start"]:p["end"]]))
                continue
            if len(text.strip()) == 0 and old_len > 0:
                # Never trade text for nothing: a page that came back empty
                # keeps what it had, whatever the triage said.
                raw.append((p["page_no"], src["text"][p["start"]:p["end"]]))
                continue
            raw.append((p["page_no"], text))
            touched += 1
            if old_len and len(text) < old_len * 0.5:
                shrank.append((doc["doc_id"], p["page_no"], old_len, len(text),
                               model))
            p["ocr_engine"] = engine
            p["ocr_model"] = model
            p["ocr_conf"] = None
            p["retranscribed_at"] = now
            p["grade"] = "clean" if engine == "gemini" else p["grade"]
            # `translatable` was set from the Tesseract grade, and a page
            # graded poor then is precisely the page most worth re-reading now.
            # Leaving the flag alone sent 47 freshly-transcribed pages to the
            # "not reliably transcribed" placeholder instead of to Hebrew.
            p["translatable"] = len(text.strip()) > 40

        if not touched:
            continue
        changed_docs += 1
        changed_pages += touched

        text, spans = join_pages(raw)
        for p, s in zip(pages, spans):
            p["start"], p["end"] = s["start"], s["end"]
        old_sha = src["sha256"]
        print(f"  {doc['doc_id']:26} {touched:3}/{len(pages)} pages  "
              f"{len(src['text']):7} -> {len(text):7} chars")
        if args.dry_run:
            continue

        src["text"] = text
        src["sha256"] = sha256_text(text)
        # Everything anchored to the old offsets is now wrong, not merely stale.
        dropped_ph += len(doc.get("prehighlights") or [])
        dropped_rg += len(doc.get("regions") or [])
        doc["prehighlights"] = []
        doc.pop("regions", None)
        doc["source_retranscribed_at"] = now
        doc["previous_source_sha256"] = old_sha
        f.write_text(json.dumps(doc, ensure_ascii=False, indent=1),
                     encoding="utf-8")

    print(f"\n{changed_pages} pages merged across {changed_docs} documents")
    if shrank:
        print(f"  {len(shrank)} page(s) lost more than half their length:")
        for d, p, a, b, m in shrank[:12]:
            print(f"    {d:24} p{p:<5} {a:5} -> {b:<5} {m}")
    if not args.dry_run:
        print(f"  dropped {dropped_ph} pre-highlights and {dropped_rg} regions "
              f"— both need re-running")
        print("  next: translate_he.py (changed docs only), then "
              "page_regions.py, then prehighlight_claude.py")
    else:
        print("  dry run — nothing written")


if __name__ == "__main__":
    main()
