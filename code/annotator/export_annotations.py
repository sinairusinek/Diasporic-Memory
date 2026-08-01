#!/usr/bin/env python3
"""Export the PI's annotations from Postgres back into the repo.

Postgres is a cache; the repo is the record. Two forms come out:

  annotations.tsv   flat and readable without the JSON — one row per
                    annotation, resolved to its page or speaker turn
  annotations.json  W3C Web Annotation, target.selector carrying both a
                    TextQuoteSelector and a TextPositionSelector. This is the
                    archival form: it survives a re-render, a re-translation,
                    and this repository.

Oral-testimony rows are DGD-licensed and their quotes are redacted in the
committed TSV until the publication question is settled; the unredacted file is
written alongside and gitignored.

Usage: python code/annotator/export_annotations.py --dsn "$POSTGRES_URL"
"""
import argparse
import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DOCS = REPO / "data/annotator/docs"
OUT = REPO / "data/annotator"

FIELDS = ["annotation_id", "case_id", "doc_id", "kind", "pane", "lang",
          "start_offset", "end_offset", "quote", "prefix", "suffix",
          "locator", "type", "value", "status", "created_at", "updated_at"]


def load_docs():
    out = {}
    for f in sorted(DOCS.glob("*.json")):
        out[f.stem] = json.loads(f.read_text(encoding="utf-8"))
    return out


def locator(doc, pane_name, start, end):
    """Human-readable position: 'p. 51' or 'turn 96 @ 00:41:15'."""
    pane = doc["panes"].get(pane_name) or {}
    for b in pane.get("pages") or []:
        if b["start"] <= start < b["end"] or b["start"] < end <= b["end"]:
            return f"p. {b['page_no']}"
    for b in pane.get("segments") or []:
        if b["start"] <= start < b["end"] or b["start"] < end <= b["end"]:
            t = b.get("start_sec")
            stamp = ""
            if isinstance(t, (int, float)):
                s = int(t)
                stamp = f" @ {s//3600:02d}:{s%3600//60:02d}:{s%60:02d}"
            return f"turn {b.get('n', '?')}{stamp}"
    return ""


def value_of(kind, body):
    if kind == "comment":
        return body.get("text", "")
    if kind == "tag":
        return body.get("tag", "")
    return "; ".join(body.get("keywords", []))


DEV_STORE = REPO / "annotator/.dev-data/annotations.json"


def fetch_postgres(dsn):
    import psycopg2
    import psycopg2.extras
    with psycopg2.connect(dsn) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                select id, doc_id, pane, kind, start_offset, end_offset,
                       quote, prefix, suffix, pane_sha256, body, status,
                       created_at, updated_at
                  from annotation
                 order by doc_id, pane, start_offset, id""")
            return [dict(r) for r in cur.fetchall()]


def fetch_dev_store():
    """The local file store used when POSTGRES_URL is unset (see lib/store.ts)."""
    data = json.loads(DEV_STORE.read_text(encoding="utf-8"))
    rows = data.get("annotations", [])
    for r in rows:
        for k in ("created_at", "updated_at"):
            r[k] = datetime.fromisoformat(r[k].replace("Z", "+00:00"))
    return sorted(rows, key=lambda r: (r["doc_id"], r["pane"],
                                       r["start_offset"], r["id"]))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dsn", default=os.environ.get("POSTGRES_URL"))
    args = ap.parse_args()

    docs = load_docs()
    if args.dsn:
        rows = fetch_postgres(args.dsn)
    elif DEV_STORE.exists():
        print(f"POSTGRES_URL unset — exporting the local dev store "
              f"({DEV_STORE.relative_to(REPO)})")
        rows = fetch_dev_store()
    else:
        raise SystemExit("set POSTGRES_URL or pass --dsn")

    flat, redacted, web = [], [], []
    for r in rows:
        doc = docs.get(r["doc_id"])
        if doc is None:
            continue
        body = r["body"] if isinstance(r["body"], dict) else json.loads(r["body"])
        pane = doc["panes"].get(r["pane"]) or {}
        row = {
            "annotation_id": r["id"],
            "case_id": doc["case_id"],
            "doc_id": r["doc_id"],
            "kind": doc["kind"],
            "pane": r["pane"],
            "lang": pane.get("lang", ""),
            "start_offset": r["start_offset"],
            "end_offset": r["end_offset"],
            "quote": r["quote"].replace("\t", " ").replace("\n", " "),
            "prefix": r["prefix"].replace("\t", " ").replace("\n", " "),
            "suffix": r["suffix"].replace("\t", " ").replace("\n", " "),
            "locator": locator(doc, r["pane"], r["start_offset"], r["end_offset"]),
            "type": r["kind"],
            "value": value_of(r["kind"], body).replace("\t", " ").replace("\n", " "),
            "status": r["status"],
            "created_at": r["created_at"].isoformat(),
            "updated_at": r["updated_at"].isoformat(),
        }
        flat.append(row)
        if doc["public"]:
            redacted.append(row)
        else:
            redacted.append({**row, "quote": "[DGD-restricted]",
                             "prefix": "", "suffix": ""})

        web.append({
            "@context": "http://www.w3.org/ns/anno.jsonld",
            "id": f"urn:jecke:annotation:{r['id']}",
            "type": "Annotation",
            "created": row["created_at"],
            "modified": row["updated_at"],
            "motivation": {"comment": "commenting", "tag": "tagging",
                           "keywords": "tagging"}[r["kind"]],
            "body": ([{"type": "TextualBody", "purpose": "commenting",
                       "value": body["text"]}] if r["kind"] == "comment" else
                     [{"type": "TextualBody", "purpose": "tagging",
                       "value": body["tag"]}] if r["kind"] == "tag" else
                     [{"type": "TextualBody", "purpose": "tagging", "value": k}
                      for k in body["keywords"]]),
            "target": {
                "source": f"urn:jecke:doc:{r['doc_id']}#{r['pane']}",
                "selector": [
                    {"type": "TextQuoteSelector", "exact": r["quote"],
                     "prefix": r["prefix"], "suffix": r["suffix"]},
                    {"type": "TextPositionSelector",
                     "start": r["start_offset"], "end": r["end_offset"]},
                ],
                "state": {"type": "HttpRequestState",
                          "refinedBy": {"type": "ContentHash",
                                        "value": r["pane_sha256"]}},
            },
            "generator": {"type": "Software", "name": "jecke-annotator"},
            "rights": None if doc["public"] else "DGD-restricted",
        })

    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")

    def write_tsv(path, data):
        with path.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, FIELDS, delimiter="\t", lineterminator="\n")
            w.writeheader()
            w.writerows(data)

    write_tsv(OUT / "annotations.tsv", redacted)
    write_tsv(OUT / "annotations_unredacted.tsv", flat)
    (OUT / "annotations.json").write_text(
        json.dumps({"exported_at": stamp, "annotations": web},
                   ensure_ascii=False, indent=1), encoding="utf-8")

    n_restricted = sum(1 for r in flat if r["quote"] != "" and
                       not docs[r["doc_id"]]["public"])
    print(f"{len(flat)} annotations exported")
    print(f"  data/annotator/annotations.tsv   ({n_restricted} quotes redacted)")
    print(f"  data/annotator/annotations.json  (W3C Web Annotation)")
    print(f"  data/annotator/annotations_unredacted.tsv  (gitignored)")


if __name__ == "__main__":
    main()
