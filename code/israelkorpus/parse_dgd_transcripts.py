#!/usr/bin/env python3
"""Parse DGD (Datenbank für Gesprochenes Deutsch) transcript HTML pages
of the Israelkorpus (IS) into structured JSON.

Input:  data/israelkorpus/transcripts/*.html  (saved DGD transcript pages)
        data/israelkorpus/transcripts/*.pdf   (DGD PDF transcript exports)
Output: data/israelkorpus/structured/IS_E_XXXXX.json  (one per event)
        data/israelkorpus/structured/index.tsv        (corpus index)

Each JSON: {event_id, transcript_id, source_file, speakers: {label: dgd_id},
            contributions: [{n, cid, speaker, speaker_id, start, end, text}]}
"""
import json
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TRANSCRIPTS = REPO / "data/israelkorpus/transcripts"
OUT = REPO / "data/israelkorpus/structured"


class DGDTranscriptParser(HTMLParser):
    """Walk the <table class="transcript"> rows.

    Row layout: td.popr-cell | td.numbering | td.speaker | td.contribution
    Words are <span class="w" data-start data-end>; punctuation is
    <span class="w "> without timing; non-verbal events are <span class="nv" title="...">.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.transcript_id = None
        self.contributions = []
        self.speaker_ids = {}      # label -> IS--_S_xxxxx
        self._cur = None           # current contribution dict
        self._cell = None          # 'numbering' | 'speaker' | 'contribution' | None
        self._span = None          # 'w' | 'nv' | None
        self._buf = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "div" and a.get("class") == "popr":
            if self.transcript_id is None:
                self.transcript_id = a.get("data-transcript-id")
            self._cur = {"cid": a.get("data-c-id"), "time": a.get("data-time")}
        elif tag == "td" and self._cur is not None:
            cls = (a.get("class") or "").split()
            if "numbering" in cls:
                self._cell = "numbering"
                self._buf = []
            elif "speaker" in cls:
                self._cell = "speaker"
                self._buf = []
                m = re.match(r"(IS--_S_\d+)", a.get("title") or "")
                self._cur["speaker_id"] = m.group(1) if m else None
            elif "contribution" in cls:
                self._cell = "contribution"
                self._buf = []
                self._cur["start"] = float(a["cont_start"]) if a.get("cont_start") else None
                self._cur["end"] = float(a["cont_end"]) if a.get("cont_end") else None
        elif tag == "span" and self._cell == "contribution":
            cls = (a.get("class") or "").strip().split()
            if "w" in cls:
                self._span = "w"
            elif "nv" in cls:
                self._span = "nv"
                title = a.get("title") or ""
                self._buf.append(f" (({title})) ")

    def handle_endtag(self, tag):
        if tag == "span":
            if self._span == "w":
                self._buf.append(" ")
            self._span = None
        elif tag == "td" and self._cell:
            text = "".join(self._buf).strip()
            if self._cell == "numbering":
                self._cur["n"] = int(text) if text.isdigit() else text
            elif self._cell == "speaker":
                self._cur["speaker"] = text
                if self._cur.get("speaker_id") and text:
                    self.speaker_ids[text] = self._cur["speaker_id"]
            elif self._cell == "contribution":
                self._cur["text"] = clean_text(text)
                self.contributions.append(self._cur)
                self._cur = None
            self._cell = None

    def handle_data(self, data):
        if self._cell == "numbering" or self._cell == "speaker":
            self._buf.append(data)
        elif self._cell == "contribution" and self._span == "w":
            self._buf.append(data)


def clean_text(t: str) -> str:
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r" ([,.;:!?])", r"\1", t)   # reattach punctuation spans
    return t.strip()


def parse_html(path: Path):
    p = DGDTranscriptParser()
    p.feed(path.read_text(encoding="utf-8"))
    if not p.transcript_id:
        return None
    event_id = re.sub(r"^(IS)--_(E_\d+).*", r"\1_\2", p.transcript_id)
    return {
        "event_id": event_id,
        "transcript_id": p.transcript_id,
        "source_file": path.name,
        "source": "html",
        "speakers": p.speaker_ids,
        "contributions": p.contributions,
    }


PDF_LABELED = re.compile(r"^\s*(?:\d+\s+)?([A-ZÄÖÜ]{1,4}):\s*(.*)$")
PDF_COMMENT = re.compile(r"^\s*(?:\d+\s+)?K\s\s")
PDF_CONT = re.compile(r"^\s*(?:\d+\s+)?(\S.*)$")


def _append(cur, chunk):
    chunk = chunk.strip()
    if not chunk:
        return
    if cur["text"].endswith("-"):
        cur["text"] = cur["text"][:-1] + chunk
    else:
        cur["text"] += " " + chunk


def parse_pdf(path: Path):
    """Older DGD 'Partitur' PDF exports: numbered lines, 'MD:'/'AF:' speaker
    codes, 'K' comment lines (skipped), continuation lines numbered but
    unlabeled, words hyphen-wrapped across lines."""
    txt = subprocess.run(["pdftotext", "-layout", str(path), "-"],
                         capture_output=True, text=True, check=True).stdout
    m = re.match(r"(IS--_E_\d+\S*)", path.stem)
    transcript_id = m.group(1) if m else path.stem
    event_id = re.sub(r"^(IS)--_(E_\d+).*", r"\1_\2", transcript_id)
    contributions = []
    cur = None
    n = 0
    for line in txt.splitlines():
        s = line.strip()
        if (not s or s.isdigit() or s.startswith("IS--_E_")
                or "INSTITUT FÜR DEUTSCHE SPRACHE" in s):
            continue
        if PDF_COMMENT.match(line):
            continue
        lm = PDF_LABELED.match(line)
        if lm:
            spk = lm.group(1)
            if spk == "K":       # comment tier (prosody notes), not speech
                continue
            if cur and cur["speaker"] == spk:
                _append(cur, lm.group(2))
            else:
                if cur:
                    cur["text"] = clean_text(cur["text"])
                    contributions.append(cur)
                n += 1
                cur = {"n": n, "cid": None, "speaker": spk, "speaker_id": None,
                       "start": None, "end": None, "text": lm.group(2)}
            continue
        cm = PDF_CONT.match(line)
        if cm and cur is not None:
            _append(cur, cm.group(1))
    if cur:
        cur["text"] = clean_text(cur["text"])
        contributions.append(cur)
    return {
        "event_id": event_id,
        "transcript_id": transcript_id,
        "source_file": path.name,
        "source": "pdf",
        "speakers": {},
        "contributions": contributions,
    }


# interviewee speaker IDs for the PDF-derived events (no IDs in the PDFs;
# identified from transcript openings + the DGD speaker list)
PDF_SPEAKERS = {
    "IS_E_00042": "IS--_S_00051",  # Friedländer, Abraham H.
    "IS_E_00043": "IS--_S_00051",
    "IS_E_00105": "IS--_S_00123",  # Rothschild, Charlotte
    "IS_E_00109": "IS--_S_00126",  # Rudberg, Hilde
    "IS_E_00110": "IS--_S_00126",
    "IS_E_00114": "IS--_S_00132",  # Schwarz-Gardos, Alice
}


def load_speakers():
    path = REPO / "data/israelkorpus/speakers.tsv"
    table = {}
    if path.exists():
        for line in path.read_text().splitlines()[1:]:
            sid, name, by, sex = line.split("\t")
            table[sid] = (name, by, sex)
    return table


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    records = []
    for f in sorted(TRANSCRIPTS.glob("*.html")):
        if f.name.startswith("metadata-"):
            continue
        rec = parse_html(f)
        if rec:
            records.append(rec)
    for f in sorted(TRANSCRIPTS.glob("*.pdf")):
        records.append(parse_pdf(f))

    # dedupe: prefer html if same event twice
    by_event = {}
    for r in records:
        if r["event_id"] not in by_event or r["source"] == "html":
            by_event[r["event_id"]] = r

    speakers = load_speakers()
    index_rows = []
    for eid, r in sorted(by_event.items()):
        sids = sorted(set(r["speakers"].values()))
        if not sids and eid in PDF_SPEAKERS:
            sids = [PDF_SPEAKERS[eid]]
        bios = [speakers.get(s) for s in sids if s in speakers]
        r["interviewees"] = [
            {"speaker_id": s, "name": b[0], "birth_year": b[1], "sex": b[2]}
            for s, b in zip(sids, bios)]
        out_path = OUT / f"{eid}.json"
        out_path.write_text(json.dumps(r, ensure_ascii=False, indent=1))
        words = sum(len(c["text"].split()) for c in r["contributions"])
        ends = [c["end"] for c in r["contributions"] if c.get("end")]
        dur = max(ends) if ends else None
        index_rows.append([
            eid, r["transcript_id"], r["source_file"], r["source"],
            ";".join(sids),
            "; ".join(b[0] for b in bios),
            ";".join(b[1] for b in bios),
            str(len(r["contributions"])), str(words),
            f"{dur/60:.1f}" if dur else "",
        ])
    header = ["event_id", "transcript_id", "source_file", "source",
              "speaker_ids", "interviewees", "birth_years",
              "n_contributions", "n_words", "duration_min"]
    (OUT / "index.tsv").write_text(
        "\t".join(header) + "\n" +
        "\n".join("\t".join(row) for row in index_rows) + "\n")
    print(f"{len(by_event)} events -> {OUT}")
    for row in index_rows:
        print("  ", "\t".join(row))


if __name__ == "__main__":
    main()
