"""Push recatalog-pipeline records (catalog.tsv) into Omeka S.

Per folder, reads:
  data/recatalog/<folder>/catalog.tsv     (segmented documents, trilingual)
  data/recatalog/<folder>/omeka_map.tsv   (doc_id -> legacy item_id | NEW)

For docs mapped to a legacy item: enrich the existing Omeka item with a
Drive deep-link (dcterms:source URI labelled with the page range) via
GET-modify-PUT (NEVER PATCH — it erases omitted fields). Idempotent: an
identical URI+label already present is skipped.

For docs marked NEW: create an item (EgoDocument template) with trilingual
descriptions, minting the next free R#### under the folder's legacy prefix.

Usage:
  python code/ingest_recatalog.py --folder 0047-2 --prefix IL-MTFN-001-G-F-0047-002 \
      --drive-url https://drive.google.com/drive/folders/XXX [--dry-run]
"""
from __future__ import annotations
import argparse, csv, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from omeka import Omeka

ROOT = Path(__file__).resolve().parent.parent
SITE_ID = 1
CLASS_MAP_FILE = ROOT / "data/omeka-audit/class_map.json"

PROPS = {  # must match create_templates.py / ingest_jecke.py
    "dcterms:title": 1, "dcterms:identifier": 10, "dcterms:source": 11,
    "dcterms:isPartOf": 33,
    "ric-o:generalDescription": 3502, "ric-o:hasAuthor": 3139,
    "ric-o:hasOrHadLanguage": 3201, "ric-o:hasDocumentaryFormType": 3163,
    "ric-o:hasCreationDate": 3150, "bibo:pages": 112,
}


def lit(prop, value, lang=None):
    out = {"type": "literal", "property_id": PROPS[prop], "@value": value}
    if lang:
        out["@language"] = lang
    return out


def uri(prop, url, label):
    return {"type": "uri", "property_id": PROPS[prop], "@id": url, "o:label": label}


def drive_label(row, folder):
    return f"Scans pp.{row['page_range']}, Drive folder IL-MTFN-001-G-F-{folder}"


def find_by_identifier(om, identifier):
    hits = om.get("items", **{
        "property[0][property]": PROPS["dcterms:identifier"],
        "property[0][type]": "eq", "property[0][text]": identifier})
    return hits[0] if hits else None


def enrich(om, item, url, label, dry):
    existing = item.get("dcterms:source", [])
    if any(v.get("@id") == url and v.get("o:label") == label for v in existing):
        return "already"
    body = dict(item)  # full representation -> safe PUT
    body["dcterms:source"] = existing + [uri("dcterms:source", url, label)]
    if not dry:
        om.put(f"items/{item['o:id']}", body)
    return "enriched"


def build_new(row, identifier, prefix, class_map, url, label):
    spec = class_map["EgoDocument"]
    payload = {
        "@type": "o:Item", "o:is_public": True,
        "o:resource_template": {"o:id": spec["template_id"]},
        "o:item_set": [{"o:id": spec["item_set_id"]}],
        "o:site": [{"o:id": SITE_ID}],
        "o:resource_class": {"o:id": spec["resource_class_id"]},
    }

    def add(prop, value, lang=None):
        v = (value or "").strip()
        if v:
            payload.setdefault(prop, []).append(lit(prop, v, lang))

    add("dcterms:identifier", identifier)
    add("dcterms:isPartOf", prefix)
    add("dcterms:title", row.get("title"))
    add("ric-o:generalDescription", row.get("description_he"), "he")
    add("ric-o:generalDescription", row.get("description_de"), "de")
    add("ric-o:generalDescription", row.get("description_en"), "en")
    add("ric-o:hasAuthor", row.get("from_person"))
    add("ric-o:hasOrHadLanguage", row.get("languages"))
    add("ric-o:hasDocumentaryFormType", row.get("doc_type"))
    add("ric-o:hasCreationDate", row.get("date_text"))
    add("bibo:pages", row.get("page_range"))
    payload.setdefault("dcterms:source", []).append(uri("dcterms:source", url, label))
    return payload


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", required=True)
    ap.add_argument("--prefix", required=True, help="legacy sub-series id, e.g. IL-MTFN-001-G-F-0047-002")
    ap.add_argument("--drive-url", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    d = ROOT / "data/recatalog" / args.folder
    rows = {r["doc_id"]: r for r in csv.DictReader(open(d / "catalog.tsv"), delimiter="\t")}
    mapping = {r["doc_id"]: r for r in csv.DictReader(open(d / "omeka_map.tsv"), delimiter="\t")}
    class_map = json.loads(CLASS_MAP_FILE.read_text())
    om = Omeka()

    # next free R#### under prefix: after max of (legacy TSV numbering, live Omeka,
    # ids referenced in the map) — legacy ids exist even when absent from Omeka
    n = 0
    legacy_tsv = ROOT / "data/JeckeArchive/Jecke-items.tsv"
    for r in csv.DictReader(open(legacy_tsv), delimiter="\t"):
        iid = r.get("item_id") or ""
        if iid.startswith(args.prefix + "-R"):
            n = max(n, int(iid.rsplit("-R", 1)[1]))
    for m in mapping.values():
        if m["legacy_item_id"].startswith(args.prefix + "-R"):
            n = max(n, int(m["legacy_item_id"].rsplit("-R", 1)[1]))
    n += 1
    while find_by_identifier(om, f"{args.prefix}-R{n:04d}"):
        n += 1

    stats = {"enriched": 0, "already": 0, "created": 0, "errors": 0}
    cache = {}  # legacy_id -> live item (fetch once even when several docs map to it)
    for doc_id, row in rows.items():
        m = mapping.get(doc_id)
        if m is None:
            print(f"WARN {doc_id}: no row in omeka_map.tsv, skipped"); continue
        label = drive_label(row, args.folder)
        try:
            if m["legacy_item_id"] != "NEW":
                legacy = m["legacy_item_id"]
                if legacy not in cache:
                    item = find_by_identifier(om, legacy)
                    if item is None:
                        # legacy record never made it into Omeka — create it under its own id
                        payload = build_new(row, legacy, args.prefix, class_map, args.drive_url, label)
                        if args.dry_run:
                            print(f"DRY-NEW  {doc_id} -> {legacy} (legacy id absent from Omeka)")
                        else:
                            r = om.post("items", payload)
                            print(f"CREATED  {doc_id} -> {legacy} (legacy id was absent, o:id={r['o:id']})")
                            cache[legacy] = om.get(f"items/{r['o:id']}")
                        stats["created"] += 1
                        continue
                    cache[legacy] = item
                res = enrich(om, cache[legacy], args.drive_url, label, args.dry_run)
                if res == "enriched" and not args.dry_run:
                    cache[legacy] = om.get(f"items/{cache[legacy]['o:id']}")
                stats[res] += 1
                print(f"{res.upper():8s} {doc_id} -> {legacy}")
            else:
                identifier = f"{args.prefix}-R{n:04d}"
                payload = build_new(row, identifier, args.prefix, class_map, args.drive_url, label)
                if args.dry_run:
                    print(f"DRY-NEW  {doc_id} -> {identifier}")
                    print(json.dumps(payload, ensure_ascii=False)[:400])
                else:
                    r = om.post("items", payload)
                    print(f"CREATED  {doc_id} -> {identifier} (o:id={r['o:id']})")
                n += 1
                stats["created"] += 1
        except Exception as e:
            stats["errors"] += 1
            print(f"ERR  {doc_id}: {str(e)[:150]}", file=sys.stderr)
    print(stats)


if __name__ == "__main__":
    main()
