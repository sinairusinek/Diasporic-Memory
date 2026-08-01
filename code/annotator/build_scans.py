#!/usr/bin/env python3
"""Make WebP page derivatives and upload them to Vercel Blob.

The originals are ~2.2 GB and gitignored (data/recatalog/*/scans/), so the app
cannot read them from a checkout. Downscaling only the ~300 pages actually in
scope gives ~35 MB, which Blob serves happily — and the app proxies them
through /api/scan so the session gate applies. Blob URLs are public by default;
putting them in the bundle rather than in the page's <img src> is what keeps
rights-uncertain material behind the password.

Needs BLOB_READ_WRITE_TOKEN. Without it the build is a no-op and the app simply
shows no facsimile.

Input:  data/annotator/docs/*.json, data/recatalog/<folder>/scans/
Output: scan_url written into each page block; local copies under
        data/annotator/scans/ for inspection
"""
import argparse
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

REPO = Path(__file__).resolve().parents[2]
DOCS = REPO / "data/annotator/docs"
RECATALOG = REPO / "data/recatalog"
LOCAL = REPO / "data/annotator/scans"

MAX_EDGE = 1600
QUALITY = 80
BLOB_API = "https://blob.vercel-storage.com"


def derivative(src: Path, dest: Path) -> bool:
    from PIL import Image
    if dest.exists():
        return True
    try:
        with Image.open(src) as im:
            im = im.convert("RGB")
            scale = MAX_EDGE / max(im.size)
            if scale < 1:
                im = im.resize((round(im.width * scale), round(im.height * scale)),
                               Image.LANCZOS)
            dest.parent.mkdir(parents=True, exist_ok=True)
            im.save(dest, "WEBP", quality=QUALITY, method=5)
        return True
    except Exception as e:
        print(f"  ! {src.name}: {e}")
        return False


def upload(path: Path, key: str, token: str) -> str | None:
    r = requests.put(
        f"{BLOB_API}/{key}",
        headers={"authorization": f"Bearer {token}",
                 "x-api-version": "7",
                 "x-content-type": "image/webp",
                 "x-add-random-suffix": "0"},
        data=path.read_bytes(), timeout=120)
    if r.status_code >= 300:
        print(f"  ! upload {key}: {r.status_code} {r.text[:120]}")
        return None
    return r.json().get("url")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--docs", nargs="*")
    ap.add_argument("--no-upload", action="store_true",
                    help="build derivatives only; leave scan_url unset")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    token = os.environ.get("BLOB_READ_WRITE_TOKEN")
    if not token and not args.no_upload:
        print("BLOB_READ_WRITE_TOKEN is not set — building local derivatives "
              "only. The app will show no facsimile until it is set.")
        args.no_upload = True

    files = sorted(DOCS.glob("*.json"))
    if args.docs:
        files = [f for f in files if any(d in f.stem for d in args.docs)]

    made = sent = missing = 0
    for f in files:
        doc = json.loads(f.read_text(encoding="utf-8"))
        pages = doc["panes"]["source"].get("pages") or []
        folder = doc["meta"]["folder"]
        jobs = []
        for p in pages:
            if not p.get("scan_file"):
                missing += 1
                continue
            src = RECATALOG / folder / "scans" / p["scan_file"]
            if not src.exists():
                missing += 1
                continue
            dest = LOCAL / doc["doc_id"] / f"{p['page_no']:04d}.webp"
            jobs.append((p, src, dest))

        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            ok = list(pool.map(lambda j: derivative(j[1], j[2]), jobs))
        made += sum(ok)

        for (p, _src, dest), good in zip(jobs, ok):
            if not good:
                continue
            if args.no_upload:
                continue
            key = f"annotator/{doc['doc_id']}/{p['page_no']:04d}.webp"
            url = upload(dest, key, token)
            if url:
                p["scan_url"] = url
                sent += 1

        f.write_text(json.dumps(doc, ensure_ascii=False, indent=1),
                     encoding="utf-8")
        if jobs:
            size = sum(d.stat().st_size for _, _, d in jobs if d.exists())
            print(f"  {doc['doc_id']:26} {len(jobs):3} pages  {size/1e6:5.1f} MB")

    print(f"{made} derivatives, {sent} uploaded, {missing} pages without a scan")
    if args.no_upload:
        print(f"  local copies under {LOCAL} (gitignored)")


if __name__ == "__main__":
    main()
