# Re-cataloguing + Page-Mapping + OCR pipeline

Pilot implementation of the plan in `~/.claude/plans/expressive-orbiting-reddy.md`.
Turns each `IL-MTFN-001-G-F-XXXX` scan folder into: a page→document map, a clean
trilingual catalogue, and per-page transcriptions — instrumented for cost so we can
project scaling to the whole MTFN collection.

## Why

Scans live in Google Drive with **folder-wide page numbering** and *scan order ≠
document order*; there is **no item→page map**; the legacy catalogue
(`data/Documents2024-12-13.tsv`) is inconsistent/incomplete. Google Vision reads
printed pages perfectly but returns **empty on German handwriting** (verified).

## Architecture: this is a HYBRID pipeline

Some steps only the **agent (Claude Code, in-session)** can run because they use the
Google Drive / Vision MCP tools, which are NOT callable from standalone scripts.
Other steps are **plain scripts** (rclone, Transkribus, text processing). Split:

| Stage | Runner | Mechanism |
|---|---|---|
| 0 Acquire (image binaries) | script | `rclone copy` (needs one-time `rclone config`) |
| 0 Inventory (page list) | agent | Drive MCP `search_files` (paginated) |
| 1 OCR — print **bake-off** | script + agent | **Tesseract** (`ocr_tesseract.py`, FREE/local, no tokens) **vs** Google Vision (Drive MCP `read_file_content`) — compare quality & price |
| 1 OCR — handwriting **bake-off** | script + agent | Transkribus HTR (`code/transkribus_client.py`) **vs** Claude vision (agent reads JPEG) |
| 1 Classify pages | agent | heuristic: empty Vision text + non-blank image ⇒ handwriting; Vision labels refine type |

Two bake-offs run in the pilot so we can pick the cheapest engine that meets quality:
**print** = Tesseract (free) vs Vision; **handwriting** = Transkribus vs Claude vision.
Default routing target after the pilot: free Tesseract for clean print, escalate only
where its `mean_conf` is low; reserve paid/token engines for handwriting.
| 2 Segment → documents | agent + human | LLM boundary detection; **human verifies** |
| 3 Re-catalogue | agent + human | LLM structured metadata; **human verifies** |
| 4 Facsimile mockups | script | `mockups/_shared/frame.*`; `sips` to shrink images |
| 5 Feasibility memo | script | `metrics.py` |

> Scaling note: at full-collection scale, Stage-1 print OCR should move off the MCP
> tool onto a batched **Google Cloud Vision API key** (not yet provisioned). The pilot
> uses the MCP `read_file_content` to measure quality/throughput first.

## The accession register (ספר האוסף) — what it does and does NOT give

Each folder's scans **open with its accession-register card(s)** (e.g. Worms `0444-3`
pages 1–4). These provide, per folder:
- ✅ an **itemized content inventory** — the documents in the folder, grouped by
  category, each with a description, date, language, and sometimes a page count;
- ✅ **provenance/donor** metadata (donor, acquisition date, related holdings);
- ❌ **no page→scan mapping** — the register does *not* say which scan pages hold
  which item.

Consequence: the register is the **"answer key" of what documents exist** (drives
Stage 3 cataloguing and gives Stage 2 a known target list), but assigning
**scan-page ranges to each item is still done by Stage 2 OCR boundary-detection**.
Segmentation is therefore *alignment against a known item list*, not blind hunting.

**IMPORTANT (pilot finding):** a register card is **NOT reliably present** — only 1 of
the 7 pilot folders (Worms 0444) opened with one. The others begin directly with
content (a poem, press clippings, Yad Vashem pages of testimony, a conference program).
So segmentation must work from the OCR spine **without** an answer-key in most folders —
which it did successfully. Do not assume a register card exists; detect and use it when
present, fall back to pure boundary-detection otherwise.

## Per-folder output layout

```
data/recatalog/<folder>/
  scans/            page JPEGs (rclone) — gitignored, large
  pages.tsv         page_no, filename, file_id, bytes         (Stage 0)
  pages_ocr.tsv     page_no, script, modality, source_type, engine, quality, text_file   (Stage 1)
  ocr/<page>.txt    per-page transcription                    (Stage 1)
  documents.tsv     page→document map (items_to_pages schema)  (Stage 2)
  catalog.tsv       clean trilingual catalogue                 (Stage 3)
  review.md         human-verification table                   (Stages 2–3)
data/recatalog/feasibility_report.md                           (Stage 5)
```

## Schemas

**pages_ocr.tsv** — `page_no, script(latin|hebrew|mixed|none), modality(print|typescript|handwriting|photo|blank), source_type, engine(vision|transkribus|claude), quality(0-1|na), text_file`

**documents.tsv** — reuses `data/landsberg/items_to_pages_G-F-0047-023.tsv`:
`section_id, parent_r_item, transkribus_doc_id, page_start, page_end, divider_page, title_he, title_de_or_en, author, language, doc_type, date_text, in_existing_catalog, heimat_relevant, notes`

**catalog.tsv** — aligns with `letters_enriched.tsv` + `Documents2024-12-13.tsv`:
`doc_id, page_range, title, date_text, doc_type, languages, from_person, to_person, places, persons, description_he, description_de, description_en, is_heimat_relevant, heimat_rationale, source_pages, notes`

## Pilot folders

`0047-23` (done — gold reference), `0444-3` (Worms — first end-to-end), `0113-41`,
`0422-3`, `0276-6`, `0047-2`, `0185-2`, `0047-4` (handwriting bake-off).

## Reused assets

`code/transkribus_client.py`, `code/htr_extract_text.py`, `code/extract_letter_metadata.py`,
`code/build_csv_combined.py`, `mockups/_shared/frame.*`, the Tefen accession register
(`data/hecht/`), and the page-map schema in `data/landsberg/`.
