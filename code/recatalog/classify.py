"""Stage 1 (classify) — turn Tesseract output into pages_ocr.tsv with routing flags.

Reads the free Tesseract manifest + per-page text and classifies each page by
script (hebrew/latin/mixed/none) and modality (print / print_degraded /
handwriting_or_image / blank), then flags which pages need escalation to a paid
handwriting engine (Transkribus / Claude vision). Escalation set = the pages the
free engine could not read well.

Usage:  python code/recatalog/classify.py --folder 0444-3
Writes: data/recatalog/<folder>/pages_ocr.tsv
"""
from __future__ import annotations
import argparse, csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
BASE = ROOT / "data/recatalog"

HEB = range(0x0590, 0x05FF)


def scripts(text: str) -> str:
    heb = sum(1 for c in text if ord(c) in HEB)
    lat = sum(1 for c in text if c.isascii() and c.isalpha())
    if heb == 0 and lat == 0:
        return "none"
    if heb and lat and min(heb, lat) / max(heb, lat) > 0.15:
        return "mixed"
    return "hebrew" if heb > lat else "latin"


def classify(chars: int, conf: float) -> tuple[str, bool]:
    """(modality, needs_escalation)."""
    if chars == 0:
        return "blank_or_image", True      # photo / blank / handwriting Tesseract dropped
    if conf >= 0.75 and chars >= 80:
        return "print", False
    if conf >= 0.60:
        return "print_degraded", False
    return "handwriting_or_image", True    # low conf w/ text => cursive or degraded


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", required=True)
    args = ap.parse_args()
    base = BASE / args.folder
    man = base / "ocr_tesseract" / "_manifest.tsv"
    txt_dir = base / "ocr_tesseract"

    rows = []
    with man.open() as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            pno = int(r["page_no"]); chars = int(r["chars"]); conf = float(r["mean_conf"])
            text = (txt_dir / f"{pno:04d}.txt").read_text(errors="ignore")
            scr = scripts(text)
            mod, esc = classify(chars, conf)
            rows.append([pno, chars, f"{conf:.3f}", scr, mod,
                         "tesseract", "yes" if esc else "no",
                         f"ocr_tesseract/{pno:04d}.txt"])
    rows.sort(key=lambda x: x[0])
    out = base / "pages_ocr.tsv"
    with out.open("w", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["page_no", "chars", "conf", "script", "modality",
                    "engine", "needs_escalation", "text_file"])
        w.writerows(rows)

    esc = sum(1 for r in rows if r[6] == "yes")
    print(f"{len(rows)} pages -> {out}")
    print(f"  escalation set (handwriting/image/blank): {esc} pages "
          f"({esc*100//len(rows)}%)")
    from collections import Counter
    for k, v in Counter(r[4] for r in rows).most_common():
        print(f"  {k:22} {v}")
    for k, v in Counter(r[3] for r in rows).most_common():
        print(f"  script:{k:15} {v}")


if __name__ == "__main__":
    main()
