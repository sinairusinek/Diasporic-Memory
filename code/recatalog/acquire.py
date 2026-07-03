"""Stage 0 — acquire scan images for one folder via rclone, then inventory them.

Downloads a Drive folder's page JPEGs (addressed by Drive folder ID) into
data/recatalog/<folder>/scans/ and writes pages.tsv.

Prereq (one-time): configure an rclone remote for the Google Drive holding the
scans, e.g.  `rclone config`  ->  remote name `jeckedrive`, type `drive`.

Usage:
  python code/recatalog/acquire.py --folder 0444-3 \
      --drive-folder-id 1rpo85nfk5RFq7xZWvROIk2tX5A87mlLg \
      --remote jeckedrive

Notes:
- Uses --drive-root-folder-id so we copy exactly that folder, wherever it lives.
- pages.tsv page_no is parsed from the trailing _NNNN in the filename
  (folder-wide page counter; scan order != document order).
"""
from __future__ import annotations
import argparse, csv, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
OUT_ROOT = ROOT / "data/recatalog"
PAGE_RE = re.compile(r"_(\d{3,4})\.jpe?g$", re.I)


def rclone_copy(remote: str, drive_folder_id: str, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    cmd = [
        "rclone", "copy", f"{remote}:",
        "--drive-root-folder-id", drive_folder_id,
        str(dest),
        "--drive-acknowledge-abuse", "--transfers", "8", "--progress",
        "--include", "*.jpg", "--include", "*.jpeg",
    ]
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True)


def inventory(scans: Path, out_tsv: Path) -> int:
    rows = []
    for f in sorted(scans.glob("*.jp*g")):
        m = PAGE_RE.search(f.name)
        page_no = int(m.group(1)) if m else -1
        rows.append((page_no, f.name, "", f.stat().st_size))
    rows.sort(key=lambda r: r[0])
    with out_tsv.open("w", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["page_no", "filename", "file_id", "bytes"])
        w.writerows(rows)
    return len(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", required=True, help="short folder id, e.g. 0444-3")
    ap.add_argument("--drive-folder-id", required=True)
    ap.add_argument("--remote", default="jeckedrive")
    ap.add_argument("--skip-download", action="store_true", help="only re-inventory")
    args = ap.parse_args()

    base = OUT_ROOT / args.folder
    scans = base / "scans"
    if not args.skip_download:
        rclone_copy(args.remote, args.drive_folder_id, scans)
    if not scans.exists():
        sys.exit(f"no scans at {scans}")
    n = inventory(scans, base / "pages.tsv")
    print(f"pages.tsv: {n} pages -> {base/'pages.tsv'}")


if __name__ == "__main__":
    main()
