#!/usr/bin/env python3
"""Shared text normalization for the annotator build pipeline.

EVERY character offset and content hash in data/annotator/ depends on the
functions here byte-for-byte. Never inline or reimplement them: if `join_pages`
changes, every stored annotation offset for every written document drifts, and
the app falls back to quote-relocation for the whole corpus.

The contract:
  * a document's text is ONE flat string;
  * `join_pages` returns that string plus a list of (start, end) spans, one per
    page, in the same offset space;
  * the joiner between pages ("\n\n") belongs to no page, so a selection that
    crosses a boundary resolves to every page whose span it overlaps.
"""
import hashlib
import re
import unicodedata

PAGE_JOINER = "\n\n"

# Line-final hyphen + newline = a word broken across lines by the typesetter.
# Only rejoin when what follows starts lowercase; "Jüdische Gemeinde-\nVorstand"
# is a real compound and must keep its hyphen.
_DEHYPHEN = re.compile(r"(\w)-\n(?=[a-zäöüß])")

# Tesseract emits stray form feeds and long runs of blank lines.
_FORMFEED = re.compile(r"\f+")
_BLANKRUN = re.compile(r"\n{3,}")
_TRAILWS = re.compile(r"[ \t]+(?=\n)")


def normalize_page(text: str) -> str:
    """Clean one page of OCR without changing its meaning.

    Idempotent: normalize_page(normalize_page(x)) == normalize_page(x).
    """
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _FORMFEED.sub("\n", text)
    text = _DEHYPHEN.sub(r"\1", text)
    text = _TRAILWS.sub("", text)
    text = _BLANKRUN.sub("\n\n", text)
    return text.strip()


def join_pages(pages):
    """Join normalized page texts into one offset space.

    `pages` is an iterable of (key, raw_text). Returns (text, spans) where
    spans is a list of dicts {key, start, end}; `end` is exclusive and points
    at the first character of the joiner, which belongs to no page.

    Blank pages are kept with start == end so the page index stays complete
    and the scan strip can still show them.
    """
    parts, spans, cursor = [], [], 0
    for i, (key, raw) in enumerate(pages):
        body = normalize_page(raw or "")
        if i:
            parts.append(PAGE_JOINER)
            cursor += len(PAGE_JOINER)
        spans.append({"key": key, "start": cursor, "end": cursor + len(body)})
        parts.append(body)
        cursor += len(body)
    text = "".join(parts)
    assert cursor == len(text), "join_pages cursor desync"
    return text, spans


def sha256_text(text: str) -> str:
    """Content hash of a pane, used to detect drift against stored offsets."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def context(text: str, start: int, end: int, pad: int = 32):
    """The W3C quote-selector triple for a span: (prefix, quote, suffix)."""
    return (text[max(0, start - pad):start],
            text[start:end],
            text[end:end + pad])


def spans_overlapping(spans, start, end):
    """Every span (page or contribution) a [start, end) selection touches."""
    return [s for s in spans
            if s["start"] < end and s["end"] > start
            or (s["start"] == s["end"] == start)]
