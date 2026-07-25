"""Post-bulk-ingest cleanup.

1. Add the secondary item set to the 2 composite-class items.
2. Delete the junk item set 7645.
3. Refresh data/omeka-audit/omeka_all_identifiers.txt by pulling all
   dcterms:identifier values from Omeka.
4. Diff against TSV item_ids to report what's still missing.

Usage:
    python code/post_ingest_cleanup.py            # do all steps
    python code/post_ingest_cleanup.py composite  # just composite
    python code/post_ingest_cleanup.py junkset    # just delete 7645
    python code/post_ingest_cleanup.py verify     # just refresh + diff
"""
from __future__ import annotations
import csv, json, os, sys, urllib.error, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TSV = ROOT / "data/JeckeArchive/Jecke-items.tsv"
EXTRAS = ROOT / "data/omeka-audit/csv-import/composite_extras.tsv"
ALL_IDS = ROOT / "data/omeka-audit/omeka_all_identifiers.txt"
MISSING = ROOT / "data/omeka-audit/open_records_missing_from_omeka.txt"
STILL_MISSING = ROOT / "data/omeka-audit/still_missing_after_ingest.txt"
UA = {"User-Agent": "jecke-cli/1.0"}


def env():
    # Load .env if needed
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


def find_item_by_identifier(identifier: str) -> dict | None:
    base, _, _ = env()
    q = auth_qs() + "&" + urllib.parse.urlencode({
        "property[0][property]": "10",
        "property[0][type]": "eq",
        "property[0][text]": identifier,
    })
    req = urllib.request.Request(f"{base}/items?{q}", headers=UA)
    d = json.load(urllib.request.urlopen(req, timeout=30))
    return d[0] if d else None


def add_item_set(item: dict, set_id: int) -> bool:
    """PATCH the item to add an item_set, preserving existing sets."""
    base, _, _ = env()
    current = item.get("o:item_set", [])
    if any(s.get("o:id") == set_id for s in current):
        return False  # already there
    new_sets = current + [{"o:id": set_id}]
    body = json.dumps({"o:item_set": new_sets}).encode()
    req = urllib.request.Request(
        f"{base}/items/{item['o:id']}?{auth_qs()}",
        data=body, method="PATCH",
        headers={**UA, "Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=30)
    return True


def step_composite():
    print("== Step: composite extras ==")
    with EXTRAS.open() as f:
        reader = csv.DictReader(f, delimiter="\t")
        rows = list(reader)
    for r in rows:
        iid = r["item_id"]; extra = int(r["extra_item_set_id"])
        item = find_item_by_identifier(iid)
        if not item:
            print(f"  {iid}: NOT FOUND in Omeka")
            continue
        try:
            changed = add_item_set(item, extra)
            print(f"  {iid} (o:id={item['o:id']}): "
                  f"{'added set ' + str(extra) if changed else 'already in set ' + str(extra)}")
        except urllib.error.HTTPError as e:
            print(f"  {iid}: PATCH HTTP {e.code}")


def step_junkset():
    print("== Step: delete junk item set 7645 ==")
    base, _, _ = env()
    req = urllib.request.Request(
        f"{base}/item_sets/7645?{auth_qs()}", method="DELETE", headers=UA)
    try:
        urllib.request.urlopen(req, timeout=30)
        print("  deleted 7645")
    except urllib.error.HTTPError as e:
        print(f"  DELETE 7645: HTTP {e.code}")


def step_verify():
    print("== Step: refresh identifiers + diff ==")
    base, _, _ = env()
    ids: set[str] = set()
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
                    ids.add(v["@value"])
        page += 1
        if len(data) < 100:
            break
    ALL_IDS.write_text("\n".join(sorted(ids)))
    print(f"  Omeka now has {len(ids)} distinct dcterms:identifier values")

    tsv_ids: set[str] = set()
    with TSV.open(encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            tsv_ids.add(row["item_id"])
    print(f"  TSV has {len(tsv_ids)} item_ids")

    originally_missing = set(MISSING.read_text().splitlines())
    still_missing = originally_missing - ids
    STILL_MISSING.write_text("\n".join(sorted(still_missing)))
    print(f"  Originally missing: {len(originally_missing)}")
    print(f"  Still missing after ingest: {len(still_missing)} "
          f"(written to {STILL_MISSING.relative_to(ROOT)})")


def main():
    steps = sys.argv[1:] or ["composite", "junkset", "verify"]
    for s in steps:
        fn = {"composite": step_composite, "junkset": step_junkset, "verify": step_verify}.get(s)
        if not fn:
            print(f"Unknown step: {s}"); continue
        fn()
        print()


if __name__ == "__main__":
    main()
