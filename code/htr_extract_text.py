"""Re-extract plain text from cached Transkribus PAGE XML.

Reads:  data/transkribus/htr/<docId>/pages/*.xml
Writes: data/transkribus/htr/<docId>/pages/<page>.txt   (overwrites)
        data/transkribus/htr/<docId>/fulltext.txt        (concatenated)

Per TextLine: join all <Word> Unicode in document order; if a line has no
Words, use the TextLine's own Unicode.
"""
from __future__ import annotations
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

NS = "{http://schema.primaresearch.org/PAGE/gts/pagecontent/2013-07-15}"
ROOT = Path(__file__).resolve().parent.parent / "data/transkribus/htr"


def line_text(tl: ET.Element) -> str:
    words = tl.findall(f"{NS}Word")
    if words:
        parts = []
        for w in words:
            u = w.find(f"{NS}TextEquiv/{NS}Unicode")
            if u is not None and u.text:
                parts.append(u.text)
        return " ".join(parts)
    u = tl.find(f"{NS}TextEquiv/{NS}Unicode")
    return u.text if (u is not None and u.text) else ""


def page_text(xml_path: Path) -> str:
    try:
        root = ET.fromstring(xml_path.read_bytes())
    except ET.ParseError:
        return ""
    out = []
    for tl in root.iter(f"{NS}TextLine"):
        t = line_text(tl)
        if t:
            out.append(t)
    return "\n".join(out)


def process(doc_id: str) -> None:
    pages_dir = ROOT / doc_id / "pages"
    if not pages_dir.exists():
        print(f"skip {doc_id}: no pages dir")
        return
    xmls = sorted(pages_dir.glob("*.xml"))
    full = []
    for x in xmls:
        t = page_text(x)
        (pages_dir / (x.stem + ".txt")).write_text(t, encoding="utf-8")
        if t.strip():
            full.append(f"=== page {x.stem} ===\n{t}\n")
    (ROOT / doc_id / "fulltext.txt").write_text("\n".join(full), encoding="utf-8")
    print(f"{doc_id}: {len(xmls)} pages, {len(full)} non-empty")


if __name__ == "__main__":
    for d in sys.argv[1:]:
        process(d)
