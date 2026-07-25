"""Retry the 10 legacy merges that failed with 422.

Reason for failure: Omeka validates resource-template required fields on PATCH;
since our patches only sent diffs, the identifier was missing from the body
even though it was set on the item, and validation rejected.

Fix: include the newer's dcterms:identifier and dcterms:isPartOf in every
PATCH, regardless of whether they changed.
"""
from __future__ import annotations
import json, os, urllib.error, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UA = {"User-Agent": "jecke-cli/1.0"}

# The 10 identifiers that failed
FAILED = [
    "IL-MTFN-001-G-F-0009-001",
    "IL-MTFN-001-G-F-0047-001",
    "IL-MTFN-001-G-F-0053-001",
    "IL-MTFN-001-G-F-0070-001",
    "IL-MTFN-001-G-F-0113-001",
    "IL-MTFN-001-G-F-0186-001",
    "IL-MTFN-001-G-F-0353-001",
    "IL-MTFN-001-G-F-0390-001",
    "IL-MTFN-001-G-F-0414-001",
    "IL-MTFN-001-G-F-0490-001",
]
PRESERVE = {"dcterms:identifier", "dcterms:isPartOf"}


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


def value_signature(v: dict) -> tuple:
    return (v.get("type"), v.get("@value"), v.get("@language"),
            v.get("value_resource_id"), v.get("@id"))


def find_pair(ident: str) -> tuple[dict, dict] | None:
    base, _, _ = env()
    qs = auth_qs() + "&" + urllib.parse.urlencode({
        "property[0][property]": "10",
        "property[0][type]": "eq",
        "property[0][text]": ident,
    })
    req = urllib.request.Request(f"{base}/items?{qs}", headers=UA)
    items = json.load(urllib.request.urlopen(req, timeout=30))
    if len(items) != 2:
        print(f"  {ident}: found {len(items)} items, expected 2")
        return None
    items.sort(key=lambda x: x["o:id"])
    return items[0], items[-1]


def merge_with_preserve(older: dict, newer: dict) -> dict:
    patch: dict = {}

    # ALWAYS preserve the newer's required fields
    for k in PRESERVE:
        if newer.get(k):
            patch[k] = newer[k]

    for k, v in older.items():
        if ":" not in k or k.startswith("o:") or k.startswith("@") or k in PRESERVE:
            continue
        if not isinstance(v, list):
            continue
        existing = newer.get(k, []) or []
        existing_sigs = {value_signature(x) for x in existing if isinstance(x, dict)}
        added = [x for x in v if isinstance(x, dict) and value_signature(x) not in existing_sigs]
        if added:
            patch[k] = existing + added
        elif k in newer:
            # Re-affirm to satisfy any required check
            patch[k] = existing

    if (older.get("o:resource_class") or {}).get("o:id") and not (newer.get("o:resource_class") or {}).get("o:id"):
        patch["o:resource_class"] = {"o:id": older["o:resource_class"]["o:id"]}

    older_sets = [s.get("o:id") for s in (older.get("o:item_set") or []) if s.get("o:id")]
    newer_sets = [s.get("o:id") for s in (newer.get("o:item_set") or []) if s.get("o:id")]
    extra_sets = [sid for sid in older_sets if sid not in newer_sets]
    if extra_sets:
        patch["o:item_set"] = [{"o:id": sid} for sid in newer_sets + extra_sets]

    return patch


def patch_item(oid: int, body: dict) -> None:
    base, _, _ = env()
    req = urllib.request.Request(
        f"{base}/items/{oid}?{auth_qs()}",
        data=json.dumps(body).encode(),
        method="PATCH",
        headers={**UA, "Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=30)


def delete_item(oid: int) -> None:
    base, _, _ = env()
    req = urllib.request.Request(
        f"{base}/items/{oid}?{auth_qs()}", method="DELETE", headers=UA)
    urllib.request.urlopen(req, timeout=30)


def main():
    succeeded = failed = 0
    new_pairs: list[tuple[int, int]] = []
    for ident in FAILED:
        pair = find_pair(ident)
        if not pair:
            failed += 1
            continue
        older, newer = pair
        try:
            patch_body = merge_with_preserve(older, newer)
            patch_item(newer["o:id"], patch_body)
            delete_item(older["o:id"])
            new_pairs.append((older["o:id"], newer["o:id"]))
            print(f"{ident}: merged {older['o:id']} -> {newer['o:id']}")
            succeeded += 1
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:400]
            print(f"{ident}: HTTP {e.code}: {body}")
            failed += 1

    if new_pairs:
        map_path = ROOT / "data/omeka-audit/legacy_merge_mapping.json"
        existing = json.loads(map_path.read_text()) if map_path.exists() else []
        existing.extend(new_pairs)
        map_path.write_text(json.dumps(existing))
        print(f"Appended {len(new_pairs)} pairs to mapping (total {len(existing)})")

    print(f"\nSucceeded: {succeeded}, failed: {failed}")


if __name__ == "__main__":
    main()
