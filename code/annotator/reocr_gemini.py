#!/usr/bin/env python3
"""Re-transcribe the printed pages from the scans with Gemini vision.

Tesseract read every page in this corpus and only 89 of 302 came back clean.
Its failures are structural, not marginal: it reads a newspaper montage
straight across the columns, so sentences from three articles interleave, and
it drops accents and long-s until the German is unsearchable. Re-running it
cannot help. A vision model reads the page as a page.

What it is asked to do, and just as importantly what it is not:

  * transcribe, never translate, never tidy. A misprint stays a misprint.
  * follow the reading order of the LAYOUT, so a two-column page comes back as
    two columns and not as alternating lines. This is the single biggest gain
    over Tesseract here.
  * mark what it cannot read as [...] rather than guessing. An invented word
    is indistinguishable from a real one downstream, and this corpus is
    evidence.
  * leave handwriting alone beyond noting it. Anything whose body is
    handwritten was routed to Transkribus by triage_pages.py; a printed page
    with a pencilled archival note reaches here, and the note is worth less
    than the risk of inventing a reading for it.

Results are written beside the corpus, NOT into it. Replacing a source pane
changes its sha256, which re-triggers the Hebrew translation of the whole
document and moves every offset in it. That is a decision to take after
reading the new text, not a side effect of producing it.

Output: data/annotator/reocr/<doc_id>/<page_no>.txt
        data/annotator/reocr/index.tsv
"""
import argparse
import csv
import hashlib
import io
import json
import random
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from google.genai import types
from PIL import Image

import llm

REPO = Path(__file__).resolve().parents[2]
DOCS = REPO / "data/annotator/docs"
SCANS = REPO / "data/recatalog"
OUT = REPO / "data/annotator/reocr"

MODEL = "gemini-3-flash-preview"
# Transcription needs the glyphs, not just the layout, so this is far larger
# than the 1400px the triage used to tell cursive from print.
MAX_EDGE = 3000

PROMPT = """Transcribe this scanned page from a German-Jewish archive.

The page may be a newspaper article or clipping, a brochure, a programme, a
typescript or a printed letter. Several unrelated clippings may be pasted on
one sheet.

RULES:

1. Follow the reading order of the LAYOUT. Transcribe each column, article or
   clipping through to its end before starting the next; never read straight
   across a multi-column page. Where one article continues past another, keep
   its text together.
2. Separate each article, clipping or distinct block with a blank line, and
   put its headline on its own line above it.
3. Transcribe exactly what is printed, including misprints, old spelling
   (daß, Muth), hyphens at line ends, and the original punctuation. Do not
   correct, modernise, translate or summarise anything.
4. Where the scan is illegible or cut off, write [...] and move on. Never
   guess a word, a name, a date or a number. A gap is usable evidence; an
   invented word is not.
5. Preserve mastheads, datelines, page numbers, bylines and photo captions —
   mark a caption by starting the line with "Bildunterschrift: ".
6. Do not transcribe handwriting. Where a handwritten note, date, stamp or
   signature appears, write [handschriftlich] on its own line in place of it.
   Printed text is the job here.
7. Preserve paragraph breaks. Do not merge paragraphs and do not add headings
   that are not on the page.

Return only the transcription. No preamble, no commentary, no explanation."""


def scan_index():
    idx = {}
    for p in SCANS.glob("*/scans/*"):
        idx.setdefault(p.name, p)
    return idx


def transcribe(path, usage, force=False):
    raw = path.read_bytes()
    key = llm.cache_key("reocr_page",
                        hashlib.sha256(raw).hexdigest() + MODEL +
                        hashlib.sha256(PROMPT.encode()).hexdigest()[:16])
    if not force:
        hit = llm.cache_get(key)
        if hit is not None:
            usage.hit()
            return hit["text"]

    im = Image.open(io.BytesIO(raw)).convert("RGB")
    if max(im.size) > MAX_EDGE:
        scale = MAX_EDGE / max(im.size)
        im = im.resize((int(im.width * scale), int(im.height * scale)))
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=92)

    delay = 2.0
    for attempt in range(5):
        try:
            resp = llm.client().models.generate_content(
                model=MODEL,
                contents=[types.Part.from_bytes(data=buf.getvalue(),
                                                mime_type="image/jpeg"),
                          PROMPT],
                config=types.GenerateContentConfig(
                    max_output_tokens=32000,
                    thinking_config=types.ThinkingConfig(thinking_level="low"),
                ),
            )
            break
        except Exception as e:
            if attempt == 4 or not llm._retryable(e):
                raise
            time.sleep(delay + random.uniform(0, 1.5))
            delay = min(delay * 2, 40)

    if usage and resp.usage_metadata:
        usage.add(resp.usage_metadata)
    finish = resp.candidates[0].finish_reason if resp.candidates else None
    if finish is not None and finish != types.FinishReason.STOP:
        raise RuntimeError(f"stopped early ({finish.name})")
    text = (resp.text or "").strip()
    llm.cache_put(key, {"text": text})
    return text


def collect(only=None):
    out = []
    for f in sorted(DOCS.glob("*.json")):
        doc = json.loads(f.read_text(encoding="utf-8"))
        if only and not any(o in doc["doc_id"] for o in only):
            continue
        for p in (doc["panes"]["source"].get("pages") or []):
            if (p.get("triage") or {}).get("engine") == "gemini":
                out.append((doc["doc_id"], p))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--docs", nargs="*")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    idx = scan_index()
    pages = collect(args.docs)
    if args.limit:
        pages = pages[:args.limit]
    usage = llm.Usage()
    rows, lock = [], __import__("threading").Lock()

    def one(item):
        doc_id, p = item
        dest = OUT / doc_id
        txt = dest / f"{p['page_no']}.txt"
        if txt.exists() and not args.force:
            return None
        img = idx.get(p.get("scan_file") or "")
        if not img:
            print(f"  {doc_id} p{p['page_no']}: no scan on disk")
            return None
        try:
            text = transcribe(img, usage, args.force)
        except Exception as e:
            print(f"  {doc_id} p{p['page_no']}: {type(e).__name__} {str(e)[:110]}")
            return None
        dest.mkdir(parents=True, exist_ok=True)
        txt.write_text(text, encoding="utf-8")
        old = p["end"] - p["start"]
        with lock:
            rows.append([doc_id, p["page_no"], p["grade"], old, len(text),
                         round(len(text) / max(1, old), 2)])
        print(f"  {doc_id:26} p{p['page_no']:<5} {p['grade']:6} "
              f"{old:6} -> {len(text):6} chars")
        return True

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        list(pool.map(one, pages))

    if rows:
        OUT.mkdir(parents=True, exist_ok=True)
        index = OUT / "index.tsv"
        new = not index.exists()
        with index.open("a", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh, delimiter="\t")
            if new:
                w.writerow(["doc_id", "page_no", "tesseract_grade",
                            "tesseract_chars", "gemini_chars", "ratio"])
            w.writerows(rows)
    print(f"\n{len(rows)} pages re-transcribed of {len(pages)} routed")
    print(f"  {usage.report()}  (Pro rates — Flash is a fraction of this)")
    print(f"  -> {OUT.relative_to(REPO)}  (not merged into the corpus)")


if __name__ == "__main__":
    main()
