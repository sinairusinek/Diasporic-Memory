#!/usr/bin/env python3
"""Compile the tag vocabulary from annotation_scheme_return_spans.md.

The scheme markdown is the single source of truth: editing it and rebuilding is
the supported way to change the vocabulary. Nothing in the app or the database
hard-codes a tag id, so a renamed tag is a data migration, not a code change.

Two shapes come out of the same file:
  facets  F1-F4, each with a cardinality the UI enforces
          (F1/F2 exactly one, F3/F4 zero or one)
  themes  T1-T7 groups, each with sub-tags; one or more per span
"""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCHEME = REPO / "annotation_scheme_return_spans.md"

FACET_META = {
    "F1": ("span-type", "one", "מהו סוג ההיגד"),
    "F2": ("time-layer", "one", "לאיזה זמן ההיגד מתייחס"),
    "F3": ("voice", "zero-or-one", "עמדת מי ההיגד מבטא"),
    "F4": ("stance", "zero-or-one", "יחס לשיבה"),
}

_HEAD = re.compile(r"^##+\s*(F[1-4]|T[1-7])\s*[·.]?\s*(.*)$")
_ROW = re.compile(r"^\|\s*`([^`]+)`\s*\|\s*(.*?)\s*\|")
_BULLET = re.compile(r"^-\s*`(T\d\.\d+)\s+([^`]+)`\s*(?:—\s*(.*))?$")
_INLINE = re.compile(r"`(\w+:[\w-]+)`(?:\s*\(([^)]*)\))?")


def load():
    text = SCHEME.read_text(encoding="utf-8")
    facets, themes, order = {}, {}, []
    current = None

    for line in text.splitlines():
        h = _HEAD.match(line)
        if h:
            current = h.group(1)
            title = re.sub(r"\s*\(.*\)$", "", h.group(2)).strip()
            if current.startswith("F"):
                name, card, he = FACET_META[current]
                facets[current] = {"id": current, "name": name, "title": title,
                                   "cardinality": card, "hint_he": he,
                                   "tags": []}
            else:
                themes[current] = {"id": current, "title": title, "tags": []}
                order.append(current)
            continue
        if not current:
            continue

        if current.startswith("F"):
            m = _ROW.match(line)
            if m and not m.group(1).startswith("Tag"):
                facets[current]["tags"].append(
                    {"id": m.group(1), "label": m.group(1).split(":", 1)[-1],
                     "description": m.group(2), "facet": current})
                continue
            # F2-F4 list their tags inline in backticks rather than a table.
            for tag, gloss in _INLINE.findall(line):
                if any(t["id"] == tag for t in facets[current]["tags"]):
                    continue
                facets[current]["tags"].append(
                    {"id": tag, "label": tag.split(":", 1)[-1],
                     "description": gloss.strip(), "facet": current})
        else:
            m = _BULLET.match(line)
            if m:
                themes[current]["tags"].append(
                    {"id": m.group(1), "label": m.group(2),
                     "description": (m.group(3) or "").strip(),
                     "group": current})

    vocab = {
        "facets": [facets[k] for k in ("F1", "F2", "F3", "F4") if k in facets],
        "themes": [themes[k] for k in order],
        "source": "annotation_scheme_return_spans.md",
    }
    vocab["index"] = {t["id"]: t
                      for grp in vocab["facets"] + vocab["themes"]
                      for t in grp["tags"]}
    return vocab


if __name__ == "__main__":
    v = load()
    for f in v["facets"]:
        print(f"{f['id']} {f['title']} [{f['cardinality']}] "
              f"{len(f['tags'])} tags")
        for t in f["tags"]:
            print(f"     {t['id']:28} {t['description'][:56]}")
    for g in v["themes"]:
        print(f"{g['id']} {g['title']}  {len(g['tags'])} tags")
        for t in g["tags"]:
            print(f"     {t['id']:8} {t['label']:24} {t['description'][:44]}")
    print(f"\ntotal {len(v['index'])} tags")
