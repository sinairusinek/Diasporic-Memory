#!/usr/bin/env python3
"""Project source-pane highlights onto the Hebrew translation.

Page-level alignment from translate_he.py narrows each source highlight to the
corresponding page of the translation; Claude then locates the Hebrew rendering
of that specific passage within that page. The returned Hebrew quote is
resolved by exact string search, exactly as in prehighlight_claude.py.

Anything that cannot be located is dropped rather than approximated. Scheme
rule 4: the translation is not annotation evidence. A highlight missing from
the Hebrew pane costs the reader a visual cue; a highlight on the wrong Hebrew
sentence is a false claim about the source.

Input/Output: data/annotator/docs/*.json  (edited in place)
"""
import argparse
import json
from pathlib import Path

import llm

REPO = Path(__file__).resolve().parents[2]
DOCS = REPO / "data/annotator/docs"

SYSTEM = [{
    "type": "text",
    "text": """You are given a passage from a German (or English) source document and the
Hebrew translation of the page it appears on. Find the Hebrew text that renders
that specific passage.

Return ONLY the Hebrew substring, copied character-for-character from the
translation you were given — no quotation marks, no explanation, no preamble.

If the passage was not translated (the page is marked untranscribed), or you
cannot identify with confidence which Hebrew text corresponds to it, return
exactly: NONE

Do not paraphrase, retranslate, or reconstruct. Copy from the given Hebrew text
or return NONE. A wrong span is far worse than no span.""",
}]


def locate(text, quote):
    quote = (quote or "").strip().strip('"“”')
    if len(quote) < 6 or quote == "NONE":
        return None
    hits, i = [], text.find(quote)
    while i != -1 and len(hits) < 3:
        hits.append(i)
        i = text.find(quote, i + 1)
    return (hits[0], hits[0] + len(quote)) if len(hits) == 1 else None


def block_for(blocks, start, end):
    """The alignment block a source span falls in, if it falls in just one."""
    hits = [b for b in blocks if b["source_start"] <= start
            and end <= b["source_end"]]
    return hits[0] if len(hits) == 1 else None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--docs", nargs="*")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--strict-only", action="store_true", default=True,
                    help="project only strict highlights (default)")
    ap.add_argument("--all-tiers", dest="strict_only", action="store_false")
    args = ap.parse_args()

    files = sorted(DOCS.glob("*.json"))
    if args.docs:
        files = [f for f in files if any(d in f.stem for d in args.docs)]

    usage = llm.Usage()
    projected = dropped = 0
    for f in files:
        doc = json.loads(f.read_text(encoding="utf-8"))
        tgt = doc["panes"].get("translation")
        if not tgt:
            continue
        blocks = tgt.get("pages") or tgt.get("segments") or []
        if not blocks:
            continue
        src_text = doc["panes"]["source"]["text"]
        he_text = tgt["text"]

        kept = [h for h in doc["prehighlights"] if h["pane"] != "translation"]
        new = []
        for h in kept:
            if h["pane"] != "source":
                continue
            if args.strict_only and not h.get("strict"):
                continue
            blk = block_for(blocks, h["start"], h["end"])
            if blk is None or blk.get("grade") == "poor":
                dropped += 1
                continue
            he_page = he_text[blk["start"]:blk["end"]]
            src_page = src_text[blk["source_start"]:blk["source_end"]]
            user = (f"Passage from the source:\n{h['quote']}\n\n"
                    f"---\nSource page:\n{src_page}\n\n"
                    f"---\nHebrew translation of that page:\n{he_page}")
            answer = llm.ask(SYSTEM, user, task="project_he", usage=usage,
                             max_tokens=2000, effort="low", force=args.force)
            span = locate(he_page, answer)
            if span is None:
                dropped += 1
                continue
            s, e = blk["start"] + span[0], blk["start"] + span[1]
            new.append({**h,
                        "id": f"{h['id']}-he",
                        "pane": "translation",
                        "start": s, "end": e,
                        "quote": he_text[s:e]})
            projected += 1

        doc["prehighlights"] = kept + new
        f.write_text(json.dumps(doc, ensure_ascii=False, indent=1),
                     encoding="utf-8")
        if new or dropped:
            print(f"  {doc['doc_id']:26} {len(new):3} projected")

    print(f"{projected} highlights projected onto Hebrew, {dropped} dropped")
    print(f"  {usage.report()}")


if __name__ == "__main__":
    main()
