#!/usr/bin/env python3
"""Re-transcribe the triaged handwritten pages with Transkribus HTR.

transkribus_client.py only ever pulled finished transcriptions down. This is
the other half, and it does not go through collections at all: the old
TrpServer recognition endpoints are retired (htrCITlab now answers with the
HTR+ shutdown notice), and the current Processing API is stateless — post an
image and a model id, poll, get PAGE back. Nothing is uploaded to a
collection, so nothing has to be cleaned up there afterwards.

Two models, chosen per page from the hand the triage saw:

  Text Titan II (579509)        Latin script — German, and the Latin-hand
                                letters of Hebrew-speaking correspondents
  Hebrew Hand Sept.25 (396997)  handwritten Hebrew

A page is transcribed with one model, never both: running the wrong script's
model produces fluent nonsense, which is the failure this whole exercise is
meant to remove.

Results are written beside the corpus, NOT into it. Replacing a source pane
changes its sha256, which would re-trigger the Hebrew translation of the whole
document and move every offset in it. That is a decision to take once the new
text has been read, not a side effect of transcribing.

Output: data/transkribus/annotator/<doc_id>/<page_no>.txt   plain text
        data/transkribus/annotator/<doc_id>/<page_no>.json  lines + coords
        data/transkribus/annotator/index.tsv                one row per page
"""
import argparse
import base64
import csv
import json
import random
import sys
import time
from pathlib import Path

import requests

REPO = Path(__file__).resolve().parents[2]
DOCS = REPO / "data/annotator/docs"
SCANS = REPO / "data/recatalog"
OUT = REPO / "data/transkribus/annotator"

TOKEN_URL = ("https://account.readcoop.eu/auth/realms/readcoop/"
             "protocol/openid-connect/token")
PROC_URL = "https://transkribus.eu/processing/v1/processes"
MODELS = {"latin": 579509, "hebrew": 396997}
MODEL_NAMES = {579509: "Text Titan II", 396997: "Hebrew Hand Sept.25"}


class Auth:
    """Bearer token that renews itself.

    The readcoop token is short-lived. Fetching it once at startup worked for
    the first three pages of a 34-page run and then every remaining request
    came back 401, so the expiry is refreshed ahead of time and any 401 is
    treated as "stale, get a new one and retry" rather than as a failure.
    """

    def __init__(self):
        import os
        self.user = os.environ.get("TRANSKRIBUS_USER")
        self.pw = os.environ.get("TRANSKRIBUS_PASS")
        if not self.user or not self.pw:
            sys.exit("Set TRANSKRIBUS_USER and TRANSKRIBUS_PASS")
        self.token = None
        self.expires_at = 0.0

    def headers(self):
        if self.token is None or time.time() > self.expires_at:
            self.refresh()
        return {"Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"}

    def refresh(self):
        r = requests.post(TOKEN_URL, timeout=30, data={
            "grant_type": "password", "client_id": "processing-api-client",
            "username": self.user, "password": self.pw})
        r.raise_for_status()
        j = r.json()
        self.token = j["access_token"]
        # Renew a minute early rather than discovering expiry as a 401.
        self.expires_at = time.time() + max(60, int(j.get("expires_in", 300)) - 60)


def _request(method, url, auth, **kw):
    """One call, retrying transient failures and re-authenticating on 401."""
    delay = 3.0
    for attempt in range(6):
        try:
            r = requests.request(method, url, headers=auth.headers(),
                                 timeout=kw.pop("timeout", 120), **kw)
        except (requests.ConnectionError, requests.Timeout) as e:
            if attempt == 5:
                raise
            time.sleep(delay + random.uniform(0, 2))
            delay = min(delay * 2, 60)
            continue
        if r.status_code == 401:
            auth.refresh()
            continue
        if r.status_code in (429, 500, 502, 503, 504):
            if attempt == 5:
                raise RuntimeError(f"{r.status_code}: {r.text[:150]}")
            time.sleep(delay + random.uniform(0, 2))
            delay = min(delay * 2, 60)
            continue
        return r
    raise RuntimeError(f"{method} {url} failed after retries")


def scan_index():
    idx = {}
    for p in SCANS.glob("*/scans/*"):
        idx.setdefault(p.name, p)
    return idx


def model_for(hand):
    return MODELS["hebrew"] if (hand or "").lower() == "hebrew" else MODELS["latin"]


def recognise(auth, image_path, htr_id, timeout_s=900):
    """One page through the Processing API. Returns (processId, content)."""
    body = {
        "config": {"textRecognition": {"htrId": htr_id}},
        "image": {"base64": base64.b64encode(image_path.read_bytes()).decode()},
    }
    r = _request("POST", PROC_URL, auth, json=body, timeout=300)
    if not r.ok:
        raise RuntimeError(f"submit failed {r.status_code}: {r.text[:200]}")
    pid = r.json().get("processId")

    waited = 0
    while waited < timeout_s:
        time.sleep(6)
        waited += 6
        pr = _request("GET", f"{PROC_URL}/{pid}", auth, timeout=60)
        try:
            st = pr.json()
        except ValueError:
            # An HTML error page rather than JSON: transient, keep polling
            # rather than throwing the page away.
            continue
        status = st.get("status")
        if status == "FINISHED":
            return pid, st.get("content") or {}
        if status in ("FAILED", "CANCELED"):
            raise RuntimeError(f"process {pid} {status}: {str(st)[:200]}")
    raise RuntimeError(f"process {pid} still running after {timeout_s}s")


def collect(only=None):
    out = []
    for f in sorted(DOCS.glob("*.json")):
        doc = json.loads(f.read_text(encoding="utf-8"))
        if only and not any(o in doc["doc_id"] for o in only):
            continue
        for p in (doc["panes"]["source"].get("pages") or []):
            t = p.get("triage") or {}
            if t.get("engine") == "transkribus":
                out.append((doc["doc_id"], p, t))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--docs", nargs="*")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--force", action="store_true",
                    help="re-run pages already transcribed")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    idx = scan_index()
    pages = collect(args.docs)
    if args.limit:
        pages = pages[:args.limit]

    if args.dry_run:
        for doc_id, p, t in pages:
            htr = model_for(t.get("hand_kind"))
            print(f"  {doc_id:26} p{p['page_no']:<5} {MODEL_NAMES[htr]}")
        print(f"\ndry run — {len(pages)} pages, nothing sent")
        return

    auth = Auth()
    rows, done, skipped, failed = [], 0, 0, 0
    for doc_id, p, t in pages:
        dest = OUT / doc_id
        txt_path = dest / f"{p['page_no']}.txt"
        if txt_path.exists() and not args.force:
            skipped += 1
            continue
        img = idx.get(p.get("scan_file") or "")
        if not img:
            print(f"  {doc_id} p{p['page_no']}: no scan on disk")
            failed += 1
            continue
        htr = model_for(t.get("hand_kind"))
        try:
            pid, content = recognise(auth, img, htr)
        except Exception as e:
            print(f"  {doc_id} p{p['page_no']}: {type(e).__name__} {str(e)[:120]}")
            failed += 1
            continue

        text = (content.get("text") or "").strip()
        dest.mkdir(parents=True, exist_ok=True)
        txt_path.write_text(text, encoding="utf-8")
        (dest / f"{p['page_no']}.json").write_text(
            json.dumps({"process_id": pid, "htr_id": htr,
                        "model": MODEL_NAMES[htr], "scan_file": img.name,
                        "content": content}, ensure_ascii=False, indent=1),
            encoding="utf-8")
        old = p["end"] - p["start"]
        rows.append([doc_id, p["page_no"], MODEL_NAMES[htr], t.get("hand_kind", ""),
                     p["grade"], old, len(text), pid])
        done += 1
        print(f"  {doc_id:26} p{p['page_no']:<5} {MODEL_NAMES[htr]:20} "
              f"{old:6} -> {len(text):6} chars")

    if rows:
        OUT.mkdir(parents=True, exist_ok=True)
        index = OUT / "index.tsv"
        new = not index.exists()
        with index.open("a", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh, delimiter="\t")
            if new:
                w.writerow(["doc_id", "page_no", "model", "hand",
                            "tesseract_grade", "tesseract_chars", "htr_chars",
                            "process_id"])
            w.writerows(rows)
    print(f"\n{done} transcribed, {skipped} already done, {failed} failed")
    print(f"  -> {OUT.relative_to(REPO)}  (not merged into the corpus)")


if __name__ == "__main__":
    main()
