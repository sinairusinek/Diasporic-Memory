#!/usr/bin/env python3
"""Generate the Hebrew translation pane, page by page.

Page-by-page is not just chunking: the page is the alignment unit, so the
translation pane's block index falls out for free and a selection in either
pane resolves to the same page and the same scan.

Pages graded `poor` by build_written.py are never translated — Tesseract fails
on German cursive and shreds dense press montages, and translating that
produces fluent, confident, wrong Hebrew. They get a placeholder so the block
index still tiles the text, and the reader is sent to the facsimile.

Input/Output: data/annotator/docs/*.json  (translation pane written in place)
"""
import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import llm
from textnorm import join_pages, sha256_text

REPO = Path(__file__).resolve().parents[2]
DOCS = REPO / "data/annotator/docs"

UNTRANSLATED = "[העמוד לא תועתק באופן מהימן — ראו את הסריקה]"

SYSTEM = [{
    "type": "text",
    "text": """You translate historical German and English documents into Hebrew for a
scholarly archive of German-Jewish emigrants' post-war returns to Germany.

The source is OCR of a scanned page and is imperfect. Rules:

1. Translate into clear, readable modern Hebrew. Preserve the register of the
   original: an official municipal letter stays formal, a private letter stays
   personal, a newspaper report stays journalistic.
2. Keep proper names, place names and institutions in their conventional Hebrew
   form where one exists (Köln -> קלן, Wiesbaden -> ויסבאדן, Worms -> וורמס);
   otherwise transliterate and put the original in parentheses on first use.
3. Keep dates, numbers, file references and addresses exactly as they appear.
4. Preserve the paragraph structure of the source. Do not merge or reorder
   paragraphs, and do not add headings the source does not have.
5. Where the OCR is garbled beyond reconstruction, render what you can and mark
   the gap [...]. Never invent plausible text to bridge a gap — a visible gap is
   usable evidence, an invented sentence is not.
6. Terms that carry the source's own weight — Heimat, Vaterstadt, alte Heimat,
   Wiedergutmachung, Begegnungswoche — translate them, and give the German in
   parentheses on first occurrence so the lexeme stays visible to the reader.
7. Return only the Hebrew translation. No preamble, no notes, no explanation of
   what you did.""",
}]


def page_text(doc, page):
    return doc["panes"]["source"]["text"][page["start"]:page["end"]]


def translate_page(doc, page, usage, force):
    body = page_text(doc, page)
    if not page["translatable"] or not body.strip():
        return UNTRANSLATED
    hint = ""
    if page["grade"] == "mixed":
        hint = ("\n\nNote: this page's OCR is partly garbled (columns may be "
                "interleaved). Translate the passages that are coherent and "
                "mark the rest [...].")
    title = doc["meta"]["title"]
    user = (f"Document: {title}\n"
            f"Type: {doc['meta']['doc_type']}, {doc['meta']['date_text']}\n"
            f"Page {page['page_no']} of {doc['meta']['page_range']}."
            f"{hint}\n\n---\n{body}")
    return llm.ask(SYSTEM, user, task="translate_he", usage=usage,
                   max_tokens=16000, effort="medium", force=force)


def translate_doc(doc, usage, force, workers):
    src = doc["panes"]["source"]
    blocks = src.get("pages") or src.get("segments") or []
    if not blocks:
        return None

    if src.get("segments"):
        # Oral excerpts have no pages; the speaker turn is the unit instead.
        units = [{"start": s["start"], "end": s["end"], "page_no": s["n"],
                  "grade": "clean", "translatable": True} for s in blocks]
    else:
        units = blocks

    with ThreadPoolExecutor(max_workers=workers) as pool:
        parts = list(pool.map(
            lambda u: translate_page(doc, u, usage, force), units))

    text, spans = join_pages([(u["page_no"], p) for u, p in zip(units, parts)])
    index = [{"page_no": u["page_no"], "start": s["start"], "end": s["end"],
              "source_start": u["start"], "source_end": u["end"],
              "grade": u.get("grade", "clean")}
             for u, s in zip(units, spans)]

    return {
        "pane": "translation", "lang": "he", "dir": "rtl",
        "text": text, "sha256": sha256_text(text),
        "pages": index if src.get("pages") else [],
        "segments": index if src.get("segments") else [],
        "align": [{"src": [u["start"], u["end"]], "tgt": [s["start"], s["end"]]}
                  for u, s in zip(units, spans)],
        "model": llm.MODEL,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_sha256": src["sha256"],
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--docs", nargs="*", help="doc_id substrings to limit to")
    ap.add_argument("--kind", choices=["written", "oral"])
    ap.add_argument("--limit", type=int)
    ap.add_argument("--force", action="store_true",
                    help="re-translate even if the source text is unchanged")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    files = sorted(DOCS.glob("*.json"))
    if args.docs:
        files = [f for f in files if any(d in f.stem for d in args.docs)]

    usage = llm.Usage()
    done = skipped = 0
    for f in files:
        doc = json.loads(f.read_text(encoding="utf-8"))
        if args.kind and doc["kind"] != args.kind:
            continue
        prev = doc["panes"].get("translation")
        # Hash-gated: an unchanged source is a no-op. This is what keeps
        # annotation offsets from drifting on every rebuild.
        if prev and not args.force and \
                prev.get("source_sha256") == doc["panes"]["source"]["sha256"]:
            skipped += 1
            continue
        if args.limit and done >= args.limit:
            break

        pane = translate_doc(doc, usage, args.force, args.workers)
        if pane is None:
            continue
        doc["panes"]["translation"] = pane
        f.write_text(json.dumps(doc, ensure_ascii=False, indent=1),
                     encoding="utf-8")
        done += 1
        print(f"  {doc['doc_id']:26} {len(pane['text']):7}ch he   "
              f"({len(pane.get('pages') or pane.get('segments'))} blocks)")

    print(f"{done} translated, {skipped} already current")
    print(f"  {usage.report()}")


if __name__ == "__main__":
    main()
