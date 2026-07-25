"""Minimal Transkribus REST client.

Reads:  TRANSKRIBUS_USER, TRANSKRIBUS_PASS from environment
Writes: data/transkribus/htr/<docId>/
          fulldoc.json            full doc metadata (collId, pages, imgUrl, ...)
          pages/<pageNr>.xml      PAGE XML transcription
          pages/<pageNr>.txt      plain text (one line per PAGE TextLine)
          pages/<pageNr>.jpg      page image

Usage:
  python code/transkribus_client.py --doc 1243735                    # whole doc
  python code/transkribus_client.py --doc 1243735 --pages 1-5,10     # specific pages
  python code/transkribus_client.py --doc 1243735 --text-only        # skip image download

Transkribus REST docs: https://transkribus.eu/TrpServer/Swadl/wadl.html
"""
from __future__ import annotations
import argparse, json, os, re, sys, time
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET

import requests

BASE = "https://transkribus.eu/TrpServer/rest"
ROOT = Path(__file__).resolve().parent.parent
OUT_ROOT = ROOT / "data/transkribus/htr"
PAGE_NS = {"p": "http://schema.primaresearch.org/PAGE/gts/pagecontent/2013-07-15"}


def login(session: requests.Session) -> None:
    user = os.environ.get("TRANSKRIBUS_USER")
    pw = os.environ.get("TRANSKRIBUS_PASS")
    if not user or not pw:
        sys.exit("Set TRANSKRIBUS_USER and TRANSKRIBUS_PASS")
    r = session.post(f"{BASE}/auth/login", data={"user": user, "pw": pw}, timeout=30)
    r.raise_for_status()


def find_doc(session: requests.Session, doc_id: int) -> tuple[int, dict]:
    """Walk the user's collections to find which one holds doc_id. Returns (collId, fulldoc)."""
    r = session.get(f"{BASE}/collections/list", params={"JSON": True}, timeout=30)
    r.raise_for_status()
    cols = r.json()
    for col in cols:
        cid = col["colId"]
        rr = session.get(
            f"{BASE}/collections/{cid}/{doc_id}/fulldoc", params={"JSON": True}, timeout=60
        )
        if rr.status_code == 200:
            return cid, rr.json()
    sys.exit(f"docId {doc_id} not found in any of {len(cols)} collections")


def parse_pages_spec(spec: str, max_n: int) -> list[int]:
    out: set[int] = set()
    for part in spec.split(","):
        if "-" in part:
            a, b = part.split("-", 1)
            out.update(range(int(a), int(b) + 1))
        else:
            out.add(int(part))
    return sorted(p for p in out if 1 <= p <= max_n)


def page_xml_text(xml_bytes: bytes) -> str:
    """Concatenate Unicode text from every TextLine in a PAGE XML, in order."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        return f"[XML parse error: {e}]"
    lines: list[str] = []
    for tl in root.iter("{http://schema.primaresearch.org/PAGE/gts/pagecontent/2013-07-15}TextLine"):
        u = tl.find(".//p:Unicode", PAGE_NS)
        if u is not None and u.text:
            lines.append(u.text)
    return "\n".join(lines)


def download_page(
    session: requests.Session, col_id: int, doc_id: int, page: dict, out_dir: Path,
    fetch_image: bool, fetch_text: bool,
) -> None:
    page_nr = page["pageNr"]
    page_id = page["pageId"]
    nr_pad = f"{page_nr:04d}"
    # PAGE XML
    if fetch_text:
        # Use the most-recent transcript if any exists
        tsl = page.get("tsList", {}).get("transcripts", [])
        if tsl:
            ts_url = tsl[0]["url"]
            r = session.get(ts_url, timeout=60)
            if r.status_code == 200:
                (out_dir / f"{nr_pad}.xml").write_bytes(r.content)
                text = page_xml_text(r.content)
                (out_dir / f"{nr_pad}.txt").write_text(text, encoding="utf-8")
                print(f"  page {nr_pad}: {len(text.splitlines())} text lines")
            else:
                print(f"  page {nr_pad}: transcript HTTP {r.status_code}", file=sys.stderr)
        else:
            print(f"  page {nr_pad}: no transcript")
    # Image
    if fetch_image and page.get("url"):
        r = session.get(page["url"], timeout=120)
        if r.status_code == 200:
            (out_dir / f"{nr_pad}.jpg").write_bytes(r.content)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--doc", type=int, required=True, help="Transkribus docId")
    ap.add_argument("--col", type=int, help="Collection ID (optional; auto-discovered otherwise)")
    ap.add_argument("--pages", help='Page selection e.g. "1-5,10" (default: all)')
    ap.add_argument("--text-only", action="store_true", help="Skip image download")
    ap.add_argument("--images-only", action="store_true", help="Skip PAGE XML download")
    args = ap.parse_args()

    s = requests.Session()
    login(s)
    print("logged in", file=sys.stderr)

    if args.col:
        col_id = args.col
        r = s.get(f"{BASE}/collections/{col_id}/{args.doc}/fulldoc", params={"JSON": True}, timeout=60)
        r.raise_for_status()
        fulldoc = r.json()
    else:
        col_id, fulldoc = find_doc(s, args.doc)
        print(f"found in collId={col_id}", file=sys.stderr)

    out_dir = OUT_ROOT / str(args.doc)
    pages_dir = out_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "fulldoc.json").write_text(json.dumps(fulldoc, indent=2, ensure_ascii=False))
    (out_dir / "colId.txt").write_text(str(col_id))

    pages = fulldoc.get("pageList", {}).get("pages", []) or []
    title = fulldoc.get("md", {}).get("title") or fulldoc.get("title")
    print(f"doc {args.doc} '{title}': {len(pages)} pages")

    if args.pages:
        wanted = set(parse_pages_spec(args.pages, len(pages)))
        pages = [p for p in pages if p["pageNr"] in wanted]
        print(f"selected {len(pages)} pages")

    fetch_text = not args.images_only
    fetch_image = not args.text_only
    for i, p in enumerate(pages, 1):
        download_page(s, col_id, args.doc, p, pages_dir, fetch_image, fetch_text)
        if i % 10 == 0:
            time.sleep(1)


if __name__ == "__main__":
    main()
