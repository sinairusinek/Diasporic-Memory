"""Part (a) — Transkribus HTR via the NEW Processing API (base64, server-to-server).

The old TrpServer job-trigger endpoints are gone; Transkribus moved recognition to
https://transkribus.eu/processing/v1 (OAuth2). This posts each page image as base64,
polls, and writes the transcription — no local-context cost, no TrpServer upload dance.

Env: TRANSKRIBUS_USER, TRANSKRIBUS_PASS
Models: 50870 German Giant I | 265149 German Genius | 399677 Modern-Hebrew | 579509 Text Titan II

Usage:
  python code/recatalog/transkribus_htr.py --folder 0047-4 --pages 24,25,32,33,40 --model 50870
Writes: data/recatalog/<folder>/ocr_transkribus/<page>.txt
"""
from __future__ import annotations
import argparse, base64, glob, os, re, socket, subprocess, sys, time
import requests

OAUTH = "https://account.readcoop.eu/auth/realms/readcoop/protocol/openid-connect/token"
API = "https://transkribus.eu/processing/v1"


def _dns_workaround(host: str) -> None:
    """macOS mDNSResponder sometimes negative-caches transkribus.eu while direct DNS
    queries succeed. If getaddrinfo fails, resolve via nslookup and pin the mapping."""
    try:
        socket.getaddrinfo(host, 443)
        return
    except socket.gaierror:
        pass
    out = subprocess.run(["nslookup", "-type=A", host], capture_output=True, text=True).stdout
    m = re.search(r"Name:\s*" + re.escape(host) + r"\s*\nAddress:\s*([0-9.]+)", out)
    if not m:
        sys.exit(f"cannot resolve {host} (getaddrinfo AND nslookup failed)")
    ip, orig = m.group(1), socket.getaddrinfo
    socket.getaddrinfo = lambda h, *a, **k: orig(ip if h == host else h, *a, **k)
    print(f"[dns workaround] {host} -> {ip}")


def token() -> str:
    r = requests.post(OAUTH, data={"grant_type": "password",
        "username": os.environ["TRANSKRIBUS_USER"], "password": os.environ["TRANSKRIBUS_PASS"],
        "client_id": "processing-api-client"}, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


def parse_pages(spec: str) -> list[int]:
    out = []
    for part in spec.split(","):
        if "-" in part:
            a, b = part.split("-", 1); out += list(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return out


def submit(h, img_path, model_id) -> int:
    b64 = base64.b64encode(open(img_path, "rb").read()).decode()
    body = {"config": {"textRecognition": {"htrId": model_id}}, "image": {"base64": b64}}
    r = requests.post(f"{API}/processes", headers=h, json=body, timeout=120)
    r.raise_for_status()
    return r.json()["processId"]


def poll(h, pid, timeout_s=600) -> str:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        try:
            j = requests.get(f"{API}/processes/{pid}", headers=h, timeout=30).json()
        except Exception:
            # tokens expire mid-run and the API then returns non-JSON — refresh and retry
            h["Authorization"] = f"Bearer {token()}"
            time.sleep(4)
            continue
        st = j.get("status")
        if st in ("FINISHED", "COMPLETED"):
            return (j.get("content") or {}).get("text", "")
        if st in ("FAILED", "CANCELED"):
            return f"__{st}__"
        time.sleep(8)
    return "__TIMEOUT__"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", required=True)
    ap.add_argument("--pages", required=True)
    ap.add_argument("--model", type=int, default=50870)
    args = ap.parse_args()

    _dns_workaround("transkribus.eu")
    h = {"Authorization": f"Bearer {token()}", "Content-Type": "application/json"}
    out_dir = f"data/recatalog/{args.folder}/ocr_transkribus"
    os.makedirs(out_dir, exist_ok=True)
    scans = f"data/recatalog/{args.folder}/scans"

    jobs = []
    for p in parse_pages(args.pages):
        m = glob.glob(f"{scans}/*_{p:04d}.jpg")
        if not m:
            print(f"p{p}: no image"); continue
        try:
            pid = submit(h, m[0], args.model)
        except Exception:
            h["Authorization"] = f"Bearer {token()}"
            pid = submit(h, m[0], args.model)
        jobs.append((p, pid))
        print(f"p{p}: submitted process {pid}")

    for p, pid in jobs:
        txt = poll(h, pid)
        open(f"{out_dir}/{p:04d}.txt", "w").write(txt)
        n = 0 if txt.startswith("__") else len(txt)
        print(f"p{p}: {n} chars -> {out_dir}/{p:04d}.txt  {'('+txt+')' if txt.startswith('__') else ''}")


if __name__ == "__main__":
    main()
