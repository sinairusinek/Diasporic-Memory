"""Extract structured sender/recipient/place/date fields from trilingual
descriptions of letters and postcards in Jecke-items.tsv.

Reads:  data/JeckeArchive/Jecke-items.tsv
Writes: data/JeckeArchive/letters_enriched.tsv

Usage:
  python code/extract_letter_metadata.py --limit 5      # smoke test
  python code/extract_letter_metadata.py --limit 50     # validate
  python code/extract_letter_metadata.py                # full run (~2067 items)
  python code/extract_letter_metadata.py --resume       # skip already-done IDs

Cost: ~$5-15 for full run with Opus 4.7 + prompt caching.
Use --model claude-sonnet-4-6 for ~3x cheaper if quality is sufficient.
"""
from __future__ import annotations
import argparse, csv, json, os, sys
from pathlib import Path
import anthropic

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data/JeckeArchive/Jecke-items.tsv"
OUT = ROOT / "data/JeckeArchive/letters_enriched.tsv"

OUT_FIELDS = [
    "item_id", "from_person", "to_person", "from_place", "to_place",
    "send_date", "mentioned_places", "mentioned_persons",
    "is_heimat_relevant", "notes",
]

SYSTEM_PROMPT = """You extract structured metadata from trilingual (Hebrew/German/English) archival descriptions of letters and postcards from the Jecke Archive (German-Jewish refugees and their descendants).

For each item you receive a description in up to three languages (Hebrew item_description, German translation, English translation). Cross-validate across all three to maximize accuracy.

Extract the following, returning NULL when not stated:
- from_person: sender's full name (preserve original spelling; prefer Latin script)
- to_person: recipient's full name
- from_place: place letter was sent FROM (city, ideally with country)
- to_place: place letter was sent TO
- send_date: date written or sent (YYYY, YYYY-MM, or YYYY-MM-DD)
- mentioned_places: other places named in the description (semicolon-separated)
- mentioned_persons: other people named (semicolon-separated)
- is_heimat_relevant: true if the letter relates to German-speaking origins, return visits, correspondence with people remaining in/from Germany/Austria/Central Europe, or memory of pre-emigration life. False for purely local/Israeli matters or unrelated WWI/family correspondence with no Heimat dimension.
- notes: brief (<=15 words) note on anything ambiguous or interesting (e.g. "letter found inside notebook", "posthumous collection")

Rules:
- For collections of multiple letters: extract the dominant/representative sender-recipient pair if clear; otherwise leave persons NULL and explain in notes.
- "Heimat" in this project = the Central European German-speaking origin world. WWI front-line correspondence is NOT Heimat-relevant unless it involves the diasporic-memory dimension.
- Names: prefer Latin script. Hebrew-only names: transliterate.
- Return STRICT JSON only, matching the schema."""

SCHEMA = {
    "type": "object",
    "properties": {
        "from_person": {"type": ["string", "null"]},
        "to_person": {"type": ["string", "null"]},
        "from_place": {"type": ["string", "null"]},
        "to_place": {"type": ["string", "null"]},
        "send_date": {"type": ["string", "null"]},
        "mentioned_places": {"type": ["string", "null"]},
        "mentioned_persons": {"type": ["string", "null"]},
        "is_heimat_relevant": {"type": "boolean"},
        "notes": {"type": ["string", "null"]},
    },
    "required": ["from_person", "to_person", "from_place", "to_place",
                 "send_date", "mentioned_places", "mentioned_persons",
                 "is_heimat_relevant", "notes"],
    "additionalProperties": False,
}


def is_letter(row: dict) -> bool:
    dt = (row.get("document_type") or "")
    return any(k in dt for k in ("Letter", "Postcard", "מכתב", "גלויה"))


def build_user_msg(row: dict) -> str:
    parts = [f"item_id: {row['item_id']}"]
    if row.get("title"):
        parts.append(f"title: {row['title']}")
    if row.get("creation_date"):
        parts.append(f"creation_date_field: {row['creation_date']}")
    if row.get("main_subject"):
        parts.append(f"main_subject_field: {row['main_subject']}")
    if row.get("item_description"):
        parts.append(f"\nHebrew description:\n{row['item_description']}")
    if row.get("german_translation"):
        parts.append(f"\nGerman:\n{row['german_translation']}")
    if row.get("english_translation"):
        parts.append(f"\nEnglish:\n{row['english_translation']}")
    return "\n".join(parts)


def extract_one(client: anthropic.Anthropic, model: str, row: dict) -> dict:
    resp = client.messages.create(
        model=model,
        max_tokens=600,
        system=[{
            "type": "text",
            "text": SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{"role": "user", "content": build_user_msg(row)}],
        output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
    )
    text = next(b.text for b in resp.content if b.type == "text")
    data = json.loads(text)
    return data, resp.usage


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="claude-opus-4-7")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--resume", action="store_true",
                    help="Skip item_ids already present in output file")
    args = ap.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Set ANTHROPIC_API_KEY")

    done = set()
    if args.resume and OUT.exists():
        with open(OUT, encoding="utf-8") as f:
            for r in csv.DictReader(f, delimiter="\t"):
                done.add(r["item_id"])
        print(f"Resuming: {len(done)} already done", file=sys.stderr)

    with open(SRC, encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f, delimiter="\t") if is_letter(r)]
    print(f"Found {len(rows)} letters/postcards", file=sys.stderr)

    rows = [r for r in rows if r["item_id"] not in done]
    if args.limit:
        rows = rows[:args.limit]
    print(f"Processing {len(rows)} items with {args.model}", file=sys.stderr)

    client = anthropic.Anthropic()
    mode = "a" if (args.resume and OUT.exists()) else "w"
    with open(OUT, mode, encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=OUT_FIELDS, delimiter="\t")
        if mode == "w":
            w.writeheader()

        total_in = total_out = total_cached = 0
        for i, row in enumerate(rows, 1):
            try:
                data, usage = extract_one(client, args.model, row)
            except Exception as e:
                print(f"FAIL {row['item_id']}: {e}", file=sys.stderr)
                continue
            data["item_id"] = row["item_id"]
            w.writerow({k: data.get(k) for k in OUT_FIELDS})
            f.flush()

            total_in += usage.input_tokens
            total_out += usage.output_tokens
            total_cached += usage.cache_read_input_tokens or 0
            if i % 25 == 0 or i == len(rows):
                print(f"[{i}/{len(rows)}] in={total_in} out={total_out} "
                      f"cached={total_cached} ({100*total_cached/max(1,total_in+total_cached):.0f}%)",
                      file=sys.stderr)

    print(f"Wrote {OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
