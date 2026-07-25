"""Re-class all items currently using bibo:Series (83) to arkivo:File (1026).

arkivo:File's label has been renamed to 'Folder' so the badge will display
'Folder' on the public site while the underlying URI stays archival-correct.
"""
from __future__ import annotations
import json, os, urllib.error, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UA = {"User-Agent": "jecke-cli/1.0"}
OLD_CLASS = 83    # bibo:Series
NEW_CLASS = 1026  # arkivo:File (relabeled "Folder")


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
    base, _, _ = env()
    # Collect all items with old class
    item_ids: list[int] = []
    page = 1
    while True:
        q = auth_qs() + "&" + urllib.parse.urlencode({
            "resource_class_id": OLD_CLASS, "per_page": 100, "page": page})
        req = urllib.request.Request(f"{base}/items?{q}", headers=UA)
        data = json.load(urllib.request.urlopen(req, timeout=60))
        if not data:
            break
        for it in data:
            item_ids.append(it["o:id"])
            # Stash identifier+isPartOf for the PATCH (avoids required-field 422)
        if len(data) < 100:
            break
        page += 1
    print(f"Found {len(item_ids)} items to re-class")

    succeeded = failed = 0
    for i, oid in enumerate(item_ids):
        # Fetch identifier+isPartOf to preserve in PATCH
        try:
            req = urllib.request.Request(f"{base}/items/{oid}?{auth_qs()}", headers=UA)
            cur = json.load(urllib.request.urlopen(req, timeout=30))
        except Exception as e:
            print(f"  o:id={oid}: fetch failed: {e}")
            failed += 1
            continue
        body = {"o:resource_class": {"o:id": NEW_CLASS}}
        for preserve in ("dcterms:identifier", "dcterms:isPartOf"):
            if cur.get(preserve):
                body[preserve] = cur[preserve]
        try:
            req = urllib.request.Request(
                f"{base}/items/{oid}?{auth_qs()}",
                data=json.dumps(body).encode(), method="PATCH",
                headers={**UA, "Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=30)
            succeeded += 1
        except urllib.error.HTTPError as e:
            print(f"  o:id={oid}: HTTP {e.code}")
            failed += 1
        if (i + 1) % 100 == 0:
            print(f"  ... {i+1}/{len(item_ids)} processed")

    print(f"Re-classed: {succeeded}, failed: {failed}")


if __name__ == "__main__":
    main()
