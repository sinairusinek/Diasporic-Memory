#!/usr/bin/env python3
"""Build annotator bundles from the Israelkorpus oral testimonies.

One bundle per *excerpt window*, never a whole transcript: the interviews run to
~1,000 contributions each and only the return-visit passages are in scope. Two
reasons — the PI should not have to scroll an interview to find the visit, and
the DGD terms of service are unresolved on publication, so the less of the
corpus that leaves the archive the better. Every bundle is public:false and the
app never serves them outside the password gate.

Windows come from the hits already computed by
code/israelkorpus/scan_heimat_signals.py; hits within MERGE_GAP contributions of
each other become one window, padded by PAD on each side.

Input:  data/israelkorpus/structured/IS_E_*.json
        data/israelkorpus/heimat_scan.tsv
        data/post_war_visits.tsv
Output: data/annotator/docs/IS_E_XXXXX__wNN.json
"""
import argparse
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from textnorm import join_pages, sha256_text

REPO = Path(__file__).resolve().parents[2]
STRUCTURED = REPO / "data/israelkorpus/structured"
SCAN = REPO / "data/israelkorpus/heimat_scan.tsv"
VISITS = REPO / "data/post_war_visits.tsv"
DOCS = REPO / "data/annotator/docs"

MERGE_GAP = 12  # hits this close (in contributions) belong to one window
PAD = 4         # contributions of context on each side

# The loose tier is co-occurrence only ("Deutschland" near a travel verb) and is
# more than half of all hits. It seeds windows too eagerly and would bury the
# real return passages, so it never opens a window on its own — but it is kept
# when it falls inside a window opened by a stronger hit.
SEEDING = {"heimat", "return_visit_lexeme", "return_visit_strong", "invitation"}

# Transcription artefacts in the DGD conventions: ↑↓ intonation, ** pauses,
# (( )) comments, = latching. Kept in the text (they are evidence about the
# telling) but normalized so they do not fragment the reading.
ARTIFACT = re.compile(r"\(\([^)]*\)\)")


def load_case_map():
    """record_id -> case row, for the 16 oral cases in post_war_visits.tsv."""
    out = {}
    with VISITS.open(newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            rec = (r.get("record_id") or "").strip()
            m = re.match(r"IS--_E_(\d+)", rec)
            if m:
                out[f"IS_E_{m.group(1)}"] = r
    return out


def load_hits():
    hits = {}
    with SCAN.open(newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            hits.setdefault(r["event_id"], []).append(
                {"n": int(r["n"]), "category": r["category"],
                 "match": r["match"], "time": r["time"]})
    return hits


def windows(hits, available):
    """Group hits into (first_n, last_n, hit_list) windows."""
    seeds = sorted({h["n"] for h in hits if h["category"] in SEEDING})
    if not seeds:
        return []
    groups, cur = [], [seeds[0]]
    for n in seeds[1:]:
        if n - cur[-1] <= MERGE_GAP:
            cur.append(n)
        else:
            groups.append(cur)
            cur = [n]
    groups.append(cur)

    out = []
    for g in groups:
        lo, hi = min(g) - PAD, max(g) + PAD
        ns = [n for n in available if lo <= n <= hi]
        if not ns:
            continue
        inside = [h for h in hits if ns[0] <= h["n"] <= ns[-1]]
        out.append((ns, inside))
    # Merge windows that ended up overlapping after padding.
    merged = []
    for ns, inside in out:
        if merged and ns[0] <= merged[-1][0][-1]:
            prev_ns, prev_in = merged.pop()
            ns = sorted(set(prev_ns) | set(ns))
            seen = {(h["n"], h["category"]) for h in prev_in}
            inside = prev_in + [h for h in inside
                               if (h["n"], h["category"]) not in seen]
        merged.append((ns, inside))
    return merged


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", ARTIFACT.sub(" ", text or "")).strip()


def build_event(event_id, rec, hits, case, dry=False):
    contribs = rec["contributions"]
    # Contributions carry their own `n`; it is NOT the list index
    # (contributions[95]["n"] == 96). Indexing by position silently shifts
    # every window by one turn.
    by_n = {c["n"]: c for c in contribs}
    available = sorted(by_n)
    speakers = {s.get("speaker_id"): s for s in rec.get("interviewees", [])}
    interviewee = ", ".join(s["name"] for s in rec.get("interviewees", []))

    bundles = []
    for i, (ns, inside) in enumerate(windows(hits, available), start=1):
        pieces = [(n, clean(by_n[n]["text"])) for n in ns]
        text, spans = join_pages(pieces)
        segs = []
        for (n, _), span in zip(pieces, spans):
            c = by_n[n]
            sid = c.get("speaker_id")
            segs.append({
                "n": n,
                "speaker": c.get("speaker") or "",
                "speaker_name": (speakers.get(sid) or {}).get("name", ""),
                "start_sec": c.get("start"),
                "start": span["start"], "end": span["end"],
            })
        cats = sorted({h["category"] for h in inside})
        first_time = next((h["time"] for h in inside if h["time"]), "")
        doc_id = f"{event_id}__w{i:02d}"
        bundles.append({
            "doc_id": doc_id,
            "catalog_doc_id": rec["transcript_id"],
            "case_id": case["case_id"] if case else "",
            "kind": "oral",
            "public": False,
            "meta": {
                "title": f"{interviewee or event_id} — excerpt {i}"
                         + (f" ({first_time})" if first_time else ""),
                "date_text": "",
                "doc_type": "oral_history_interview",
                "languages": ["de"],
                "from_person": interviewee,
                "to_person": "Anne Betten",
                "places": [case["city_region"]] if case else [],
                "persons": [s["name"] for s in rec.get("interviewees", [])],
                "heimat_rationale": (case or {}).get("evidence", ""),
                "notes": "Israelkorpus (Betten). DGD-licensed: excerpt only, "
                         "not for public display.",
                "folder": "israelkorpus",
                "page_range": f"contributions {ns[0]}–{ns[-1]}",
                "is_heimat_relevant": "yes",
                "event_id": event_id,
                "signal_categories": cats,
                "restricted": "DGD",
            },
            "summary_he": "",
            "summary_de": "",
            "summary_en": (case or {}).get("evidence", ""),
            "panes": {
                "source": {
                    "pane": "source", "lang": "de", "dir": "ltr",
                    "text": text, "sha256": sha256_text(text),
                    "pages": [], "segments": segs,
                },
                "translation": None,
            },
            "prehighlights": [],
            "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        })
    return bundles


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--events", nargs="*", help="e.g. IS_E_00042")
    ap.add_argument("--all-events", action="store_true",
                    help="include events with no post_war_visits case")
    ap.add_argument("--docs", nargs="*",
                    help="doc_id substrings to limit to; a selection that "
                         "names no oral document simply builds nothing")
    args = ap.parse_args()

    cases = load_case_map()
    hits = load_hits()
    DOCS.mkdir(parents=True, exist_ok=True)

    targets = args.events or sorted(cases)
    total_docs = total_win = 0
    for event_id in targets:
        path = STRUCTURED / f"{event_id}.json"
        if not path.exists():
            print(f"  ! {event_id}: no structured transcript")
            continue
        case = cases.get(event_id)
        if case is None and not args.all_events:
            continue
        rec = json.loads(path.read_text(encoding="utf-8"))
        bundles = build_event(event_id, rec, hits.get(event_id, []), case)
        if args.docs:
            bundles = [b for b in bundles
                       if any(d in b["doc_id"] for d in args.docs)]
        for b in bundles:
            out = DOCS / f"{b['doc_id']}.json"
            if out.exists():
                prev = json.loads(out.read_text(encoding="utf-8"))
                if prev["panes"]["source"]["sha256"] == \
                        b["panes"]["source"]["sha256"]:
                    b["panes"]["translation"] = prev["panes"]["translation"]
                    b["prehighlights"] = prev["prehighlights"]
            out.write_text(json.dumps(b, ensure_ascii=False, indent=1),
                           encoding="utf-8")
        total_win += len(bundles)
        total_docs += 1
        chars = sum(len(b["panes"]["source"]["text"]) for b in bundles)
        print(f"  {event_id} [{case['case_id'] if case else '--':6}] "
              f"{len(bundles):2} windows  {chars:6}ch  "
              f"{(case or {}).get('person','')[:28]}")
    print(f"{total_win} oral bundles from {total_docs} interviews -> {DOCS}")


if __name__ == "__main__":
    main()
