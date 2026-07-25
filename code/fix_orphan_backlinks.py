"""Rewrite dcterms:hasPart / dcterms:isPartOf URLs that point to deleted
older items so they point at their surviving merge partner.

Uses data/omeka-audit/legacy_merge_mapping.json as the rewrite table.
"""
from __future__ import annotations
import argparse, json, os, urllib.error, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UA = {"User-Agent": "jecke-cli/1.0"}
MAP_FILE = ROOT / "data/omeka-audit/legacy_merge_mapping.json"
LINK_PROPS = ("dcterms:hasPart", "dcterms:isPartOf", "dcterms:relation",
              "dcterms:isReferencedBy", "dcterms:references")


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


def rewrite_value(v, redirect: dict[int, int], base_url: str) -> tuple[dict, bool]:
    """If v is a resource-value (or URI) pointing at an old id, rewrite to new id."""
    if not isinstance(v, dict):
        return v, False

    # Case A: value_resource_id (proper Omeka resource link)
    rid = v.get("value_resource_id")
    if isinstance(rid, int) and rid in redirect:
        new = dict(v)
        new["value_resource_id"] = redirect[rid]
        # Strip stale embedded snapshot fields if present
        for k in ("@id", "url", "display_title", "value_resource_name"):
            new.pop(k, None)
        return new, True

    # Case B: URI value with @id like https://.../api/items/1809
    aid = v.get("@id") or v.get("o:value_resource", {}).get("@id")
    if isinstance(aid, str):
        prefix = f"{base_url}/items/"
        if aid.startswith(prefix):
            try:
                old_id = int(aid[len(prefix):].split("?", 1)[0].rstrip("/"))
            except ValueError:
                return v, False
            if old_id in redirect:
                new = dict(v)
                new["@id"] = f"{base_url}/items/{redirect[old_id]}"
                return new, True
    return v, False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    base, _, _ = env()
    mapping = json.loads(MAP_FILE.read_text())
    redirect: dict[int, int] = {old: new for old, new in mapping}
    print(f"Loaded {len(redirect)} id redirects")

    # Scan all items and collect candidates for rewrite
    candidates: list[tuple[int, dict]] = []
    page = 1
    while True:
        q = auth_qs() + "&" + urllib.parse.urlencode({"per_page": 100, "page": page})
        req = urllib.request.Request(f"{base}/items?{q}", headers=UA)
        data = json.load(urllib.request.urlopen(req, timeout=60))
        if not data:
            break
        for it in data:
            patch: dict = {}
            changed_any = False
            for prop in LINK_PROPS:
                values = it.get(prop)
                if not isinstance(values, list):
                    continue
                new_values = []
                local_changed = False
                for v in values:
                    rv, ch = rewrite_value(v, redirect, base)
                    new_values.append(rv)
                    local_changed = local_changed or ch
                if local_changed:
                    patch[prop] = new_values
                    changed_any = True
            if changed_any:
                candidates.append((it["o:id"], patch))
        if len(data) < 100:
            break
        page += 1

    print(f"Items needing rewrite: {len(candidates)}")
    if args.dry_run:
        for oid, patch in candidates[:10]:
            print(f"  o:id={oid}: props {list(patch.keys())}")
        return

    # Patch each — include identifier to satisfy required-field validation
    succeeded = failed = 0
    for oid, patch in candidates:
        # Fetch the item to know its identifier; re-add it to the patch
        try:
            req = urllib.request.Request(f"{base}/items/{oid}?{auth_qs()}", headers=UA)
            cur = json.load(urllib.request.urlopen(req, timeout=30))
            for preserve in ("dcterms:identifier", "dcterms:isPartOf"):
                if preserve not in patch and cur.get(preserve):
                    patch[preserve] = cur[preserve]
        except Exception as e:
            print(f"  o:id={oid}: prefetch failed: {e}")
            failed += 1
            continue

        try:
            body = json.dumps(patch).encode()
            req = urllib.request.Request(
                f"{base}/items/{oid}?{auth_qs()}",
                data=body, method="PATCH",
                headers={**UA, "Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=30)
            succeeded += 1
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:300]
            print(f"  o:id={oid}: HTTP {e.code}: {body}")
            failed += 1

    print(f"Succeeded: {succeeded}, failed: {failed}")


if __name__ == "__main__":
    main()
