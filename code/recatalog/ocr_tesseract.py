"""Stage 1 (print) — FREE local OCR via Tesseract.

Zero-cost alternative to Google Vision for printed / typescript pages. Runs fully
offline on the rclone-downloaded scans, so it consumes no Max-plan tokens and no
paid API. Used in the pilot's PRINT bake-off: Tesseract (free) vs Google Vision.

Prereq (one-time):
  macOS:  brew install tesseract tesseract-lang     # includes deu, heb, eng, frak
  check:  tesseract --list-langs

Usage:
  python code/recatalog/ocr_tesseract.py --folder 0444-3            # all pages
  python code/recatalog/ocr_tesseract.py --folder 0444-3 --pages 110-130
  # German Fraktur / old print:
  python code/recatalog/ocr_tesseract.py --folder 0444-3 --langs deu+frak+heb+eng

Writes: data/recatalog/<folder>/ocr_tesseract/<page_no>.txt
        data/recatalog/<folder>/ocr_tesseract/_manifest.tsv  (page_no, chars, mean_conf)

mean_conf comes from Tesseract TSV output (per-word confidences, 0-100) and is the
cheap quality signal we compare against Vision in the feasibility memo.
"""
from __future__ import annotations
import argparse, csv, re, statistics, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
OUT_ROOT = ROOT / "data/recatalog"
PAGE_RE = re.compile(r"_(\d{3,4})\.jpe?g$", re.I)


def parse_pages(spec: str) -> set[int]:
    out: set[int] = set()
    for part in spec.split(","):
        if "-" in part:
            a, b = part.split("-", 1)
            out.update(range(int(a), int(b) + 1))
        else:
            out.add(int(part))
    return out


def ocr_page(img: Path, langs: str) -> tuple[str, float]:
    """Return (text, mean_word_confidence 0-1)."""
    txt = subprocess.run(
        ["tesseract", str(img), "-", "-l", langs, "--psm", "3"],
        capture_output=True, text=True,
    ).stdout
    tsv = subprocess.run(
        ["tesseract", str(img), "-", "-l", langs, "--psm", "3", "tsv"],
        capture_output=True, text=True,
    ).stdout
    confs = []
    for line in tsv.splitlines()[1:]:
        cols = line.split("\t")
        if len(cols) >= 12 and cols[11].strip():
            try:
                c = float(cols[10])
                if c >= 0:
                    confs.append(c)
            except ValueError:
                pass
    mean_conf = round(statistics.mean(confs) / 100, 3) if confs else 0.0
    return txt.strip(), mean_conf


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", required=True)
    ap.add_argument("--langs", default="deu+heb+eng")
    ap.add_argument("--pages", help="e.g. 110-130,145")
    args = ap.parse_args()

    base = OUT_ROOT / args.folder
    scans = base / "scans"
    if not scans.exists():
        sys.exit(f"no scans at {scans} (run acquire.py first)")
    out = base / "ocr_tesseract"
    out.mkdir(exist_ok=True)

    want = parse_pages(args.pages) if args.pages else None
    manifest = []
    for img in sorted(scans.glob("*.jp*g")):
        m = PAGE_RE.search(img.name)
        page_no = int(m.group(1)) if m else -1
        if want is not None and page_no not in want:
            continue
        text, conf = ocr_page(img, args.langs)
        (out / f"{page_no:04d}.txt").write_text(text)
        manifest.append((page_no, len(text), conf))
        print(f"p{page_no:>4}  {len(text):>5} chars  conf {conf}")

    manifest.sort()
    with (out / "_manifest.tsv").open("w", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["page_no", "chars", "mean_conf"])
        w.writerows(manifest)
    print(f"\n{len(manifest)} pages -> {out}")


if __name__ == "__main__":
    main()
