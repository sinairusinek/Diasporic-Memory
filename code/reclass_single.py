"""Re-class a single item by o:id to a target class.

Usage:
    python code/reclass_single.py <o_id> <target_class_id>

Example:
    python code/reclass_single.py 3972 1028
"""
from __future__ import annotations
import json, os, sys, urllib.error, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UA = {"User-Agent": "jecke-cli/1.0"}


def env():
    if "OMEKA_BASE_URL" not in os.environ:
        for line in (ROOT / ".env").read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip().strip('"').strip("'")
    return (os.environ["OMEKA_BASE_URL"],
            os.environ["OMEKA_KEY_IDENTITY"],
            os.environ["OMEKA_KEY_CREDENTIAL"])


def auth_qs() -> str:
    _, ki, kc = env()
    return urllib.parse.urlencode({"key_identity": ki, "key_credential": kc})


def main():
    if len(sys.argv) != 3:
        print(__doc__); sys.exit(1)
    oid = int(sys.argv[1])
    target = int(sys.argv[2])
    base, _, _ = env()
    req = urllib.request.Request(f"{base}/items/{oid}?{auth_qs()}", headers=UA)
    cur = json.load(urllib.request.urlopen(req, timeout=30))
    body = {"o:resource_class": {"o:id": target}}
    for preserve in ("dcterms:identifier", "dcterms:isPartOf"):
        if cur.get(preserve):
            body[preserve] = cur[preserve]
    req = urllib.request.Request(
        f"{base}/items/{oid}?{auth_qs()}",
        data=json.dumps(body).encode(), method="PATCH",
        headers={**UA, "Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=30)
        print(f"o:id={oid} now class={target}")
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.read().decode('utf-8','replace')[:300]}")
        sys.exit(2)


if __name__ == "__main__":
    main()
