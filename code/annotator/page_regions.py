#!/usr/bin/env python3
"""Mark which part of each scanned page is the document the archivist meant.

A newspaper page was scanned whole, but usually only one article on it is the
source. The rest — the neighbouring column, the masthead, the sports results,
a carnival report that happens to share the sheet — reads as if it belonged to
the document, and it does not.

This marks regions; it never removes text. `drop` means "the app should get
this out of the reader's way", not "this is gone": the source pane still
renders every character, the offsets are unchanged, and a region the model got
wrong is one click from being read. That asymmetry is deliberate and it is
what lets the prompt below call `drop` on a merely-plausible passage, which a
destructive pass could not afford to do.

Two shapes of pollution, and only one is separable:

  * a wanted article sharing a page with unrelated ones — cleanly separable;
  * a wanted passage sitting INSIDE an unrelated article, e.g. the two
    sentences about 40 emigrants from Israel buried in a Rosenmontagszug
    report (0276-D04 p4). Dropping the article there would take the evidence
    with it, so the prompt is told to cut the wanted run out of its host.

Input/Output: data/annotator/docs/*.json  (`regions` written in place)
"""
import argparse
import csv
import json
from pathlib import Path

import llm
from prehighlight_claude import locate, parse_json

REPO = Path(__file__).resolve().parents[2]
DOCS = REPO / "data/annotator/docs"
OVERRIDES = REPO / "data/annotator/region_overrides.tsv"

# Types where a scan holds more than the document. A letter or a manuscript
# note is photographed on its own and has nothing to separate.
SHARED_PAGE_TYPES = {
    "newspaper_article", "newspaper_clippings", "program_booklet",
    "mixed_leaflets", "city_brochure", "invitation_program",
}

LABELS = {"keep", "drop", "chrome"}

SYSTEM = [{
    "type": "text",
    "text": """You segment scanned newspaper and brochure pages for a scholarly archive on
the post-war return visits of German-Jewish emigrants to Germany.

A whole page was scanned, but usually only part of it is the document the
archivist meant. The rest is whatever else shared the sheet: unrelated
articles, advertisements, mastheads, sports results, a neighbouring column the
OCR has interleaved into the text.

You are given the page's OCR text and the archivist's rationale for why the
document is relevant. Divide the page into consecutive regions and label each:

  keep    — the article or section the rationale is about, with its headline,
            byline, caption and continuation
  drop    — page matter that is not that document
  chrome  — masthead, publication name, page number, date line, clipping-
            service stamp

Nothing is deleted. A `drop` region stays in the archive and stays readable;
it is only moved out of the reader's way. So label by what the passage IS, and
do not inflate `keep` to protect against your own uncertainty.

RULES:

1. A wanted passage may sit INSIDE an unrelated article. When a paragraph or
   two about emigrants, a visit, or the Jewish community appears in the middle
   of a report about something else, cut it out: `drop` the host article
   before it, `keep` the passage, `drop` the host after it. Do not label the
   whole host `keep` because it contains the passage, and do not label the
   passage `drop` because its host is irrelevant.
2. The OCR interleaves columns, so one article may be split into several
   non-adjacent runs. Emit each run as its own region rather than swallowing
   what lies between them.
3. A page may hold more than one wanted article. Label each `keep`.
4. `keep` needs a positive reason you could state — this passage is about the
   visit, the emigrants, the community, the commemoration, the invitation. A
   passage that merely names the same city, or shares the page with the
   article, is not enough.
5. Local news, obituaries of unrelated people, sport, weather, advertisements
   and tourist description are `drop` even when they sit inches from the
   wanted article and even when they mention the town.
6. If the whole page is the wanted document, return one `keep` region covering
   it. If none of it is, say so — every region `drop` is a valid answer.
7. Do not correct, re-flow or tidy the OCR in the anchors you return.

Return a JSON array, in page order. Each element:
  {"label": "keep|drop|chrome",
   "start_anchor": "<first 6-12 words of the region, verbatim>",
   "end_anchor": "<last 6-12 words of the region, verbatim>",
   "what": "<short English description, e.g. 'carnival parade report'>",
   "confidence": <0.0-1.0>}

Anchors are matched against the page by exact string search, so copy them
character-for-character including OCR errors and column noise.""",
}]


def regions_for_page(doc, page, usage, force):
    """Locate the model's regions and tile the page with them.

    Anchors are resolved by the same exact-match rule the pre-highlight guard
    uses. Anything that will not resolve is not guessed at: the page falls back
    to a single `keep`, which is the reading the app had before this pass and
    so can only fail safe.
    """
    src = doc["panes"]["source"]
    body = src["text"][page["start"]:page["end"]]
    if not body.strip():
        return []

    user = (f"Document: {doc['meta']['title']}\n"
            f"Type: {doc['meta']['doc_type']}, {doc['meta']['date_text']}\n"
            f"Archivist's rationale: {doc['meta']['heimat_rationale']}\n"
            f"Page {page['page_no']}, OCR graded {page['grade']}.\n\n"
            f"---\n{body}")
    raw = llm.ask(SYSTEM, user, task="page_regions", usage=usage,
                  max_tokens=8000, effort="medium", force=force)

    found = []
    for item in parse_json(raw):
        label = str(item.get("label") or "")
        if label not in LABELS:
            continue
        a = locate(body, str(item.get("start_anchor") or ""))
        b = locate(body, str(item.get("end_anchor") or ""))
        if not a or not b or b[1] <= a[0]:
            continue
        try:
            conf = float(item.get("confidence", 0))
        except (TypeError, ValueError):
            conf = 0.0
        found.append({"start": a[0], "end": b[1], "label": label,
                      "what": str(item.get("what") or "")[:120],
                      "confidence": round(conf, 2)})

    if not found:
        return [{"page_no": page["page_no"], "start": page["start"],
                 "end": page["end"], "label": "keep",
                 "what": "unsegmented", "confidence": 0.0}]

    # Resolve overlaps by first-come, then fill the gaps. Gaps become `keep`:
    # unclaimed text is text the model did not say was someone else's. A gap
    # that is only the blank line between two regions is absorbed into the
    # region that follows rather than becoming a region of its own.
    found.sort(key=lambda r: r["start"])
    tiled, cursor = [], 0
    for r in found:
        if r["start"] < cursor:
            r = {**r, "start": cursor}
            if r["end"] <= r["start"]:
                continue
        if r["start"] > cursor:
            if body[cursor:r["start"]].strip():
                tiled.append({"start": cursor, "end": r["start"],
                              "label": "keep", "what": "unclaimed",
                              "confidence": 0.0})
            else:
                r = {**r, "start": cursor}
        tiled.append(r)
        cursor = r["end"]
    if cursor < len(body):
        if body[cursor:].strip() or not tiled:
            tiled.append({"start": cursor, "end": len(body), "label": "keep",
                          "what": "unclaimed", "confidence": 0.0})
        else:
            tiled[-1] = {**tiled[-1], "end": len(body)}

    return [{"page_no": page["page_no"],
             "start": page["start"] + r["start"],
             "end": page["start"] + r["end"],
             "label": r["label"], "what": r["what"],
             "confidence": r["confidence"]}
            for r in tiled]


def load_overrides():
    """Human corrections to the model's labels, keyed by doc_id.

    Anchored to text, not to offsets. The first version of this file recorded
    absolute offsets and was silently invalidated the moment the pages were
    re-transcribed — offset 2820 had been the Philipp Jenninger profile and
    became the middle of a church service programme. An anchor moves with its
    sentence.

    A row marks where a region STARTS; it runs to the next override on the
    same page, or to the end of the page. An empty anchor means the whole page.
    """
    if not OVERRIDES.exists():
        return {}
    out = {}
    with OVERRIDES.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            if not row.get("doc_id") or row["doc_id"].startswith("#"):
                continue
            out.setdefault(row["doc_id"], []).append({
                "page_no": int(row["page_no"]),
                "anchor": (row.get("start_anchor") or "").strip(),
                "label": row["label"].strip(),
                "note": (row.get("note") or "").strip(),
            })
    return out


def apply_overrides(regions, overrides, doc):
    """Replace a page's regions wholesale wherever the PI has ruled on it.

    Her rows tile the page between them, so the model's segmentation of that
    page is discarded rather than merged with — a half-corrected page is
    harder to reason about than either an automatic one or a hand one.
    Anything that will not resolve is reported and skipped, never guessed at.
    """
    src = doc["panes"]["source"]
    text = src["text"]
    pages = {p["page_no"]: p for p in (src.get("pages") or [])}
    by_page = {}
    for o in overrides:
        by_page.setdefault(o["page_no"], []).append(o)

    unresolved = []
    for page_no, rows in by_page.items():
        page = pages.get(page_no)
        if not page:
            unresolved.append(f"page {page_no} not in document")
            continue
        body = text[page["start"]:page["end"]]

        marks = []
        for o in rows:
            if not o["anchor"]:
                marks.append((0, o))
                continue
            span = locate(body, o["anchor"])
            if span is None:
                unresolved.append(
                    f"page {page_no}: anchor not found or ambiguous — "
                    f"{o['anchor'][:60]!r}")
                continue
            marks.append((span[0], o))
        if not marks:
            continue
        marks.sort(key=lambda m: m[0])

        replacement = []
        for i, (start, o) in enumerate(marks):
            end = marks[i + 1][0] if i + 1 < len(marks) else len(body)
            if end <= start:
                continue
            replacement.append({
                "page_no": page_no,
                "start": page["start"] + start,
                "end": page["start"] + end,
                "label": o["label"],
                "what": o["note"] or "set by hand",
                "confidence": 1.0,
            })
        if replacement:
            if replacement[0]["start"] > page["start"]:
                replacement.insert(0, {
                    "page_no": page_no, "start": page["start"],
                    "end": replacement[0]["start"], "label": "keep",
                    "what": "before the first hand-marked region",
                    "confidence": 0.0})
            regions = [r for r in regions if r["page_no"] != page_no]
            regions.extend(replacement)

    regions.sort(key=lambda r: r["start"])
    return regions, unresolved


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--docs", nargs="*", help="doc_id substrings to limit to")
    ap.add_argument("--all-types", action="store_true",
                    help="do not restrict to page-sharing document types")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    files = sorted(DOCS.glob("*.json"))
    if args.docs:
        files = [f for f in files if any(d in f.stem for d in args.docs)]

    overrides = load_overrides()
    usage = llm.Usage()
    done = 0
    tot_keep = tot_drop = tot_chrome = tot_overridden = 0
    nonlocal_fallback = [0]
    for f in files:
        doc = json.loads(f.read_text(encoding="utf-8"))
        pages = doc["panes"]["source"].get("pages") or []
        if not pages:
            continue
        if not args.all_types and not args.docs and \
                doc["meta"]["doc_type"] not in SHARED_PAGE_TYPES:
            continue
        if args.limit and done >= args.limit:
            break

        regions = []
        for p in pages:
            regions.extend(regions_for_page(doc, p, usage, args.force))
        ovs = overrides.get(doc["doc_id"], [])
        if ovs:
            regions, unresolved = apply_overrides(regions, ovs, doc)
            tot_overridden += len(ovs)
            for u in unresolved:
                print(f"  !! {doc['doc_id']}: {u}")
        doc["regions"] = regions
        f.write_text(json.dumps(doc, ensure_ascii=False, indent=1),
                     encoding="utf-8")

        by = {k: sum(r["end"] - r["start"] for r in regions if r["label"] == k)
              for k in LABELS}
        tot_keep += by["keep"]; tot_drop += by["drop"]; tot_chrome += by["chrome"]
        total = max(1, sum(by.values()))
        # Pages whose anchors would not resolve fell back to a single `keep`.
        # A rising count here means the model is prettifying its anchors, the
        # same failure the pre-highlight guard watches for.
        fell_back = sum(1 for r in regions if r["what"] == "unsegmented")
        nonlocal_fallback[0] += fell_back
        done += 1
        print(f"  {doc['doc_id']:26} {len(pages):3}pp {len(regions):4} regions  "
              f"keep {100*by['keep']//total:3}%  drop {100*by['drop']//total:3}%  "
              f"chrome {100*by['chrome']//total:2}%"
              + (f"  {fell_back} page(s) unsegmented" if fell_back else ""))

    grand = max(1, tot_keep + tot_drop + tot_chrome)
    print(f"{done} documents · {tot_keep:,} keep / {tot_drop:,} drop / "
          f"{tot_chrome:,} chrome chars ({100*tot_drop//grand}% set aside)")
    print(f"  {nonlocal_fallback[0]} pages fell back to a single keep region")
    print(f"  {tot_overridden} regions set by hand from region_overrides.tsv")
    print(f"  {usage.report()}")


if __name__ == "__main__":
    main()
