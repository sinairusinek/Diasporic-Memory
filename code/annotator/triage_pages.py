#!/usr/bin/env python3
"""Decide, page by page, which engine should transcribe it.

Tesseract was used for everything, and it is only good on clean print: 213 of
302 pages came back graded mixed or poor. Re-running the same engine will not
help. The two alternatives have different strengths, so the page has to be
looked at before it can be routed:

  * Gemini vision reads print, typescript, multi-column newspaper montages and
    tables far better than Tesseract, and reads them in the right order;
  * Transkribus HTR is the only thing here that reads German cursive, which
    Tesseract does not attempt and which Gemini transcribes fluently and
    wrongly -- the worst failure mode of the three, because it looks right.

The model is asked only what it SEES. Routing is decided in code below, so the
policy is one readable function rather than a paragraph of prompt, and can be
changed without re-paying for the pass.

Output: data/annotator/page_triage.tsv, and a `triage` block on each page in
        data/annotator/docs/*.json
"""
import argparse
import csv
import hashlib
import io
import json
import random
import time
from pathlib import Path

from google.genai import types
from PIL import Image

import llm

REPO = Path(__file__).resolve().parents[2]
DOCS = REPO / "data/annotator/docs"
SCANS = REPO / "data/recatalog"
OUT = REPO / "data/annotator/page_triage.tsv"

MODEL = "gemini-3-flash-preview"
# Enough to tell cursive from print and count columns. The page is not being
# read here, only looked at, and full-resolution scans would cost several times
# more for no better answer.
MAX_EDGE = 1400

PROMPT = """You are looking at one scanned page from a German-Jewish archive, to decide
which transcription engine should be pointed at it. Do not transcribe it.

Report what you see:

script      What the text on the page physically is:
              print        — typeset, printed (newspaper, book, brochure)
              typescript   — typewritten
              handwriting  — handwritten in any hand, including German cursive
                             (Kurrent/Sütterlin) and Hebrew
              mixed        — a substantial amount of two or more of the above,
                             e.g. a printed form filled in by hand, or a
                             printed letter with a handwritten annotation that
                             carries content
              none         — no readable text at all (photograph, blank page,
                             musical notation, a map with no legend)

hand_kind   Only if any handwriting is present: "kurrent" for old German
            cursive, "latin" for modern Latin longhand, "hebrew", or "" if
            there is none.

layout      single | two-column | multi-column | montage (several clippings
            pasted on one sheet) | form | table | mostly-image

legibility  good | faded | low-contrast | skewed | bleed-through | damaged

text_amount none | sparse | moderate | dense

issues      A list, any of: marginalia, stamp, handwritten-annotation,
            photo-caption, musical-notation, map, ruled-lines, tight-gutter,
            page-curl, or [] if none apply.

note        One short English clause on anything that would trip a
            transcriber, e.g. "two clippings overlap at the fold".

Be careful with `script`. A page of dense German cursive and a page of faded
print look similar in thumbnail, and they route to different engines: calling
cursive "print" produces confident nonsense downstream.

Return one JSON object with exactly those keys, plus "confidence" 0.0-1.0."""


def scan_index():
    """Every scan on disk by basename — page records store a bare filename."""
    idx = {}
    for p in SCANS.glob("*/scans/*"):
        idx.setdefault(p.name, p)
    return idx


def look(path, usage, force=False):
    """One vision call, cached on the image bytes so a re-run is free."""
    raw = path.read_bytes()
    key = llm.cache_key("triage_page", hashlib.sha256(raw).hexdigest() + MODEL)
    if not force:
        hit = llm.cache_get(key)
        if hit is not None:
            usage.hit()
            return hit["data"]

    im = Image.open(io.BytesIO(raw))
    im = im.convert("RGB")
    if max(im.size) > MAX_EDGE:
        scale = MAX_EDGE / max(im.size)
        im = im.resize((int(im.width * scale), int(im.height * scale)))
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=88)

    delay = 2.0
    for attempt in range(5):
        try:
            resp = llm.client().models.generate_content(
                model=MODEL,
                contents=[
                    types.Part.from_bytes(data=buf.getvalue(),
                                          mime_type="image/jpeg"),
                    PROMPT,
                ],
                config=types.GenerateContentConfig(
                    max_output_tokens=2000,
                    thinking_config=types.ThinkingConfig(thinking_level="low"),
                    response_mime_type="application/json",
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

    try:
        data = json.loads(resp.text or "{}")
    except json.JSONDecodeError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    llm.cache_put(key, {"data": data})
    return data


def route(seen, page):
    """Which engine should read this page, and why.

    Asymmetric on purpose: cursive goes to Transkribus even when most of the
    page is print, because Gemini transcribes German cursive fluently and
    wrongly, and a confident invented reading is worse than visible garbage.

    But `mixed` alone is not enough to send a page to HTR. Nearly every clipping
    in this archive carries a pencilled date and an accession number, so the
    first pass routed the whole Cologne press file to Transkribus on the
    strength of an archivist's marginal note. Where the body is print and the
    only hand is annotation, the page reads best on Gemini — losing a pencilled
    date costs little, and losing the article costs the document.
    """
    script = (seen.get("script") or "").lower()
    amount = (seen.get("text_amount") or "").lower()
    hand = (seen.get("hand_kind") or "").lower()
    layout = (seen.get("layout") or "").lower()
    issues = {str(i).lower() for i in (seen.get("issues") or [])}
    grade = page.get("grade", "mixed")
    conf = page.get("ocr_conf")

    if script == "none" or amount == "none":
        return "none", "no readable text on the page"
    if script == "handwriting":
        return "transkribus", f"handwritten ({hand or 'unspecified'})"
    if script == "mixed":
        # A page whose body is printed reads best on Gemini even when there is
        # ink on it. Two exceptions, where the hand IS the content: a printed
        # form filled in by hand, and Kurrent that is not merely a margin note.
        if layout == "form":
            return "transkribus", "printed form completed by hand"
        if hand == "kurrent" and not (
            "handwritten-annotation" in issues or "marginalia" in issues
        ):
            return "transkribus", "German cursive carrying content"
        return "gemini", "printed body with handwriting on it"
    if page.get("ocr_engine") == "transkribus":
        return "keep", "already transcribed by Transkribus"
    if grade == "clean" and (conf is None or conf >= 0.85):
        return "keep", f"clean print, Tesseract confidence {conf}"
    return "gemini", f"{script or 'print'}, graded {grade}"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--docs", nargs="*")
    ap.add_argument("--limit", type=int, help="stop after N pages")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    idx = scan_index()
    usage = llm.Usage()
    rows = []
    files = sorted(DOCS.glob("*.json"))
    if args.docs:
        files = [f for f in files if any(d in f.stem for d in args.docs)]

    for f in files:
        doc = json.loads(f.read_text(encoding="utf-8"))
        pages = doc["panes"]["source"].get("pages") or []
        if not pages:
            continue
        changed = False
        for p in pages:
            if args.limit and len(rows) >= args.limit:
                break
            path = idx.get(p.get("scan_file") or "")
            if not path:
                rows.append([doc["doc_id"], p["page_no"], p["grade"], "", "",
                             "", "", "manual", "no scan on disk", ""])
                continue
            seen = look(path, usage, args.force)
            engine, why = route(seen, p)
            p["triage"] = {
                "engine": engine, "why": why,
                "script": seen.get("script", ""),
                "hand_kind": seen.get("hand_kind", ""),
                "layout": seen.get("layout", ""),
                "legibility": seen.get("legibility", ""),
                "text_amount": seen.get("text_amount", ""),
                "issues": seen.get("issues", []),
                "note": str(seen.get("note", ""))[:160],
                "confidence": seen.get("confidence", 0),
            }
            changed = True
            rows.append([
                doc["doc_id"], p["page_no"], p["grade"], seen.get("script", ""),
                seen.get("hand_kind", ""), seen.get("layout", ""),
                seen.get("legibility", ""), engine, why,
                str(seen.get("note", ""))[:160],
            ])
        if changed:
            f.write_text(json.dumps(doc, ensure_ascii=False, indent=1),
                         encoding="utf-8")
        if args.limit and len(rows) >= args.limit:
            break

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["doc_id", "page_no", "tesseract_grade", "script",
                    "hand_kind", "layout", "legibility", "route", "why",
                    "note"])
        w.writerows(rows)

    tally = {}
    for r in rows:
        tally[r[7]] = tally.get(r[7], 0) + 1
    print(f"{len(rows)} pages triaged -> {OUT.relative_to(REPO)}")
    for k in ("gemini", "transkribus", "keep", "none", "manual"):
        if tally.get(k):
            print(f"  {k:12} {tally[k]:4}")
    # Usage.report() prices at Gemini 3 Pro list rates; this pass runs on
    # Flash, so treat the figure as a ceiling rather than the bill.
    print(f"  {usage.report()}  (Pro rates — Flash is a fraction of this)")


if __name__ == "__main__":
    main()
