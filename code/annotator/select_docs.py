#!/usr/bin/env python3
"""Select the post-war-visit documents that go into the annotator.

`is_heimat_relevant` alone is too wide: it also flags the Hecker memoirs and the
Gerson genealogy, which are diasporic-memory material but not *visits*. The
narrowing from relevance to visit-relatedness is an editorial judgement (is a
Kristallnacht commemoration service a visit document?), so it lives here as an
explicit allow-list rather than a heuristic, and the output TSV is meant to be
read and edited by hand before the rest of the pipeline runs.

Input:  data/recatalog/<folder>/catalog.tsv   (6 visit folders)
        data/post_war_visits.tsv              (case grouping)
Output: data/annotator/manifest.tsv
"""
import argparse
import csv
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RECATALOG = REPO / "data/recatalog"
VISITS = REPO / "data/post_war_visits.tsv"
OUT = REPO / "data/annotator/manifest.tsv"

# doc_id -> case_id. Curated by hand from catalog.tsv titles + heimat_rationale.
# Adding or removing a line here is the supported way to change the corpus.
ALLOW = {
    # --- 0276-6 · Heinrich (Zvi) Schopler, Cologne invitation 1986-87 ---
    "0276-6": {
        "0276-D01": "PWV-16",  # handwritten note, 1987
        "0276-D02": "PWV-16",  # "Ein Wiedersehen nach 50 Jahren"
        "0276-D04": "PWV-16",  # Stadt Köln press clippings, Rathaus reception
        "0276-D05": "PWV-16",  # "Frühlingsfahrt in die Domstadt Köln"
        "0276-D06": "PWV-16",  # programme booklet, Israel delegation Feb 1986
        "0276-D09": "PWV-16",  # "Die Stadt KÖLN lud ehemalige Bürger ein"
        "0276-D13": "PWV-16",  # Schopler's own reception address, 27.05.1987
        "0276-D15": "PWV-16",  # press echo (FAZ, Aufbau)
        "0276-D16": "PWV-16",  # Oberbürgermeister Burger's address
        "0276-D17": "PWV-16",  # Dr Erich Loeb's address
    },
    # --- 0047-2 · Leoni Frank in Wiesbaden; Sharett correspondence ---
    "0047-2": {
        "0047-2-D05": "PWV-17",  # Sharett to Leoni Frank, Wiesbaden 1962
        "0047-2-D08": "PWV-17",  # Sharett's itinerary Lod-Paris-Hamburg-Bonn
        "0047-2-D14": "PWV-17",  # "Wo liegt Wiesbaden überhaupt?"
        "0047-2-D18": "PWV-17",  # Leoni Frank before a long journey
        "0047-2-D19": "PWV-17",  # "fremd und einsam in der Stadt..."
        "0047-2-D33": "PWV-17",  # "kommen Sie doch einmal nach Wiesbaden zurück?"
        "0047-2-D37": "PWV-17",  # letter dictated from Germany to Leoni
    },
    # --- 0444-3 · Hans Hanan Mannheimer, Worms 1964 invitation / 1985 refusal ---
    "0444-3": {
        "0444-D01": "PWV-14",  # official invitation of the city of Worms, 1964
        "0444-D02": "PWV-14",  # Hebrew handwritten note, 1964
        "0444-D03": "PWV-15",  # honorary citizenship 1985 + Mannheimer's refusal
        "0444-D04": "PWV-15",  # 1988 correspondence
        "0444-D05": "PWV-15",  # Wormser Zeitung + "Telem" press 1979-1982
        "0444-D10": "PWV-15",  # handwritten notes
    },
    # --- 0422-3 · Simon Berlinger, Hohenlohe / Schwäbisch Hall ---
    # Kept narrow: the commemorations Berlinger was invited *to*, plus the city's
    # own welcome material. The student project and the general Jewish-history
    # texts are context, not visit documents.
    "0422-3": {
        "0422-S07": "PWV-13",  # press, Kristallnacht 50th-anniversary week 1988
        "0422-S13": "PWV-13",  # 1968 service + Berlinger lecture invitation
        "0422-S16": "PWV-13",  # 1968 invitation reprise + Kristallnacht leaflets
        "0422-S18": "PWV-13",  # "Herzlich willkommen in Schwäbisch Hall"
    },
    # --- 0113-41 · Joseph Walk, 1969 journey ---
    "0113-41": {
        "0113-S02": "PWV-12",  # "Deutschland, eine Winterreise", 28.04.1969
    },
    # --- 0185-2 · Seligmann / Gerson, return to Germany 1995 ---
    "0185-2": {
        "0185-D11": "PWV-18",  # Givat Brenner life stories; return to Germany 1995
        "0185-D04": "PWV-18",  # Seligmann correspondence/diary, 1996
    },
}

RELEVANT = {"yes", "true", "1", "y"}

FIELDS = ["doc_id", "folder", "case_id", "page_range", "title", "date_text",
          "doc_type", "languages", "is_heimat_relevant", "include", "note"]


def load_cases():
    with VISITS.open(newline="", encoding="utf-8") as fh:
        return {r["case_id"]: r for r in csv.DictReader(fh, delimiter="\t")}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--folders", nargs="*", help="limit to these folders")
    ap.add_argument("--all-relevant", action="store_true",
                    help="also emit relevance-flagged docs outside the "
                         "allow-list, with include=no, for review")
    args = ap.parse_args()

    cases = load_cases()
    folders = args.folders or sorted(ALLOW)
    rows, missing = [], []

    for folder in folders:
        path = RECATALOG / folder / "catalog.tsv"
        if not path.exists():
            raise SystemExit(f"no catalog.tsv for {folder}")
        allow = ALLOW.get(folder, {})
        seen = set()
        with path.open(newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh, delimiter="\t"):
                doc_id = (r.get("doc_id") or "").strip()
                if not doc_id:
                    continue
                seen.add(doc_id)
                relevant = (r.get("is_heimat_relevant") or "").strip().lower()
                in_allow = doc_id in allow
                if not in_allow and not (args.all_relevant
                                         and relevant in RELEVANT):
                    continue
                case_id = allow.get(doc_id, "")
                if case_id and case_id not in cases:
                    raise SystemExit(f"{doc_id}: unknown case {case_id}")
                rows.append({
                    "doc_id": doc_id, "folder": folder, "case_id": case_id,
                    "page_range": (r.get("page_range") or "").strip(),
                    "title": (r.get("title") or "").strip(),
                    "date_text": (r.get("date_text") or "").strip(),
                    "doc_type": (r.get("doc_type") or "").strip(),
                    "languages": (r.get("languages") or "").strip(),
                    "is_heimat_relevant": relevant,
                    "include": "yes" if in_allow else "no",
                    "note": "" if in_allow else "relevance-flagged, not a visit doc",
                })
        missing += [f"{folder}/{d}" for d in allow if d not in seen]

    if missing:
        raise SystemExit("allow-list names doc_ids absent from catalog.tsv:\n  "
                         + "\n  ".join(missing))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, FIELDS, delimiter="\t", lineterminator="\n")
        w.writeheader()
        w.writerows(rows)

    included = sum(1 for r in rows if r["include"] == "yes")
    print(f"{included} visit documents ({len(rows)} rows) -> {OUT}")
    for folder in folders:
        n = sum(1 for r in rows if r["folder"] == folder and r["include"] == "yes")
        print(f"  {folder}: {n}")


if __name__ == "__main__":
    main()
