# Next-session pickup plan

## Session 2026-06-16 summary

**Did:**
- Surveyed Landsberg collection (G-F-0047) — 95 items / 50 subseries / 5 HTR docs.
- Built first-pass items↔pages join for `-023` → [items_to_pages_G-F-0047-023.tsv](items_to_pages_G-F-0047-023.tsv) (29 sections, draft, **not verified against facsimiles**).
- Pulled all page JPGs from Transkribus for the five Landsberg HTR docs:
  - 942484 (`-023`) — 311 jpg ✅
  - 853306 (`-042`) — 184 jpg ✅
  - 1242509 (`-019`) — 99 jpg ✅
  - 3657816 (`-004`) — 106 jpg (background download may still be finishing — verify)
  - 4008066 (`-045`) — 59 jpg (background download may still be finishing — verify)
- Discovered that pp 33–50 of `-023` are 17 Tefen Museum accession-register cards (one per Landsberg subseries) with rich structured fields.

**Did NOT do (and won't, per user decision):**
- Per-section mapping for `-019/-042/-004/-045` — paused in favor of full register approach.
- OCR correction on the 18-page Landsberg register subset.
- Catalog merge from the Landsberg register subset.

## Decision: pivot to the full Tefen Museum accession register

User has the **full register (~7,477 pages)** locally. This supersedes piecemeal per-doc mapping because the register's cards are Tefen's own item-level descriptions for *every* MTFN folder.

## Workflow when picking back up

1. **Get the register into the workflow.** User to drop the 7,477-page source (PDF? folder of JPGs?) somewhere accessible — `data/tefen_accession_register/source/` is a natural home. Confirm format and naming.
2. **HTR.** Decide pipeline:
   - Re-use Transkribus (existing `code/transkribus_client.py`, account configured) — best if printed Hebrew model is good enough.
   - Or eScriptorium (user already has Hecker setup there).
   - Sample 5–10 pages first, compare WER, pick.
3. **OCR-error correction.** Template-aware pass: the cards have ~13 fixed field labels. Build a small lexicon of canonical labels + LLM correction per card constrained to that template. Errors concentrate at line edges (RTL right, LTR left).
4. **Structured extraction.** One JSON/TSV row per card with fields: `accession_no`, `folder_id` (`G.F.NNNN/NN`), `artist_he`, `artist_lat`, `title`, `technique`, `description`, `categories[]`, `item_type`, `dimensions`, `years`, `narrow_subject`, `broad_subject`, `page_in_register`.
5. **Catalog merge.** Per row, lookup existing Omeka subseries record (`data/Subseries Records2024-12-13.tsv`, `data/omeka-audit/*`); produce a deltas TSV showing register-value vs. Omeka-value vs. proposed merge, for user review before any Omeka write.

## Loose ends / things to verify next time

- Confirm the final two background downloads (3657816, 4008066) actually completed — `ls data/transkribus/htr/3657816/pages/*.jpg | wc -l` should be 106; same for 4008066 (59).
- The accession-number pattern `NNN.1097` was observed across the Landsberg-subset register pages — `.1097` may be a Tefen sequence suffix; check whether this constant holds across the full 7,477 pages or whether it varies by collection within MTFN.
- `data/landsberg/items_to_pages_G-F-0047-023.tsv` is a paused draft — treat as scratch, not as ground truth, if you ever come back to per-doc mapping.
