#!/usr/bin/env python3
"""Assemble data/annotator/index.json and validate every bundle.

This is the gate. Everything downstream — the app's rendering, the DOM-offset
anchoring, the stored annotations — assumes the bundles are internally
consistent, and a silently wrong offset is far worse than a failed build. So
this validates and exits non-zero rather than warning:

  * text[start:end] == quote for every pre-highlight
  * page/segment spans tile the pane text with no gaps and no overlap
  * sha256 matches the shipped text
  * every case_id resolves in post_war_visits.tsv
  * no duplicate doc_id

Input:  data/annotator/docs/*.json, data/post_war_visits.tsv
Output: data/annotator/index.json
"""
import argparse
import csv
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import archival
import tags as tagvocab
from textnorm import PAGE_JOINER, sha256_text

REPO = Path(__file__).resolve().parents[2]
DOCS = REPO / "data/annotator/docs"
VISITS = REPO / "data/post_war_visits.tsv"
CASE_SUMMARIES = REPO / "data/annotator/case_summaries.json"
OUT = REPO / "data/annotator/index.json"


def load_cases():
    with VISITS.open(newline="", encoding="utf-8") as fh:
        return {r["case_id"]: r for r in csv.DictReader(fh, delimiter="\t")}


def check_pane(doc, name, pane, errors):
    where = f"{doc['doc_id']}/{name}"
    text = pane["text"]
    if sha256_text(text) != pane["sha256"]:
        errors.append(f"{where}: sha256 does not match text")

    blocks = pane.get("pages") or pane.get("segments") or []
    prev_end = None
    for b in blocks:
        if not (0 <= b["start"] <= b["end"] <= len(text)):
            errors.append(f"{where}: block {b.get('page_no', b.get('n'))} "
                          f"out of range [{b['start']},{b['end']}]")
            continue
        if prev_end is not None:
            gap = text[prev_end:b["start"]]
            if gap != PAGE_JOINER:
                errors.append(
                    f"{where}: block gap {gap!r} != joiner between "
                    f"{prev_end} and {b['start']}")
        prev_end = b["end"]
    if blocks and prev_end != len(text):
        errors.append(f"{where}: blocks end at {prev_end}, text is {len(text)}")


def check_doc(doc, cases, seen, errors):
    did = doc["doc_id"]
    if did in seen:
        errors.append(f"duplicate doc_id {did}")
    seen.add(did)

    if doc["case_id"] and doc["case_id"] not in cases:
        errors.append(f"{did}: unknown case_id {doc['case_id']}")
    if not doc["case_id"]:
        errors.append(f"{did}: no case_id")

    for name in ("source", "translation"):
        pane = doc["panes"].get(name)
        if pane:
            check_pane(doc, name, pane, errors)

    for h in doc["prehighlights"]:
        pane = doc["panes"].get(h["pane"])
        if not pane:
            errors.append(f"{did}: highlight {h['id']} on missing pane "
                          f"{h['pane']}")
            continue
        got = pane["text"][h["start"]:h["end"]]
        if got != h["quote"]:
            errors.append(f"{did}: highlight {h['id']} quote mismatch "
                          f"{h['quote']!r} != {got!r}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--warn-only", action="store_true",
                    help="report problems without failing (diagnosis only)")
    args = ap.parse_args()

    cases = load_cases()
    vocab = tagvocab.load()
    errors, seen = [], set()
    docs, by_case = [], defaultdict(list)

    for f in sorted(DOCS.glob("*.json")):
        doc = json.loads(f.read_text(encoding="utf-8"))
        check_doc(doc, cases, seen, errors)
        src = doc["panes"]["source"]
        blocks = src.get("pages") or src.get("segments") or []
        strict = sum(1 for h in doc["prehighlights"] if h.get("strict"))
        entry = {
            "doc_id": doc["doc_id"],
            "case_id": doc["case_id"],
            "kind": doc["kind"],
            "public": doc["public"],
            "title": doc["meta"]["title"],
            "date_text": doc["meta"]["date_text"],
            "doc_type": doc["meta"]["doc_type"],
            "languages": doc["meta"]["languages"],
            "folder": doc["meta"]["folder"],
            "page_range": doc["meta"]["page_range"],
            # Resolved here rather than baked into the bundles: it is pure
            # catalogue lookup, so a register correction should reach the app
            # through a free index rebuild, not a re-OCR.
            "archival": archival.context_for(
                doc["meta"]["folder"], doc["meta"].get("event_id", "")),
            "chars": len(src["text"]),
            "blocks": len(blocks),
            "has_translation": bool(doc["panes"].get("translation")),
            "n_prehighlights": len(doc["prehighlights"]),
            "n_strict": strict,
            # The catalogue view browses by summary, so the index carries them;
            # they are small next to the pane text that stays in the bundles.
            "summary_he": doc.get("summary_he", ""),
            "summary_de": doc.get("summary_de", ""),
            "summary_en": doc.get("summary_en", ""),
            "grades": {g: sum(1 for b in blocks if b.get("grade") == g)
                       for g in ("clean", "mixed", "poor")}
                      if doc["kind"] == "written" else {},
        }
        docs.append(entry)
        by_case[doc["case_id"]].append(doc["doc_id"])

    if errors:
        print(f"{len(errors)} validation error(s):", file=sys.stderr)
        for e in errors[:40]:
            print(f"  {e}", file=sys.stderr)
        if len(errors) > 40:
            print(f"  … and {len(errors) - 40} more", file=sys.stderr)
        if not args.warn_only:
            raise SystemExit(1)

    def case_sort(cid):
        return (0, int(cid.split("-")[1])) if cid.startswith("PWV-") else (1, 0)

    # Hand-written case summaries (en/he). The tsv's evidence column is a
    # working note, not prose for the catalogue, so these live in their own
    # file; a case without one falls back to nothing rather than the note.
    case_summaries = {}
    if CASE_SUMMARIES.exists():
        case_summaries = {
            k: v for k, v in
            json.loads(CASE_SUMMARIES.read_text(encoding="utf-8")).items()
            if not k.startswith("_")}

    case_list = []
    for cid in sorted(by_case, key=case_sort):
        c = cases.get(cid, {})
        ids = by_case[cid]
        cs = case_summaries.get(cid, {})
        if not cs:
            print(f"  note: no case summary for {cid}", file=sys.stderr)
        case_list.append({
            "case_id": cid,
            "person": c.get("person", ""),
            "city_region": c.get("city_region", ""),
            "year": c.get("year", ""),
            "category": c.get("category", ""),
            "evidence": c.get("evidence", ""),
            "summary_en": cs.get("en", ""),
            "summary_he": cs.get("he", ""),
            "drive_url": c.get("drive_url", ""),
            "kind": "oral" if all(i.startswith("IS_E_") for i in ids)
                    else "written",
            "doc_ids": sorted(ids),
        })

    index = {
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tags": vocab,
        "cases": case_list,
        "docs": sorted(docs, key=lambda d: (case_sort(d["case_id"]),
                                            d["doc_id"])),
    }
    OUT.write_text(json.dumps(index, ensure_ascii=False, indent=1),
                   encoding="utf-8")

    written = [d for d in docs if d["kind"] == "written"]
    oral = [d for d in docs if d["kind"] == "oral"]
    print(f"{len(docs)} documents in {len(case_list)} cases -> {OUT}")
    print(f"  written {len(written):3}  {sum(d['chars'] for d in written):8}ch")
    print(f"  oral    {len(oral):3}  {sum(d['chars'] for d in oral):8}ch")
    print(f"  pre-highlights {sum(d['n_prehighlights'] for d in docs)} "
          f"({sum(d['n_strict'] for d in docs)} strict)")
    print(f"  translated     {sum(1 for d in docs if d['has_translation'])}"
          f"/{len(docs)}")
    print(f"  tag vocabulary {len(vocab['index'])} tags")


if __name__ == "__main__":
    main()
