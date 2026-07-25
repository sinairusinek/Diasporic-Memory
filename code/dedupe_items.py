"""Find dcterms:identifier values with >1 item and delete duplicates by policy.

Default policy: keep newest (highest o:id), only for safe pair patterns:
- session pair (both o:id >= 7630): safe — identical re-ingest dups
- old + 6000s (old < 5000, new 6000-7629): safe — newer has item_set the older lacks

Skipped by default:
- both <5000 — pre-existing legacy duplicates (folder-level metadata from
  earlier ingestions); leave to user judgment.

Use --include-legacy to dedupe those too (keeps newest).

Usage:
    python code/dedupe_items.py --dry-run
    python code/dedupe_items.py                 # safe pairs only
    python code/dedupe_items.py --include-legacy
"""
from __future__ import annotations
import argparse, json, os, urllib.error, urllib.parse, urllib.request
from collections import defaultdict
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


def classify(ids: list[int]) -> str:
    lo, hi = min(ids), max(ids)
    if lo >= 7630:                 return "session"
    if lo < 5000 and 6000 <= hi < 7630:  return "old-vs-2025"
    if hi < 5000:                  return "legacy"
    return "other"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--include-legacy", action="store_true")
    args = ap.parse_args()

    base, _, _ = env()
    by_identifier: dict[str, list[int]] = defaultdict(list)
    page = 1
    while True:
        q = auth_qs() + "&" + urllib.parse.urlencode({"per_page": 100, "page": page})
        req = urllib.request.Request(f"{base}/items?{q}", headers=UA)
        data = json.load(urllib.request.urlopen(req, timeout=60))
        if not data:
            break
        for it in data:
            for v in (it.get("dcterms:identifier") or []):
                if isinstance(v, dict) and "@value" in v:
                    by_identifier[v["@value"]].append(it["o:id"])
        if len(data) < 100:
            break
        page += 1

    dups = {k: sorted(v) for k, v in by_identifier.items() if len(v) > 1}
    safe_classes = {"session", "old-vs-2025", "other"}
    if args.include_legacy:
        safe_classes.add("legacy")

    targets = []
    skipped_legacy = 0
    for ident, ids in dups.items():
        cls = classify(ids)
        if cls == "legacy" and not args.include_legacy:
            skipped_legacy += 1
            continue
        if cls not in safe_classes:
            continue
        keep = max(ids)
        for oid in ids:
            if oid != keep:
                targets.append((ident, oid, cls))

    print(f"Duplicate identifiers: {len(dups)}, safe to delete now: {len(targets)}, "
          f"legacy skipped: {skipped_legacy}")
    if args.dry_run:
        for t in targets[:10]:
            print("  ", t)
        return

    deleted = failed = 0
    for ident, oid, cls in targets:
        q = auth_qs()
        req = urllib.request.Request(f"{base}/items/{oid}?{q}", method="DELETE", headers=UA)
        try:
            urllib.request.urlopen(req, timeout=30)
            deleted += 1
        except urllib.error.HTTPError as e:
            print(f"  delete o:id={oid} ({ident}) FAILED HTTP {e.code}")
            failed += 1
    print(f"Deleted={deleted}, failed={failed}")


if __name__ == "__main__":
    main()
