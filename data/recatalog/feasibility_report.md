# Feasibility & pricing — re-cataloguing pilot

Status: **7 pilot folders OCR'd + classified (1,686 pages); Worms fully catalogued;
6 folders segmentation in progress.** Date: 2026-07-05.

## Escalation is bimodal by folder type (the key scaling finding)

The free-Tesseract-handled share depends almost entirely on whether a folder is
print/book or handwritten correspondence:

| Folder | Person | Pages | Escalation (paid tail) |
|---|---|---|---|
| 0422-3 | Berlinger (publications) | 404 | **2%** |
| 0444-3 | Mannheimer / Worms (books+letters) | 252 | 14% |
| 0113-41 | Winterreise (lecture+mixed) | 396 | 21% |
| 0185-2 | Garzon / Wilma Adam | 223 | 22% |
| 0276-6 | Schopler / Cologne (corresp.) | 147 | 23% |
| 0047-2 | Leoni Frank (handwritten letters) | 158 | **65%** |
| 0047-4 | Ruppin/Landsberg (handwritten letters) | 106 | **80%** |
| **TOTAL** | | **1,686** | **24%** |

So a print/book-heavy folder costs almost nothing (2–22% tail); a
handwritten-correspondence folder flips to 65–80% paid tail. **The collection cost is
therefore driven by the print:handwriting ratio, not page count** — this is the number
to estimate before committing (the accession register's document-type fields can
predict it per folder in advance). Worms's 14% badly understated pure correspondence.

## What was measured (Worms 0444-3)

| Metric | Value |
|---|---|
| Pages | 252 |
| Scan volume | 630 MB (avg ~2.5 MB/page) |
| rclone sync | ~3 min (one-time auth already done) |
| Tesseract OCR | ~3.5 s/page → **~15 min/folder**, fully local, **$0** |
| Documents recovered | 11 (from a folder the legacy catalogue described in one flat blob) |
| Heimat-relevant docs | 5 of 11 (invitation, 1985 refusal, 1988 letters, press, notes) |

## Engine bake-offs

**PRINT — Tesseract (free) vs Google Vision.** On the 1964 invitation (clean German
typescript) the two were equivalent in readability; Tesseract preserved letterhead
layout **and got "an 3–5 Volkshochschulen" correct where Vision hallucinated "35".**
→ **Verdict: Tesseract-first for print.** Vision adds nothing on clean print and, at
scale, would cost ~$1.50/1000 pages via the Cloud Vision API. Reserve Vision for the
mid-confidence pages where Tesseract's layout parsing struggles.

**HANDWRITING — Claude vision vs Transkribus.** Tesseract returns near-zero on
cursive (confirmed). Google Vision *also* returns empty on the German/Hebrew
handwriting here. Claude vision read a faint-pencil Hebrew note only partially
(got the "1964" header + gist) — **faint pencil needs an image-preprocessing pass
(contrast/levels via sips/ImageMagick) before any engine.** Transkribus was **not**
run: our `transkribus_client.py` is download-only, so a proper comparison needs an
upload+recognise path (public German-Kurrent model) — a ~half-day build, worth doing
before committing the collection, since handwriting is the residual cost driver.

## The cost split that matters

Per-page confidence bucketing of the 252 Worms pages:

| Bucket | Pages | Share | Engine | Cost |
|---|---|---|---|---|
| high conf ≥0.85 (clean print) | 118 | 47% | Tesseract | free |
| mid 0.60–0.85 (usable print) | 98 | 39% | Tesseract (spot-check Vision) | ~free |
| low <0.60 (handwriting/photo/blank) | 36 | **14%** | Claude/Transkribus + preprocessing | paid/tokens |

**→ ~86% of pages are handled at $0 by the free local engine.** Only the ~14%
escalation tail carries marginal cost. Worms is book-heavy (a 69pp Fraktur book + two
copies of a ~50pp cemetery booklet), which inflates the free-print share; a
correspondence-heavy folder will have a larger handwriting tail.

## The accession register (ספר האוסף)

Each folder's scans open with its register card(s). It gives an **itemised content
inventory + descriptions + provenance** (donor, acquisition date, related holdings) —
but **no page→scan mapping**. So it is the "answer key" for *what* documents exist
(anchors Stage 3 cataloguing, turns Stage 2 into alignment-against-a-list) while the
page-range assignment is still done by our OCR spine.

## Human-in-the-loop (verify segmentation + catalogue)

Segmentation was agent-produced from the OCR "spine" (first legible line per page) and
is highly legible to a human reviewer as a compact table. For Worms, ~4 boundaries are
provisional (letter clusters pp8–24, pp25–33; the two interleaved booklet copies) and
flagged `NEEDS human split`. Estimated review: **~15–20 min/folder** for a folder this
size; less for smaller folders.

## Per-folder effort model

| Stage | Runner | Cost |
|---|---|---|
| rclone sync | script | ~3 min, $0 |
| Tesseract OCR (all pages) | script | ~15 min, $0 |
| classify → pages_ocr | script | seconds, $0 |
| escalate ~14% pages | agent (Claude vision) / Transkribus | tokens or ~€0.01–0.05/pg |
| segment → documents | agent | Claude tokens (one pass/folder) |
| re-catalogue → catalog | agent | Claude tokens (one pass/folder) |
| human verify seg+catalogue | human | ~15–20 min |
| facsimile mockup (relevant docs only) | script + sips | minutes, $0 |

## Full-collection projection (958 G-F folders)

Worms (252 pp) is a large folder; the collection also holds 5,374 books. Taking a
planning average of ~120 pp/folder → **~115,000 pages**.

- **OCR (print, Tesseract):** $0 compute, ~115k × 3.5 s ≈ **~110 machine-hours** (parallelisable; overnight on a few cores).
- **Escalation (~14% ≈ 16k pages):** if Claude vision, ~1–2k tokens/page in + output ≈ token cost to model; if Transkribus public model, ~€160–800 total. **This is the main $ lever — worth the Transkribus bake-off to choose.**
- **Vision fallback (mid pages, optional):** $0 via MCP for the pilot; ~$1.50/1000 pp (~$170) if scripted via Cloud Vision API at scale.
- **Human verification:** ~15 min × 958 ≈ **~240 person-hours** (the dominant *real* cost) — reducible by trusting the register list more and only spot-checking.

**Headline:** the free-Tesseract-first design keeps the compute bill near zero; the two
real costs are (1) the handwriting-escalation engine choice and (2) human verification
time. Both are measurable per-folder and both scale linearly — no blocker to
full-collection rollout once the Transkribus upload path and a contrast-preprocessing
step are added.

## Recommended next steps before scaling
1. Build the Transkribus upload+recognise path; run the handwriting bake-off vs Claude vision on ~20 real cursive pages (Ruppin 0047-4 + Mannheimer letters).
2. Add a contrast/levels preprocessing step for faint-pencil pages.
3. Process the remaining pilot folders (0113-41, 0422-3, 0276-6, 0047-2, 0185-2, 0047-4) to get a correspondence-heavy cost profile (larger handwriting tail).
4. Decide human-verification depth (full vs register-trust + spot-check) from the pilot review times.
