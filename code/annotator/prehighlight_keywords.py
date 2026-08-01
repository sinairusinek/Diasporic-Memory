#!/usr/bin/env python3
"""Lexical pre-highlights: the deterministic half of the highlighting.

Reuses the vocabularies compiled in code/israelkorpus/scan_heimat_signals.py
rather than restating them, so the annotator and the corpus scan can never
disagree about what counts as a Heimat signal.

Those regexes were written to run over `norm()`-ed text (lowercased, DGD
transcription artefacts stripped, whitespace collapsed), which does not share an
offset space with the text the PI reads. So we normalize with an index map and
project every match back onto the original string. Running case-insensitive
regexes on the raw text instead would look simpler and would quietly miss every
match that straddles a line break.

Tiering matters more than coverage here. `return_visit_candidate` is loose
co-occurrence ("Deutschland" near a travel verb) and is over half of all hits in
the oral corpus; it is emitted but marked strict=False, and the app keeps that
layer off by default. Over-highlighting silently biases the reading; the PI can
always select an unmarked passage herself.

Input/Output: data/annotator/docs/*.json  (edited in place)
"""
import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DOCS = REPO / "data/annotator/docs"
sys.path.insert(0, str(REPO / "code/israelkorpus"))

from scan_heimat_signals import (  # noqa: E402
    ANCHOR, ARTIFACTS, DIRECT, INVITE_ANCHOR, STRONG, TRAVEL)

# Categories that survive the "no forced Heimat framing" rule on their own.
# `vaterland` is deliberately kept separate from `heimat` and NOT merged into
# it: they are distinct evidentiary axes.
STRICT = {"heimat", "vaterland", "return_visit_lexeme",
          "return_visit_strong", "invitation", "restitution"}

# Hebrew equivalents, for the handful of Hebrew-language sources. Explicit
# lexemes only — מולדת / עיר הולדת / געגועים / שיבה. Atmosphere and mere
# place-naming do not qualify.
HEBREW = {
    "heimat": re.compile(r"מולדת\w*|עיר הולדת\w*|עיר מולדת\w*|כמיהה|געגוע\w*"),
    "return_visit_lexeme": re.compile(
        r"שיבה ל|חזרה לגרמניה|שב\w* לגרמניה|ביקור\w* בגרמניה|נסיע\w* לגרמניה"),
    "invitation": re.compile(r"הזמנ\w* (?:רשמית |מטעם )?(?:העיר|העירייה)|הוזמ\w+"),
    "restitution": re.compile(r"פיצוי\w*|שילומים|השבת רכוש"),
}

_WS = re.compile(r"\s+")


def normalize_with_map(text: str):
    """norm()-equivalent text plus norm-index -> original-index.

    Mirrors scan_heimat_signals.norm() exactly: artefacts to a space, lowercase,
    whitespace runs collapsed to one space. Characters whose lowercase form is
    not single-width are left as-is so the map stays 1:1.
    """
    chars, idx = [], []
    for i, ch in enumerate(text):
        low = ch.lower()
        chars.append(low if len(low) == 1 else ch)
        idx.append(i)
    stage1 = "".join(chars)

    # Blank out artefacts, preserving length so the map survives.
    marked = list(stage1)
    for m in ARTIFACTS.finditer(stage1):
        for j in range(m.start(), m.end()):
            marked[j] = " "

    out, omap, prev_space = [], [], False
    for j, ch in enumerate(marked):
        if ch.isspace():
            if prev_space:
                continue
            out.append(" ")
            omap.append(idx[j])
            prev_space = True
        else:
            out.append(ch)
            omap.append(idx[j])
            prev_space = False
    omap.append(len(text))
    return "".join(out), omap


def trim(text: str, start: int, end: int):
    """Shrink a span off surrounding whitespace/punctuation."""
    while start < end and (text[start].isspace() or text[start] in "«»\"'([-–—"):
        start += 1
    while end > start and (text[end - 1].isspace()
                           or text[end - 1] in "«»\"'.,;:)]-–—"):
        end -= 1
    return start, end


def scan_pane(text: str, lang: str):
    """Every lexical hit in one pane, as offsets into `text`."""
    hits = []
    normed, omap = normalize_with_map(text)

    def add(category, m, strict):
        s, e = omap[m.start()], omap[min(m.end(), len(omap) - 1)]
        s, e = trim(text, s, e)
        if e > s:
            hits.append({"start": s, "end": e, "category": category,
                         "match": text[s:e], "strict": strict})

    patterns = HEBREW if lang == "he" else DIRECT
    for category, rx in patterns.items():
        for m in rx.finditer(normed):
            if category == "invitation" and lang != "he":
                window = normed[max(0, m.start() - 400):m.end() + 400]
                if not INVITE_ANCHOR.search(window):
                    continue
            add(category, m, category in STRICT)

    if lang != "he":
        strong_spans = []
        for m in STRONG.finditer(normed):
            strong_spans.append((m.start(), m.end()))
            add("return_visit_strong", m, True)
        for m in ANCHOR.finditer(normed):
            if any(a <= m.start() < b for a, b in strong_spans):
                continue
            window = normed[max(0, m.start() - 300):m.end() + 300]
            if TRAVEL.search(window):
                add("return_visit_candidate", m, False)

    return dedupe(hits)


def dedupe(hits):
    """Drop exact duplicates; keep overlapping hits of different categories."""
    seen, out = set(), []
    for h in sorted(hits, key=lambda h: (h["start"], h["end"], h["category"])):
        key = (h["start"], h["end"], h["category"])
        if key in seen:
            continue
        seen.add(key)
        out.append(h)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--docs", nargs="*", help="doc_id substrings to limit to")
    args = ap.parse_args()

    files = sorted(DOCS.glob("*.json"))
    if args.docs:
        files = [f for f in files if any(d in f.stem for d in args.docs)]

    totals = {}
    for f in files:
        doc = json.loads(f.read_text(encoding="utf-8"))
        kept = [h for h in doc["prehighlights"] if h.get("source") != "keyword"]
        new = []
        for pane_name in ("source", "translation"):
            pane = doc["panes"].get(pane_name)
            if not pane:
                continue
            for i, h in enumerate(scan_pane(pane["text"], pane["lang"])):
                new.append({
                    "id": f"kw-{doc['doc_id']}-{pane_name}-{i:04d}",
                    "pane": pane_name,
                    "start": h["start"], "end": h["end"],
                    "quote": h["match"],
                    "source": "keyword",
                    "category": h["category"],
                    "match": h["match"],
                    "strict": h["strict"],
                    "confidence": 1.0 if h["strict"] else 0.4,
                    "rationale": "",
                })
                totals[h["category"]] = totals.get(h["category"], 0) + 1
        doc["prehighlights"] = kept + new
        f.write_text(json.dumps(doc, ensure_ascii=False, indent=1),
                     encoding="utf-8")

    strict = sum(v for k, v in totals.items() if k in STRICT)
    loose = sum(v for k, v in totals.items() if k not in STRICT)
    print(f"{len(files)} docs · {strict} strict + {loose} loose lexical hits")
    for k in sorted(totals, key=lambda k: -totals[k]):
        print(f"  {'  ' if k in STRICT else '~ '}{k:26} {totals[k]}")


if __name__ == "__main__":
    main()
