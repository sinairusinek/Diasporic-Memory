#!/usr/bin/env python3
"""Build one annotator bundle per written visit document.

Reads the manifest produced by select_docs.py, expands each document's
page_range, concatenates the per-page Tesseract output into a single offset
space via textnorm.join_pages, and records each page's span, scan filename and
OCR confidence so the app can show the facsimile beside the text and warn where
the transcription is untrustworthy.

Input:  data/annotator/manifest.tsv
        data/recatalog/<folder>/{catalog.tsv,pages_ocr.tsv,ocr_tesseract/*.txt}
Output: data/annotator/docs/<doc_id>.json   (source pane only)
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from textnorm import join_pages, sha256_text

REPO = Path(__file__).resolve().parents[2]
RECATALOG = REPO / "data/recatalog"
MANIFEST = REPO / "data/annotator/manifest.tsv"
DOCS = REPO / "data/annotator/docs"

SCAN_RE = re.compile(r"_(\d{4})_(\d{4})\.jpe?g$", re.I)

# Tesseract's mean confidence is necessary but nowhere near sufficient. On the
# press-clipping montages (0444-3 p225, 0422-3 p108) it reports conf >= 0.75
# while the reading order is shredded across columns and Hebrew bleeds through
# the Latin — per-word confidence is high, the page is unusable. So grade each
# page on three signals and let the grade, not conf alone, gate translation.
CONF_FLOOR = 0.40          # below this the page is not really transcribed
WORDFRAC_FLOOR = 0.35      # fraction of tokens that are plausible words
_WORDISH = re.compile(r"[A-Za-zÄÖÜäöüßÀ-ÿ]{3,}")
_TOKEN = re.compile(r"\S+")
_STRIP = ".,;:!?»«\"'()[]–—"


def grade_page(text: str, conf: float | None) -> tuple[str, dict]:
    """'clean' | 'mixed' | 'poor', plus the signals behind the call.

    clean  ordinary prose; translate normally.
    mixed  readable but with shredded columns or heavy OCR noise; translate,
           but the reader sees a caution band and the translator is told.
    poor   not a transcription; never translated, never annotated on.

    conf is None for engines that report no per-page confidence (Transkribus's
    Processing API returns plain text only); the two text-shape signals then
    carry the whole call.
    """
    tokens = _TOKEN.findall(text)
    lines = [ln for ln in text.split("\n") if ln.strip()]
    if not tokens:
        return "poor", {"wordfrac": 0.0, "shortline": 0.0, "tokens": 0}
    words = sum(1 for t in tokens if _WORDISH.fullmatch(t.strip(_STRIP)))
    wordfrac = words / len(tokens)
    shortline = sum(1 for ln in lines if len(ln.strip()) < 25) / max(1, len(lines))
    signals = {"wordfrac": round(wordfrac, 3),
               "shortline": round(shortline, 3),
               "tokens": len(tokens)}
    if len(tokens) < 20:
        return ("poor" if wordfrac < WORDFRAC_FLOOR else "mixed"), signals
    if (conf is not None and conf < CONF_FLOOR) or wordfrac < WORDFRAC_FLOOR:
        return "poor", signals
    if wordfrac < 0.75 or shortline > 0.20:
        return "mixed", signals
    return "clean", signals


# Tesseract cannot read German cursive at all — on 0047-2 (Sharett/Frank) it
# returns Hebrew-looking noise for pages of perfectly legible Kurrent. Where a
# Transkribus HTR transcription exists (code/recatalog/transkribus_htr.py), take
# whichever engine grades better, so a targeted HTR run can rescue a folder
# without regressing the pages Tesseract already handled.
GRADE_RANK = {"poor": 0, "mixed": 1, "clean": 2}
_SENTINEL = ("__FAILED__", "__CANCELED__", "__TIMEOUT__")


def read_page(folder: str, page: int, tess_conf: float):
    """-> (text, engine, conf, grade, signals) for the better of the two engines.

    Tesseract's confidence is meaningless for Transkribus text, so the HTR page
    is graded with conf=None and the winner's own conf is what gets recorded.
    """
    tess = RECATALOG / folder / "ocr_tesseract" / f"{page:04d}.txt"
    t_text = tess.read_text(encoding="utf-8", errors="replace") if tess.exists() else ""
    cands = [(t_text, "tesseract", tess_conf)]

    htr = RECATALOG / folder / "ocr_transkribus" / f"{page:04d}.txt"
    if htr.exists():
        h_text = htr.read_text(encoding="utf-8", errors="replace")
        if not h_text.strip().startswith(_SENTINEL):
            cands.append((h_text, "transkribus", None))

    scored = []
    for text, engine, conf in cands:
        grade, signals = grade_page(text, conf)
        scored.append((GRADE_RANK[grade], signals["wordfrac"], len(text),
                       text, engine, conf, grade, signals))
    scored.sort(key=lambda s: s[:3], reverse=True)
    _, _, _, text, engine, conf, grade, signals = scored[0]
    return text, engine, conf, grade, signals


def slug(doc_id: str, folder: str) -> str:
    return f"{folder}__{doc_id}"


def parse_range(spec: str):
    """'50-52' -> [50, 51, 52]; '221' -> [221]; '5,8-9' -> [5, 8, 9]."""
    pages = []
    for part in re.split(r"[,;]", spec):
        part = part.strip()
        if not part:
            continue
        m = re.fullmatch(r"(\d+)\s*[-–]\s*(\d+)", part)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            pages += list(range(a, b + 1)) if a <= b else [a]
        elif part.isdigit():
            pages.append(int(part))
        else:
            raise ValueError(f"unparseable page_range fragment {part!r}")
    return pages


def scan_index(folder: str, n_ocr_pages: int):
    """page_no -> scan filename.

    Folders are normally 1:1 (page N is the Nth scan). 0276-6 is not: it holds
    147 files across six capture batches for 68 pages, and its pages.tsv page
    numbers were derived from the wrong filename group. So prefer the batch
    whose sequence numbers cover exactly the OCR page count, and fall back to
    sorted order only when the counts already agree.
    """
    d = RECATALOG / folder / "scans"
    if not d.is_dir():
        return {}
    files = sorted(p.name for p in d.iterdir() if SCAN_RE.search(p.name))
    if not files:
        return {}
    if len(files) == n_ocr_pages:
        return {i: name for i, name in enumerate(files, start=1)}

    groups = {}
    for name in files:
        g, seq = SCAN_RE.search(name).groups()
        groups.setdefault(g, {})[int(seq)] = name
    for g in sorted(groups, reverse=True):
        seqs = groups[g]
        if len(seqs) == n_ocr_pages and min(seqs) == 1 and max(seqs) == n_ocr_pages:
            return dict(seqs)
    print(f"  ! {folder}: {len(files)} scans vs {n_ocr_pages} OCR pages, "
          f"no batch matches — facsimile disabled for this folder")
    return {}


def page_quality(folder: str):
    """text_file -> (chars, mean_conf, needs_escalation).

    pages_ocr.tsv can carry duplicate rows per text_file (0276-6); the row with
    the most characters is the one that actually produced the transcription.
    """
    out = {}
    path = RECATALOG / folder / "pages_ocr.tsv"
    if not path.exists():
        return out
    with path.open(newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            tf = (r.get("text_file") or "").strip()
            if not tf:
                continue
            try:
                chars = int(r.get("chars") or 0)
                conf = float(r.get("conf") or 0)
            except ValueError:
                continue
            prev = out.get(tf)
            if prev is None or chars > prev[0]:
                out[tf] = (chars, conf,
                           (r.get("needs_escalation") or "").strip().lower() == "yes")
    return out


def catalog_rows(folder: str):
    path = RECATALOG / folder / "catalog.tsv"
    with path.open(newline="", encoding="utf-8") as fh:
        return {(r.get("doc_id") or "").strip(): r
                for r in csv.DictReader(fh, delimiter="\t")}


def build_doc(row, cat, scans, quality, folder):
    pages = parse_range(row["page_range"])
    raw, chosen = [], {}
    for p in pages:
        _, tess_conf, escalate = quality.get(f"ocr_tesseract/{p:04d}.txt",
                                             (0, 0.0, True))
        text, engine, conf, _, _ = read_page(folder, p, tess_conf)
        chosen[p] = (engine, conf, escalate)
        raw.append((p, text))
    text, spans = join_pages(raw)

    page_index = []
    for p, span in zip(pages, spans):
        engine, conf, escalate = chosen[p]
        body = text[span["start"]:span["end"]]
        grade, signals = grade_page(body, conf)
        if not body:
            grade = "poor"
        page_index.append({
            "page_no": p,
            "start": span["start"], "end": span["end"],
            "scan_file": scans.get(p),
            "scan_url": None,          # filled in by build_scans.py
            "ocr_engine": engine,
            "ocr_conf": round(conf, 3) if conf is not None else None,
            "needs_escalation": escalate,
            "grade": grade,
            "signals": signals,
            "translatable": grade != "poor",
        })

    def field(name):
        return (cat.get(name) or "").strip()

    def listfield(name):
        v = field(name)
        return [x.strip() for x in re.split(r"[;,]", v) if x.strip()] if v else []

    return {
        "doc_id": slug(row["doc_id"], row["folder"]),
        "catalog_doc_id": row["doc_id"],
        "case_id": row["case_id"],
        "kind": "written",
        "public": True,
        "meta": {
            "title": field("title"),
            "date_text": field("date_text"),
            "doc_type": field("doc_type"),
            "languages": listfield("languages"),
            "from_person": field("from_person"),
            "to_person": field("to_person"),
            "places": listfield("places"),
            "persons": listfield("persons"),
            "heimat_rationale": field("heimat_rationale"),
            "notes": field("notes"),
            "folder": row["folder"],
            "page_range": row["page_range"],
            "is_heimat_relevant": field("is_heimat_relevant"),
        },
        "summary_he": field("description_he"),
        "summary_de": field("description_de"),
        "summary_en": field("description_en"),
        "panes": {
            "source": {
                "pane": "source",
                "lang": (listfield("languages") or ["de"])[0],
                "dir": "rtl" if (listfield("languages") or ["de"])[0] == "he"
                       else "ltr",
                "text": text,
                "sha256": sha256_text(text),
                "pages": page_index,
            },
            "translation": None,   # filled in by translate_he.py
        },
        "prehighlights": [],
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--folders", nargs="*")
    ap.add_argument("--docs", nargs="*",
                    help="doc_id / folder substrings to limit to")
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()

    with MANIFEST.open(newline="", encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh, delimiter="\t")
                if r["include"] == "yes"]
    if args.folders:
        rows = [r for r in rows if r["folder"] in args.folders]
    if args.docs:
        rows = [r for r in rows
                if any(d in slug(r["doc_id"], r["folder"]) for d in args.docs)]
    if args.limit:
        rows = rows[:args.limit]

    DOCS.mkdir(parents=True, exist_ok=True)
    by_folder = {}
    for r in rows:
        by_folder.setdefault(r["folder"], []).append(r)

    total = 0
    for folder, frows in sorted(by_folder.items()):
        ocr_dir = RECATALOG / folder / "ocr_tesseract"
        n_ocr = len(list(ocr_dir.glob("[0-9][0-9][0-9][0-9].txt")))
        scans = scan_index(folder, n_ocr)
        quality = page_quality(folder)
        cat = catalog_rows(folder)
        for r in frows:
            doc = build_doc(r, cat[r["doc_id"]], scans, quality, folder)
            out = DOCS / f"{doc['doc_id']}.json"
            # Preserve panes/prehighlights produced by later, expensive stages.
            if out.exists():
                prev = json.loads(out.read_text(encoding="utf-8"))
                if prev["panes"]["source"]["sha256"] == \
                        doc["panes"]["source"]["sha256"]:
                    doc["panes"]["translation"] = prev["panes"]["translation"]
                    doc["prehighlights"] = prev["prehighlights"]
            out.write_text(json.dumps(doc, ensure_ascii=False, indent=1),
                           encoding="utf-8")
            src = doc["panes"]["source"]
            g = Counter(p["grade"] for p in src["pages"])
            e = Counter(p["ocr_engine"] for p in src["pages"])
            total += 1
            print(f"  {doc['doc_id']:24} {len(src['pages']):3}pp "
                  f"{len(src['text']):7}ch   "
                  f"clean {g['clean']:3}  mixed {g['mixed']:3}  poor {g['poor']:3}"
                  f"   htr {e['transkribus']:3}")
    print(f"{total} written bundles -> {DOCS}")


if __name__ == "__main__":
    main()
