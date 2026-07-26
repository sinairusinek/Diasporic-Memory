#!/usr/bin/env python3
"""Scan structured Israelkorpus transcripts for Heimat / return-visit signals.

Categories (kept separate per the project's annotation conventions —
Heimat and Vaterland are distinct evidentiary axes; only explicit lexemes
count as Heimat, per feedback-no-forced-heimat-framing):

  heimat       explicit Heimat lexemes (Heimat*, Heimweh, daheim, heimisch)
  vaterland    Vaterland / Deutschtum (coded separately, never merged)
  return_visit explicit return lexemes (Rückkehr, Rückreise, zurückgekehrt,
               Wiedersehen mit, remigriert) OR 'Deutschland' co-occurring
               with a travel/return verb in the same or adjacent contribution
  invitation   Einladung/eingeladen near Deutschland / Stadt / Bürgermeister
               (municipal visitor programs)
  restitution  Wiedergutmachung / Entschädigung / Restitution

Input:  data/israelkorpus/structured/IS_E_*.json
Output: data/israelkorpus/heimat_scan.tsv   (one row per hit)
        data/israelkorpus/heimat_scan_report.md (human-readable digest)
"""
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
STRUCTURED = REPO / "data/israelkorpus/structured"

# --- direct lexeme categories (regex on normalized lowercase text) ---
DIRECT = {
    "heimat": re.compile(
        r"\bheimat\w*|\bheimweh\w*|\bdaheim\b|\bheimisch\w*|\bheim=at"),
    "vaterland": re.compile(r"\bvaterland\w*|\bdeutschtum\w*"),
    "return_visit_lexeme": re.compile(
        r"\brückkehr\w*|\brückreise\w*|\bzurückgekehrt\w*|\bzurückkehren\w*"
        r"|\bremigr\w*|\brückwander\w*|\bwiedersehen mit\b"),
    "invitation": re.compile(r"\beinladung\w*|\beingeladen\b|\beinladen\b"),
    "restitution": re.compile(
        r"\bwiedergutmachung\w*|\bentschädigung\w*|\brestitution\w*"),
}

# --- return-visit phrase patterns ---
CITIES = (r"deutschland|berlin|hamburg|frankfurt|münchen|köln|leipzig|breslau"
          r"|königsberg|stuttgart|düsseldorf|wuppertal|elberfeld|mannheim"
          r"|heidelberg|nürnberg|dresden|hannover|kassel|essen|dortmund"
          r"|bremen|aachen|würzburg|bonn|europa")
# tier A: explicit return phrasing
STRONG = re.compile(
    rf"zurück nach ({CITIES})|nach ({CITIES}) zurück"
    rf"|wieder nach ({CITIES})|wieder in ({CITIES})"
    rf"|nach deutschland (ge)?fahren|nach deutschland geflogen"
    rf"|nach deutschland gereist|deutschland besucht"
    rf"|besuch\w* in deutschland|reise\w* nach deutschland"
    rf"|in deutschland gewesen|wieder (hin|dort|da) ?gewesen"
    rf"|zum ersten mal wieder|das erste mal wieder"
    rf"|nie (mehr |wieder )?nach deutschland|nicht mehr nach deutschland")
# tier B: loose co-occurrence, kept as candidates for manual review
ANCHOR = re.compile(r"\bdeutschland\b")
TRAVEL = re.compile(
    r"\bzurück\w*\b|\bbesuch\w*\b|\bgefahren\b|\bgeflogen\b|\bgereist\b"
    r"|\breise\w*\b|\bwiedersehen\b|\beingeladen\b")
# invitation needs a German anchor nearby to count
INVITE_ANCHOR = re.compile(
    r"\bdeutschland\b|\bstadt\b|\bbürgermeister\w*|\bgemeinde\b|\bsenat\w*"
    r"|\bdeutsche\w*\b")

ARTIFACTS = re.compile(r"[↑↓#]|\*+|\(\([^)]*\)\)|=")


def norm(t: str) -> str:
    t = ARTIFACTS.sub(" ", t.lower())
    return re.sub(r"\s+", " ", t)


def snippet(text: str, m: re.Match, pad=160) -> str:
    a, b = max(0, m.start() - pad), min(len(text), m.end() + pad)
    s = ("…" if a else "") + text[a:b].strip() + ("…" if b < len(text) else "")
    return re.sub(r"\s+", " ", s)


def hhmmss(sec):
    if sec is None:
        return ""
    s = int(sec)
    return f"{s//3600:02d}:{s%3600//60:02d}:{s%60:02d}"


def main():
    rows = []
    events = []
    for f in sorted(STRUCTURED.glob("IS_E_*.json")):
        rec = json.loads(f.read_text())
        contribs = rec["contributions"]
        normed = [norm(c["text"]) for c in contribs]
        n_hits = 0
        for i, c in enumerate(contribs):
            t = normed[i]
            if not t:
                continue
            cats = {}
            for cat, rx in DIRECT.items():
                m = rx.search(t)
                if m:
                    if cat == "invitation" and not INVITE_ANCHOR.search(
                            " ".join(normed[max(0, i - 1):i + 2])):
                        continue
                    cats[cat] = m
            sm = STRONG.search(t)
            if sm:
                cats["return_visit_strong"] = sm
            elif "return_visit_lexeme" not in cats:
                am = ANCHOR.search(t)
                if am:
                    window = " ".join(normed[max(0, i - 1):i + 2])
                    if TRAVEL.search(window):
                        cats["return_visit_candidate"] = am
            for cat, m in cats.items():
                rows.append({
                    "event_id": rec["event_id"],
                    "n": c["n"], "speaker": c.get("speaker", ""),
                    "time": hhmmss(c.get("start")),
                    "category": cat, "match": m.group(0),
                    "snippet": snippet(t, m),
                })
                n_hits += 1
        events.append((rec["event_id"], rec["source_file"], len(contribs), n_hits))

    out = REPO / "data/israelkorpus/heimat_scan.tsv"
    header = ["event_id", "n", "speaker", "time", "category", "match", "snippet"]
    with out.open("w") as fh:
        fh.write("\t".join(header) + "\n")
        for r in rows:
            fh.write("\t".join(str(r[h]) for h in header) + "\n")
    print(f"{len(rows)} hits -> {out}")
    from collections import Counter
    print(Counter(r["category"] for r in rows))
    print(Counter(r["event_id"] for r in rows))


if __name__ == "__main__":
    main()
