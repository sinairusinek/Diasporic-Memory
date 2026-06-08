"""Create per-class resource templates + item sets in Omeka S.

Idempotent: skips existing templates/item-sets by label.
Writes data/omeka-audit/class_map.json with class -> {template_id, item_set_id}.
"""
from __future__ import annotations
import json, sys
from pathlib import Path
from omeka import Omeka

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/omeka-audit/class_map.json"

# Property IDs (collected from existing templates 7/8 and inspection)
PROPS = {
    "dcterms:identifier":              10,
    "dcterms:isPartOf":                33,
    "dcterms:title":                   1,
    "ric-o:title":                     None,  # filled at runtime
    "ric-o:hasOrHadTitle":             None,
    "ric-o:generalDescription":        3502,
    "ric-o:hasAuthor":                 None,
    "ric-o:hasAddressee":              None,
    "ric-o:hasOrHadLanguage":          3201,
    "ric-o:hasDocumentaryFormType":    None,
    "ric-o:hasProductionTechniqueType":3240,
    "ric-o:hasRecordState":            3245,
    "ric-o:hasOrHadMainSubject":       3205,
    "ric-o:hasOrHadSubject":           None,
    "ric-o:hasCreationDate":           None,
    "ric-o:hasPublicationDate":        None,
    "arkivo:creationPlace":            None,
    "arkivo:destinationPlace":         None,
    "bibo:numPages":                   None,
    "ric-o:hasOrHadDigitalInstantiation": None,
}

REQUIRED = {"dcterms:identifier", "dcterms:isPartOf", "dcterms:title"}

# Jecke class -> (plural name for item_set/template, resource_class_id or None)
CLASS_SPECS = [
    ("EgoDocument",             "EgoDocuments",            1024),
    ("Image",                   "Images",                  26),
    ("Certificate",             "Certificates",            1016),
    ("Ephemera",                "Ephemera",                1025),
    ("Creative Fiction",        "Creative Fiction",        1019),
    ("Legal Document",          "Legal Documents",         64),
    ("Organization Papertrail", "Organization Papertrails",1041),
    ("Report",                  "Reports",                 1047),
    ("Financial_Document",      "Financial Documents",     1027),
    ("Object",                  "Objects",                 32),
    ("Medical Document",        "Medical Documents",       1037),
    ("Newspaper",               "Newspapers",              72),
    ("Article",                 "Articles",                36),
    ("Academic Paper",          "Academic Papers",         35),
    ("Translated Document",     "Translated Documents",    1039),
    ("Catalog",                 "Catalogs",                None),
    ("Religious Material",      "Religious Materials",     None),
    ("School Material",         "School Materials",        None),
    ("Unrecognized",            "Unrecognized",            None),
    ("MISC",                    "Misc",                    None),
]


def resolve_property_ids(om: Omeka) -> None:
    """Look up missing property IDs by term."""
    missing = [t for t, pid in PROPS.items() if pid is None]
    for term in missing:
        data = om.get("properties", term=term)
        if not data:
            raise RuntimeError(f"No property found for term {term!r}")
        PROPS[term] = data[0]["o:id"]
    print("Resolved properties:")
    for t, pid in PROPS.items():
        print(f"  {pid:5d}  {t}")


def find_by_label(om: Omeka, path: str, label: str) -> dict | None:
    for item in om.get(path, per_page=200):
        if item.get("o:label") == label or item.get("o:title") == label:
            return item
    return None


def template_payload(label: str, resource_class_id: int | None) -> dict:
    props = []
    for term, pid in PROPS.items():
        props.append({
            "o:property": {"o:id": pid},
            "o:alternate_label": None,
            "o:alternate_comment": None,
            "o:data_type": [],
            "o:is_required": term in REQUIRED,
            "o:is_private": False,
            "o:default_lang": None,
        })
    payload: dict = {
        "o:label": label,
        "o:title_property": {"o:id": PROPS["dcterms:title"]},
        "o:description_property": None,
        "o:resource_template_property": props,
        "o:data": {"use_for_resources": ["items"]},
    }
    if resource_class_id:
        payload["o:resource_class"] = {"o:id": resource_class_id}
    return payload


def item_set_payload(label: str) -> dict:
    return {
        "o:is_public": True,
        "dcterms:title": [
            {"type": "literal", "property_id": PROPS["dcterms:title"], "@value": label}
        ],
    }


def main() -> int:
    om = Omeka()
    resolve_property_ids(om)

    # Load existing templates and item sets for idempotency
    existing_templates = {t["o:label"]: t["o:id"] for t in om.get("resource_templates", per_page=500)}
    existing_sets: dict[str, int] = {}
    for s in om.get("item_sets", per_page=500):
        title = None
        for v in s.get("dcterms:title", []):
            if isinstance(v, dict) and "@value" in v:
                title = v["@value"]; break
        if title:
            existing_sets[title] = s["o:id"]

    print(f"\nExisting templates: {len(existing_templates)}")
    print(f"Existing item sets: {len(existing_sets)}")

    class_map: dict[str, dict] = {}
    for jecke_class, label, rc_id in CLASS_SPECS:
        # template
        if label in existing_templates:
            tid = existing_templates[label]
            print(f"  template skip (exists): {label!r} -> id {tid}")
        else:
            r = om.post("resource_templates", template_payload(label, rc_id))
            tid = r["o:id"]
            print(f"  template CREATED:       {label!r} -> id {tid}")
        # item set
        if label in existing_sets:
            sid = existing_sets[label]
            print(f"  item_set skip (exists): {label!r} -> id {sid}")
        else:
            r = om.post("item_sets", item_set_payload(label))
            sid = r["o:id"]
            print(f"  item_set CREATED:       {label!r} -> id {sid}")
        class_map[jecke_class] = {
            "label": label, "template_id": tid, "item_set_id": sid,
            "resource_class_id": rc_id,
        }

    OUT.write_text(json.dumps(class_map, indent=2, ensure_ascii=False))
    print(f"\nWrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
