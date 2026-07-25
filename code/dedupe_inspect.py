"""Inspect duplicate pairs in Omeka to inform a safe dedupe policy.

Groups duplicates by id-range pattern, samples a few from each group, and
reports per-item: media count, item-set membership, resource class, count of
non-empty properties, and whether key fields differ between older/newer.
"""
from __future__ import annotations
import json, os, urllib.parse, urllib.request
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


def fetch_item(oid: int) -> dict:
    base, _, _ = env()
    req = urllib.request.Request(f"{base}/items/{oid}?{auth_qs()}", headers=UA)
    return json.load(urllib.request.urlopen(req, timeout=30))


def summarize(it: dict) -> dict:
    nonempty_props = sum(
        1 for k, v in it.items()
        if ":" in k and isinstance(v, list) and any(x.get("@value") or x.get("@id") for x in v)
    )
    return {
        "id": it["o:id"],
        "created": it.get("o:created", {}).get("@value", ""),
        "media": len(it.get("o:media", []) or []),
        "item_sets": [s.get("o:id") for s in (it.get("o:item_set") or [])],
        "template": (it.get("o:resource_template") or {}).get("o:id"),
        "class": (it.get("o:resource_class") or {}).get("o:id"),
        "nonempty_props": nonempty_props,
        "title": (it.get("dcterms:title") or [{}])[0].get("@value", "")[:60],
    }


def main():
    base, _, _ = env()

    # Re-scan to find duplicates
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
    print(f"{len(dups)} identifiers with duplicates")

    # Classify pairs by id-range pattern of older vs newer
    def bucket(oid: int) -> str:
        if oid < 5000: return "<5000"
        if oid < 6000: return "5000s"
        if oid < 7000: return "6000s"
        if oid < 7630: return "early-7000s"
        return "session-7000s"
    by_pattern: dict[tuple[str, str], list[tuple[str, list[int]]]] = defaultdict(list)
    for ident, ids in dups.items():
        old, new = ids[0], ids[-1]
        by_pattern[(bucket(old), bucket(new))].append((ident, ids))

    print("\nPair patterns (older-bucket, newer-bucket) -> count:")
    for pat, group in sorted(by_pattern.items(), key=lambda x: -len(x[1])):
        print(f"  {pat[0]:>16} + {pat[1]:>16}  ->  {len(group)}")

    print("\nSampling up to 3 per pattern:")
    for pat, group in sorted(by_pattern.items(), key=lambda x: -len(x[1])):
        print(f"\n=== {pat[0]} + {pat[1]} (n={len(group)}) ===")
        for ident, ids in group[:3]:
            print(f"\n  identifier: {ident}")
            for oid in ids:
                it = fetch_item(oid)
                s = summarize(it)
                print(f"    o:id={s['id']}  created={s['created']}")
                print(f"      media={s['media']}  sets={s['item_sets']}  "
                      f"template={s['template']}  class={s['class']}  "
                      f"nonempty_props={s['nonempty_props']}")
                print(f"      title: {s['title']}")


if __name__ == "__main__":
    main()
