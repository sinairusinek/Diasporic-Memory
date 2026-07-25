"""Merge the 135 legacy folder-level duplicate pairs.

Strategy per pair (both o:ids < 5000):
- Keep the newer (higher o:id) — its Hebrew curated title is the canonical.
- PATCH it with anything the older has that the newer doesn't:
    * any property value (by @value+@language) the newer is missing
    * o:resource_class if newer has none
    * any item_set the newer doesn't already have
- Delete the older item.

Identifier handling: skip dcterms:identifier merging (both already have it;
they're paired by it).

Usage:
    python code/merge_legacy_dups.py --dry-run     # show diffs only
    python code/merge_legacy_dups.py               # do it
"""
from __future__ import annotations
import argparse, json, os, urllib.error, urllib.parse, urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UA = {"User-Agent": "jecke-cli/1.0"}

PROPERTY_KEY_RE = lambda k: ":" in k and not k.startswith("o:") and not k.startswith("@")
SKIP_PROPS = {"dcterms:identifier"}


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


def fetch_item(oid: int) -> dict:
    base, _, _ = env()
    req = urllib.request.Request(f"{base}/items/{oid}?{auth_qs()}", headers=UA)
    return json.load(urllib.request.urlopen(req, timeout=30))


def value_signature(v: dict) -> tuple:
    """Identity tuple so we can detect 'same value' across two items."""
    return (
        v.get("type"),
        v.get("@value"),
        v.get("@language"),
        v.get("value_resource_id"),
        v.get("@id"),
    )


def merge_into_newer(older: dict, newer: dict) -> tuple[dict, list[str]]:
    """Return (patch_body, diff_notes). patch_body has only the fields to send."""
    patch: dict = {}
    notes: list[str] = []

    # Property values
    for k, v in older.items():
        if not PROPERTY_KEY_RE(k):
            continue
        if k in SKIP_PROPS:
            continue
        if not isinstance(v, list):
            continue
        existing = newer.get(k, []) or []
        existing_sigs = {value_signature(x) for x in existing if isinstance(x, dict)}
        added = [x for x in v if isinstance(x, dict) and value_signature(x) not in existing_sigs]
        if added:
            patch[k] = existing + added
            for a in added:
                preview = (a.get("@value") or a.get("@id") or "").strip()
                lang = a.get("@language") or "-"
                notes.append(f"  + {k} (@{lang}): {preview[:60]}")

    # Resource class — only if newer lacks one
    if (older.get("o:resource_class") or {}).get("o:id") and not (newer.get("o:resource_class") or {}).get("o:id"):
        patch["o:resource_class"] = {"o:id": older["o:resource_class"]["o:id"]}
        notes.append(f"  + o:resource_class = {older['o:resource_class']['o:id']}")

    # Item sets — union
    older_sets = [s.get("o:id") for s in (older.get("o:item_set") or []) if s.get("o:id")]
    newer_sets = [s.get("o:id") for s in (newer.get("o:item_set") or []) if s.get("o:id")]
    extra_sets = [sid for sid in older_sets if sid not in newer_sets]
    if extra_sets:
        patch["o:item_set"] = [{"o:id": sid} for sid in newer_sets + extra_sets]
        notes.append(f"  + o:item_set adds {extra_sets}")

    return patch, notes


def patch_item(oid: int, body: dict) -> None:
    base, _, _ = env()
    req = urllib.request.Request(
        f"{base}/items/{oid}?{auth_qs()}",
        data=json.dumps(body).encode(),
        method="PATCH",
        headers={**UA, "Content-Type": "application/json"},
    )
    urllib.request.urlopen(req, timeout=30)


def delete_item(oid: int) -> None:
    base, _, _ = env()
    req = urllib.request.Request(
        f"{base}/items/{oid}?{auth_qs()}", method="DELETE", headers=UA)
    urllib.request.urlopen(req, timeout=30)


def collect_legacy_pairs() -> list[tuple[str, int, int]]:
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
    pairs = []
    for ident, ids in by_identifier.items():
        if len(ids) > 1 and max(ids) < 5000:
            ids = sorted(ids)
            pairs.append((ident, ids[0], ids[-1]))  # older, newer
    return pairs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    pairs = collect_legacy_pairs()
    print(f"Legacy pairs: {len(pairs)}")
    if args.limit:
        pairs = pairs[: args.limit]

    merged = patched = unchanged = deleted = failed = 0
    mapping: list[tuple[int, int]] = []  # (older, newer) for backlink rewrite
    for ident, older_id, newer_id in pairs:
        try:
            older = fetch_item(older_id)
            newer = fetch_item(newer_id)
        except Exception as e:
            print(f"{ident}: fetch failed: {e}")
            failed += 1
            continue
        patch_body, notes = merge_into_newer(older, newer)
        if args.dry_run:
            print(f"\n{ident}  ({older_id} -> {newer_id})")
            if notes:
                print("\n".join(notes))
            else:
                print("  (no diff to merge)")
            continue
        if patch_body:
            try:
                patch_item(newer_id, patch_body)
                patched += 1
            except Exception as e:
                print(f"{ident}: PATCH {newer_id} failed: {e}")
                failed += 1
                continue
        else:
            unchanged += 1
        try:
            delete_item(older_id)
            deleted += 1
            mapping.append((older_id, newer_id))
        except Exception as e:
            print(f"{ident}: DELETE {older_id} failed: {e}")
            failed += 1
        merged += 1

    print(f"\nProcessed: {merged}, patched: {patched}, unchanged: {unchanged}, "
          f"deleted: {deleted}, failed: {failed}")
    map_path = ROOT / "data/omeka-audit/legacy_merge_mapping.json"
    map_path.write_text(json.dumps(mapping))
    print(f"Mapping written to {map_path.relative_to(ROOT)} ({len(mapping)} pairs)")


if __name__ == "__main__":
    main()
