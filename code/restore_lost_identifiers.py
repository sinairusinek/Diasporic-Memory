"""Restore dcterms:identifier on legacy-merge keepers that lost it.

Background: the first merge run's PATCH erased dcterms:identifier on 125 of
135 keepers (Omeka PATCH semantics quirk; the body didn't re-include the
identifier even though it was present on the item). The 10 retried merges
explicitly preserved identifier and were fine.

Strategy:
For each (older_id, newer_id) in legacy_merge_mapping.json:
  1. Fetch newer; if it already has dcterms:identifier, skip.
  2. Derive parent identifier from a hasPart child:
     - Look at dcterms:hasPart values. Take the first resource link.
     - Fetch that child. Read its dcterms:identifier.
     - Strip the trailing -MMM(-RKKKK) suffix to get the parent identifier.
  3. PATCH newer with the restored identifier + preserve isPartOf to satisfy
     template-required-field validation.

Usage:
    python code/restore_lost_identifiers.py --dry-run
    python code/restore_lost_identifiers.py
"""
from __future__ import annotations
import argparse, json, os, re, urllib.error, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UA = {"User-Agent": "jecke-cli/1.0"}
MAP_FILE = ROOT / "data/omeka-audit/legacy_merge_mapping.json"
PARENT_RE = re.compile(r"^(IL-MTFN-001-G-F-\d{4})(?:-\d+(?:-R\d+)?)?$")


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


def parent_from_child_identifier(child_ident: str) -> str | None:
    m = PARENT_RE.match(child_ident or "")
    return m.group(1) if m else None


def child_o_id_from_haspart_value(v: dict, base: str) -> int | None:
    """Extract child o:id from a hasPart value, either as value_resource_id or @id URL."""
    rid = v.get("value_resource_id")
    if isinstance(rid, int):
        return rid
    aid = v.get("@id") or (v.get("o:value_resource") or {}).get("@id")
    if isinstance(aid, str):
        prefix = f"{base}/items/"
        if aid.startswith(prefix):
            try:
                return int(aid[len(prefix):].split("?", 1)[0].rstrip("/"))
            except ValueError:
                return None
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    base, _, _ = env()
    mapping = json.loads(MAP_FILE.read_text())

    needs_restore = []  # (newer_id, derived_identifier)
    skipped_have = skipped_undecodable = 0
    for older_id, newer_id in mapping:
        try:
            newer = fetch_item(newer_id)
        except Exception as e:
            print(f"  o:id={newer_id}: fetch failed: {e}")
            continue
        existing_idents = [v.get("@value") for v in (newer.get("dcterms:identifier") or [])
                           if isinstance(v, dict) and v.get("@value")]
        if existing_idents:
            skipped_have += 1
            continue
        parts = newer.get("dcterms:hasPart") or []
        derived = None
        for v in parts:
            if not isinstance(v, dict):
                continue
            child_id = child_o_id_from_haspart_value(v, base)
            if not child_id:
                continue
            try:
                child = fetch_item(child_id)
            except Exception:
                continue
            child_ident = ""
            for cv in (child.get("dcterms:identifier") or []):
                if isinstance(cv, dict) and cv.get("@value"):
                    child_ident = cv["@value"]
                    break
            parent = parent_from_child_identifier(child_ident)
            if parent:
                derived = parent
                break
        if derived:
            needs_restore.append((newer_id, derived))
        else:
            skipped_undecodable += 1
            print(f"  o:id={newer_id}: could not derive identifier from hasPart")

    print(f"\nKeepers already with identifier (skipped): {skipped_have}")
    print(f"Keepers undecodable (skipped): {skipped_undecodable}")
    print(f"Keepers to restore: {len(needs_restore)}")
    if args.dry_run:
        for oid, ident in needs_restore[:10]:
            print(f"  would PATCH o:id={oid} identifier={ident}")
        return

    succ = fail = 0
    for newer_id, derived in needs_restore:
        try:
            cur = fetch_item(newer_id)
        except Exception as e:
            print(f"  o:id={newer_id}: refetch failed: {e}")
            fail += 1
            continue
        body = {
            "dcterms:identifier": [
                {"type": "literal", "property_id": 10, "@value": derived}
            ],
        }
        if cur.get("dcterms:isPartOf"):
            body["dcterms:isPartOf"] = cur["dcterms:isPartOf"]
        try:
            req = urllib.request.Request(
                f"{base}/items/{newer_id}?{auth_qs()}",
                data=json.dumps(body).encode(), method="PATCH",
                headers={**UA, "Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=30)
            succ += 1
        except urllib.error.HTTPError as e:
            print(f"  o:id={newer_id}: HTTP {e.code}")
            fail += 1
    print(f"Restored: {succ}, failed: {fail}")


if __name__ == "__main__":
    main()
