"""Dump the folder-level structure (series + file components) of one or more
EAD records. Useful for human review of candidate collections — shows what
is actually in each box, not just the top-level abstract.

Usage:
  python3 code/inspect_folders.py 3/15595 3/6730 3/19997 ...
where each arg is repo/resource_id.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from lxml import etree as LET

EAD = "urn:isbn:1-931666-22-9"

# Patterns that suggest folder content we care about for the diasporic-memory project.
PROJECT_SIGNALS = re.compile(
    r"\b(memoir|memoirs|memoiren|erinnerung|autobiograph|"
    r"diar(y|ies)|tagebuch|"
    r"correspondenc|letters?|briefe?|"
    r"oral histor|interview|reminiscenc|"
    r"heimat|home town|hometown|"
    r"trip|journey|visit|return|reise|besuch|"
    r"photograph album)\b", re.I)


def dump(path: Path):
    parser = LET.XMLParser(recover=True, huge_tree=True)
    tree = LET.parse(str(path), parser)
    root = tree.getroot()
    archdesc = root if root.tag.endswith("archdesc") else \
               root.find(".//{%s}archdesc" % EAD)
    if archdesc is None:
        print(f"  (no archdesc in {path})")
        return

    title_el = archdesc.find("{%s}did/{%s}unittitle" % (EAD, EAD))
    title = "".join(title_el.itertext()).strip() if title_el is not None else ""
    date_el = archdesc.find("{%s}did/{%s}unitdate" % (EAD, EAD))
    dates = "".join(date_el.itertext()).strip() if date_el is not None else ""
    print(f"\n=== {title} ({dates}) ===")

    last_series = None
    for c in archdesc.iter("{%s}c" % EAD):
        did = c.find("{%s}did" % EAD)
        if did is None:
            continue
        level = c.get("level", "")
        t_el = did.find("{%s}unittitle" % EAD)
        d_el = did.find("{%s}unitdate" % EAD)
        t = " ".join(s.strip() for s in t_el.itertext() if s.strip()) if t_el is not None else ""
        d = " ".join(s.strip() for s in d_el.itertext() if s.strip()) if d_el is not None else ""

        if level == "series":
            print(f"\n  ── {t}  [{d}]")
            last_series = t
        elif level in ("subseries",):
            print(f"     · {t}  [{d}]")
        else:
            mark = "★" if PROJECT_SIGNALS.search(t) else " "
            year = ""
            # Highlight 1933+ dates inline so the user can scan post-1933 content
            ys = re.findall(r"\b(18\d{2}|19\d{2}|20\d{2})\b", d)
            if ys:
                latest = max(int(y) for y in ys)
                year = f" [{d}]"
                if latest >= 1945:
                    mark = "✦" if PROJECT_SIGNALS.search(t) else "•"
            print(f"     {mark} {t[:100]}{year}")


def main():
    base = Path(__file__).parent.parent / "data" / "cjh-oai" / "records" / "oai_ead"
    for arg in sys.argv[1:]:
        repo, res = arg.split("/")
        p = base / f"repo-{repo}" / f"resource-{res}.xml"
        if not p.exists():
            print(f"missing: {p}")
            continue
        dump(p)


if __name__ == "__main__":
    main()
