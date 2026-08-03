#!/usr/bin/env python3
"""Export clean-text Markdown from structured Israelkorpus JSONs.

Reads data/israelkorpus/structured/IS_E_*.json, strips transcription
notation (DGD literary + GAT2), and writes one Markdown file per
interview to data/israelkorpus/md/ — meant to be uploaded to Drive and
opened as Google Docs.
"""
import json
import re
import csv
import unicodedata
from pathlib import Path

BASE = Path(__file__).resolve().parents[2] / "data" / "israelkorpus"
STRUCTURED = BASE / "structured"
OUT = BASE / "md"

KNOWN_INTERVIEWERS = {
    "AB": "Anne Betten",
    "S1": "Interviewerin",  # HTML transcripts: unmapped S1 is the interviewer
}

# GAT2 / literary-transcription noise
RE_PAUSE_PAREN = re.compile(r"\((?:-+|\d+(?:[.,]\d+)?)\)")   # (-) (--) (2.3)
RE_BREATH = re.compile(r"(?<![\w])[°]?\.?h{1,3}[.°]?(?![\w])")  # .h .hh h. °h
RE_MULTISPACE = re.compile(r"\s+")


def clean_text(text: str, source: str) -> str:
    # ((Überlappung)), ((kurze Pause)), (()), ((Rohtranskript ...)) etc.,
    # including unbalanced "((Rohtranskript ...)" variants
    t = re.sub(r"\(\([^()]*\)?\)?", " ", text)
    if source == "pdf":
        # GAT2 stress accents: geheíraded -> geheiraded
        t = unicodedata.normalize("NFD", t)
        t = "".join(c for c in t if c not in "́̀")
        t = unicodedata.normalize("NFC", t)
        t = RE_PAUSE_PAREN.sub(" ", t)
        t = RE_BREATH.sub(" ", t)
        # intonation, pause, emphasis, latching, overlap markers
        t = re.sub(r"[↑↓*#=+|<>\[\]]", " ", t)
        # trailing slash on false starts: "ei/" -> "ei-"
        t = re.sub(r"(\w)/(\s|$)", r"\1-\2", t)
        # accent capitals inside otherwise-lowercase words: grOßmutter -> großmutter
        t = " ".join(
            w.lower() if (any(c.isupper() for c in w[1:]) and not w.isupper()) else w
            for w in t.split(" ")
        )
    else:
        t = re.sub(r"[|↑↓#=]", " ", t)
    return RE_MULTISPACE.sub(" ", t).strip()


def display_name(kalliope_name: str) -> str:
    """'Walk, Joseph' -> 'Joseph Walk'"""
    if "," in kalliope_name:
        last, first = kalliope_name.split(",", 1)
        return f"{first.strip()} {last.strip()}"
    return kalliope_name


def load_index():
    idx = {}
    with open(STRUCTURED / "index.tsv") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            idx[row["event_id"]] = row
    return idx


def export_one(path: Path, index: dict) -> tuple[str, str]:
    d = json.load(open(path))
    event_id = d["event_id"]
    meta = index.get(event_id, {})

    # speaker code -> display name
    id2name = {p["speaker_id"]: display_name(p["name"]) for p in d["interviewees"]}
    code2name = {}
    for code, sid in d["speakers"].items():
        if sid in id2name:
            code2name[code] = id2name[sid]
    # PDF transcripts identify speakers by initials matching the interviewees;
    # try both full initials (AHF) and first+last (AF)
    if d["source"] == "pdf" and not code2name:
        for p in d["interviewees"]:
            nm = display_name(p["name"])
            words = [w for w in nm.split() if w[0].isupper()]
            variants = {"".join(w[0] for w in words)}
            if len(words) > 1:
                variants.add(words[0][0] + words[-1][0])
            # hyphenated surname: Schwarz-Gardos -> SG
            variants.add("".join(p[0] for p in words[-1].split("-") if p).upper())
            for variant in variants:
                code2name[variant] = nm

    names = [display_name(p["name"]) for p in d["interviewees"]]
    title_names = " & ".join(names) if names else event_id
    years = "; ".join(
        f"{display_name(p['name'])} (geb. {p['birth_year']})" for p in d["interviewees"]
    )

    lines = [
        f"# {title_names} — Israelkorpus {event_id}",
        "",
        f"**Transkript:** {d['transcript_id']} (DGD, IDS Mannheim)  ",
        f"**Interviewpartner:** {years}  ",
        f"**Korpus:** Israelkorpus IS (Anne Betten u. a.)  ",
    ]
    if meta:
        dur = meta.get("duration_min", "")
        dur_s = f", Dauer ca. {float(dur):.0f} Min." if dur else ""
        lines.append(f"**Umfang:** {meta['n_words']} Wörter{dur_s}  ")
    lines += [
        "",
        "*Automatisch bereinigter Lesetext; Transkriptionszeichen (Pausen, "
        "Intonation, Überlappungen) wurden entfernt. Quelle: DGD-Volltext, "
        "nur für den internen Projektgebrauch.*",
        "",
        "---",
        "",
    ]

    # merge consecutive contributions by the same speaker
    merged = []
    for c in d["contributions"]:
        text = clean_text(c["text"], d["source"])
        if not text:
            continue
        code = c["speaker"] or "?"
        if merged and merged[-1][0] == code:
            merged[-1][1].append(text)
        else:
            merged.append([code, [text]])

    for code, chunks in merged:
        label = code2name.get(code) or KNOWN_INTERVIEWERS.get(code) or f"Sprecher:in {code}"
        lines.append(f"**{label}:** {' '.join(chunks)}")
        lines.append("")

    fname = f"{event_id} – {title_names}.md"
    (OUT / fname).write_text("\n".join(lines))
    return fname, f"{len(merged)} Redebeiträge"


def main():
    OUT.mkdir(exist_ok=True)
    index = load_index()
    files = sorted(STRUCTURED.glob("IS_E_*.json"))
    readme = ["# Israelkorpus — bereinigte Lesetexte (Pilotkorpus, 22 Interviews)", ""]
    for path in files:
        fname, info = export_one(path, index)
        print(f"{fname}  ({info})")
        readme.append(f"- {fname} ({info})")
    (OUT / "00_INDEX.md").write_text("\n".join(readme) + "\n")
    print(f"\n{len(files)} Dateien + 00_INDEX.md in {OUT}")


if __name__ == "__main__":
    main()
