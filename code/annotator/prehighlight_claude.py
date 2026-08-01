#!/usr/bin/env python3
"""Claude pre-highlights: the passages that carry each document's rationale.

The keyword pass finds explicit lexemes. This finds the passages the lexical
vocabulary cannot — a return described without ever using "Rückkehr", a refusal
articulated through circumlocution. That is also exactly why it is dangerous:
a model asked to find Heimat will find Heimat everywhere. Three guards:

  * the prompt carries the project's no-forced-framing rule and the scheme's
    T3.1 restriction verbatim;
  * returned quotes are resolved to offsets by EXACT string search — model
    reported offsets are never trusted, and a quote that does not match, or
    matches in more than one place, is dropped;
  * everything below 0.8 confidence is emitted as non-strict and rendered in a
    layer the app keeps off by default.

Input/Output: data/annotator/docs/*.json  (edited in place)
"""
import argparse
import json
import re
from pathlib import Path

import llm

REPO = Path(__file__).resolve().parents[2]
DOCS = REPO / "data/annotator/docs"
SCHEME = REPO / "annotation_scheme_return_spans.md"

# Only these may be assigned; they are the T-groups the visit corpus turns on.
CATEGORIES = {
    "T1.2": "visit — a bounded stay, return ticket assumed",
    "T1.4": "refusal — the decision NOT to go, articulated as such",
    "T1.5": "deliberation — weighing, hesitating, delaying",
    "T2.1": "municipal-invitation — Besuchsprogramm / Begegnungswoche",
    "T3.1": "heimat-claim — the place named as home",
    "T3.3": "ruin-and-rebuilding — destroyed, rebuilt, unrecognisable",
    "T3.4": "absence — what is NOT there: no relatives, no houses, no graves",
    "T4.1": "reconciliation — Versöhnung, gesture, outstretched hands",
    "T4.6": "unforgiving-formula — we forgive, but we cannot forget",
    "T4.7": "encounter — face-to-face meeting with Germans",
    "T7.5": "emotion-register — bitterness, dread, joy, explicit mixture",
}

SYSTEM = [{
    "type": "text",
    "text": """You mark passages in historical documents for a scholarly archive on the
post-war return visits of German-Jewish emigrants to Germany.

You are given a document's OCR text and the archivist's one-line rationale for
why the document is relevant. Find the passages that actually carry that
rationale, and assign each one a category.

Categories (use only these ids):
""" + "\n".join(f"  {k}  {v}" for k, v in CATEGORIES.items()) + """

RULES — these override any instinct to be comprehensive:

1. Apply T3.1 heimat-claim ONLY where an explicit Heimat / Vaterstadt / alte
   Heimat / מולדת lexeme or an unambiguous equivalent is present, and the place
   is being named as home. Atmosphere, nostalgia, and mere place-naming are NOT
   enough. A passage that merely mentions a German city is not a heimat-claim.
2. Mark the SHORTEST span that carries the theme. A whole paragraph gets a mark
   only when the theme is distributed across it, not when one clause carries it.
3. Absence of a mark is data. A visit report with no reconciliation passage is a
   finding, not a failure of yours. Do not manufacture marks to fill categories.
4. Never mark OCR garble, advertisements, or text bleeding in from an adjacent
   column. If a passage is unreadable, skip it.
5. Under-marking is recoverable; the historian can always select an unmarked
   passage. Over-marking silently biases her reading. When in doubt, omit.

Return a JSON array. Each element:
  {"quote": "<the exact substring from the text, verbatim, 4-40 words>",
   "category": "<one id from the list>",
   "confidence": <0.0-1.0>,
   "rationale": "<one short clause: why this passage, in English>"}

`quote` must be copied character-for-character from the text you were given,
including any OCR errors. Do not normalize spelling, spacing, or punctuation —
the quote is matched against the source by exact string search, and a
prettified quote is discarded. Return [] if nothing qualifies.""",
}]

MAX_CHARS = 60000


def parse_json(text):
    m = re.search(r"\[.*\]", text, re.S)
    if not m:
        return []
    try:
        out = json.loads(m.group(0))
        return out if isinstance(out, list) else []
    except json.JSONDecodeError:
        return []


def locate(text, quote):
    """Unambiguous match, tolerant of line-wrapping only. (start, end) or None.

    Every non-space character must still match exactly, OCR errors included —
    that is what stops an invented or silently-corrected quote from becoming a
    highlight. Runs of whitespace are the one exception: the model is given
    text wrapped at the scan's line breaks and re-flows it when quoting, which
    was discarding otherwise sound marks. Offsets come from the match against
    the real text, so they stay valid for the app.
    """
    quote = quote.strip()
    if len(quote) < 8:
        return None
    pattern = r"\s+".join(re.escape(w) for w in quote.split())
    hits = []
    for m in re.finditer(pattern, text):
        hits.append((m.start(), m.end()))
        if len(hits) > 1:
            return None
    return hits[0] if hits else None


def run_doc(doc, usage, force):
    src = doc["panes"]["source"]
    text = src["text"]
    # Long documents are chunked on page boundaries so a quote never straddles
    # a chunk edge and becomes unlocatable.
    blocks = src.get("pages") or src.get("segments") or []
    chunks, start = [], 0
    for b in blocks:
        if b["end"] - start > MAX_CHARS:
            chunks.append((start, b["start"]))
            start = b["start"]
    chunks.append((start, len(text)))

    found, dropped = [], 0
    for ci, (a, b) in enumerate(chunks):
        body = text[a:b]
        if not body.strip():
            continue
        user = (f"Document: {doc['meta']['title']}\n"
                f"Type: {doc['meta']['doc_type']}, {doc['meta']['date_text']}\n"
                f"Archivist's rationale: {doc['meta']['heimat_rationale']}\n\n"
                f"---\n{body}")
        raw = llm.ask(SYSTEM, user, task="prehighlight", usage=usage,
                      max_tokens=8000, effort="medium", force=force)
        for item in parse_json(raw):
            quote = str(item.get("quote") or "")
            cat = str(item.get("category") or "")
            if cat not in CATEGORIES:
                dropped += 1
                continue
            span = locate(body, quote)
            if span is None:
                dropped += 1
                continue
            s, e = a + span[0], a + span[1]
            try:
                conf = float(item.get("confidence", 0))
            except (TypeError, ValueError):
                conf = 0.0
            found.append({
                "id": f"cl-{doc['doc_id']}-{ci}-{len(found):03d}",
                "pane": "source", "start": s, "end": e,
                "quote": text[s:e],
                "source": "claude", "category": cat, "match": "",
                "strict": conf >= 0.8,
                "confidence": round(conf, 2),
                "rationale": str(item.get("rationale") or "")[:200],
            })
    return found, dropped


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--docs", nargs="*")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    files = sorted(DOCS.glob("*.json"))
    if args.docs:
        files = [f for f in files if any(d in f.stem for d in args.docs)]
    if args.limit:
        files = files[:args.limit]

    usage = llm.Usage()
    total = total_dropped = 0
    for f in files:
        doc = json.loads(f.read_text(encoding="utf-8"))
        found, dropped = run_doc(doc, usage, args.force)
        doc["prehighlights"] = [h for h in doc["prehighlights"]
                                if h.get("source") != "claude"] + found
        f.write_text(json.dumps(doc, ensure_ascii=False, indent=1),
                     encoding="utf-8")
        total += len(found)
        total_dropped += dropped
        strict = sum(1 for h in found if h["strict"])
        print(f"  {doc['doc_id']:26} {len(found):3} marks ({strict} strict)"
              + (f"  {dropped} dropped" if dropped else ""))
    print(f"{total} Claude marks across {len(files)} docs; "
          f"{total_dropped} dropped as unlocatable or out-of-vocabulary")
    print(f"  {usage.report()}")


if __name__ == "__main__":
    main()
