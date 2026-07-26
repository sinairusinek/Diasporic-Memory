---
name: project-recatalog-pipeline
description: "Re-cataloguing + page-mapping + OCR pipeline for MTFN folders — pilot design, engine bake-off findings, and Worms 0444 end-to-end result (2026-07-03)"
metadata:
  type: project
---

Repeatable per-folder pipeline to turn MTFN scan folders into page→document maps +
clean trilingual catalogues, piloted on the return-visit folders to price scaling to
the whole collection. Plan: `~/.claude/plans/expressive-orbiting-reddy.md`. Code:
`code/recatalog/` (acquire.py rclone, ocr_tesseract.py, classify.py, metrics.py).
Docs/outputs: `data/recatalog/` (README, feasibility_report.md, per-folder dirs).

**HYBRID architecture:** some stages are agent-driven via Drive/Vision MCP tools
(inventory, Vision OCR, segmentation, cataloguing), others are scripts (rclone,
Tesseract, mockup). Scripts CANNOT call the MCP tools; the agent CAN.

**Transkribus HTR path BUILT (2026-07-05, part a):** `code/recatalog/transkribus_htr.py`
uses the **new Processing API** — `POST https://transkribus.eu/processing/v1/processes`
with OAuth2 token (readcoop password grant, client_id=processing-api-client) and the
image as **base64** (`{"config":{"textRecognition":{"htrId":N}},"image":{"base64":...}}`)
→ processId → poll `GET /processes/{id}` → `content.text`. The OLD TrpServer
(`transkribus_client.py`) is download-only and its job-trigger endpoints are GONE
(404); its upload still works but is unnecessary. Our collection = "Jeckes" colId 124933.
Good models: **German Giant I (50870, CER 9.8%, PyLaia)**, German Genius (265149),
Modern-Hebrew (399677), Text Titan II (579509).

**Handwriting bake-off verdict:** on German cursive — Tesseract FAILS (letterhead only);
**Transkribus German Giant ~90%** legible (bulk, cheap, errs on hard words);
**Claude vision ~95%** (resolves names/Hebrew-loanwords via context, token cost, 1 page
at a time). Route bulk handwriting to Transkribus, escalate flagship/low-conf pages to
Claude. Google Vision also empty on cursive (print-only). Faint pencil needs contrast
preprocessing first.

**Setup done (2026-07-03):** rclone remote `jeckedrive` authed read-only to user's Drive
(`rclone copy jeckedrive: --drive-root-folder-id <ID>`); Tesseract installed with
deu/heb/eng/yid. Large scans gitignored (`data/recatalog/*/scans/`).

**Engine findings (pilot):**
- PRINT: free local **Tesseract ≈ or > Google Vision** on German print (Vision hallucinated "35" where Tesseract got "3-5"). → Tesseract-first; Vision/Cloud-Vision only as spot-check. ~3.5s/page.
- Classify by Tesseract mean_conf: **~86% of pages handled free** (conf≥0.6 print), **~14% escalation** (handwriting/photo/blank).
- HANDWRITING: Tesseract AND Google Vision both return empty on cursive. Claude vision partial on **faint-pencil** Hebrew (needs a contrast/levels preprocessing step first). Transkribus not yet run (needs upload path).

**Accession register (ספר האוסף):** opens each folder's scans; gives an **itemised content inventory + descriptions + provenance (donor/date/related holdings)** but **NO page→scan mapping**. So it anchors cataloguing + gives segmentation a target list; page ranges still come from the OCR "spine". Corrects earlier overclaim. See [[project-tefen-accession-register]].

**Worms 0444-3 done end-to-end:** 252 pp (630MB) → 11 documents mapped
(`data/recatalog/0444-3/documents.tsv`), 10 trilingual catalogue records
(`catalog.tsv`). Found the flagship 1964 invitation (pp6-7, Bürgermeister Berg,
"in Ihre alte Heimat kommen") → facsimile mockup at `mockups/worms-1964-invitation/`
(linked from return-visits exhibit). Folder is book-heavy (Moses Mannheimer 1842
Fraktur book pp34-102 + cemetery booklet ×2 pp104-208); Heimat core is only ~30pp.

**Batch of 6 more folders done (2026-07-05):** all 7 pilot folders now OCR'd+classified (1,686 pp total, **24% escalation overall**). Escalation is **bimodal by folder type**: print/book folders 2–23% (Berlinger 2%, Worms 14%, Winterreise 21%, Wilma-Adam 22%, Schopler 23%), handwritten-letter folders **65–80%** (Leoni Frank 0047-2 65%, Ruppin 0047-4 80%). → collection cost is driven by print:handwriting ratio, predictable from register/catalog doc-type fields. **Register card present in only 1/7 folders (Worms)** — NOT the norm; segmentation worked from OCR spine alone in the other 6 (via parallel subagents). `code/recatalog/batch.sh` drives acquire→ocr→classify (bash-3.2 portable). `code/recatalog/classify.py` writes pages_ocr.tsv. 4 folders segmented+catalogued by subagents → documents.tsv + catalog.tsv each.

**Identifications surfaced (feed post_war_visits):** PWV-12 Winterreise author = **Dr. Fritz Wolf** (Nahariya); Berlinger's hometown = **Berlichingen (Hohenlohe)**, 1968 return-lecture + memoir "Hohenloher Memoiren 1933-1939"; Schopler = **1986 & 1987 Cologne reunion events** (Mayor Burger speech "in Ihrer alten Heimatstadt Köln"); NEW case **Walli & Ernst Seligmann returned to Germany 1995** (Givat Brenner bios, 0185-2 p209). Flagship facsimile mockups built + deployed: winterreise-1969, schopler-cologne, berlinger-hohenlohe, worms-1964-invitation, worms-1985-refusal.

**Part (a) COMPLETE (2026-07-26):** 0047-2 + 0047-4 HTR'd (91 pp German Giant) and segmented — ALL 7 pilot folders now have documents.tsv + catalog.tsv. Script hardening: `transkribus_htr.py` now has a macOS-mDNSResponder DNS workaround (transkribus.eu negative-cached while nslookup works) and OAuth token refresh mid-run (readcoop tokens expire during long poll loops; symptom = JSONDecodeError crash). **0047-2 is Leoni Frank's famous-correspondents folder**: Einstein 1924, Herzl 1900 (provenance pair), Zweig ×3, Weizmann bundle, and the **Sharett–Leonie Frank exchange 1959–65** with an unsent 1959 letter FROM Wiesbaden during her remigration ("fremd und einsam", five generations born there) — prime mockup candidate; 7/39 docs Heimat-relevant. 0047-4 = 1919–39 correspondence (Ruppin, Soskin, Feiwel, Pappenheim 1919 Wiesbaden, Alfred's 1925 Vienna Congress letters); 0 Heimat-relevant. Items not found in scans, need human check: 0047-2 Hans Cohen postcard/Szold 1939/Emil Hoffmann 1947; 0047-4 Heilbrunner portraits (prob. pp.97-100), Ussischkin attribution.

**Omeka stage BUILT (2026-07-26): `code/ingest_recatalog.py`** — per-folder, reads catalog.tsv + hand-made `omeka_map.tsv` (doc_id → legacy item_id | NEW). KEY LESSON: pilot folders were often ALREADY item-level catalogued (0047-2: 21 legacy items, 0047-4: 17, all in Omeka) — so the stage RECONCILES: enriches legacy items with page-labelled Drive deep-links (dcterms:source URI, GET-modify-PUT, idempotent) and creates only unmatched docs (minted next-free R####). Ran live: 60 docs → 34 legacy items enriched + 2 created. Theme now renders dcterms:source as a "Scans" section on item pages (deployed). Drive folder URLs resolved via exact-title search (unpadded names); canonical parent 1-4oOmBO58AMvdRjUQvxQlaywtXdgWT-a.

**Scaling projection (958 folders, ~115k pages):** Tesseract compute ≈ $0 (~110 machine-hrs, parallelisable); escalation tail (~14%, engine TBD) + human verification (~15-20 min/folder ≈ 240 person-hrs) are the two real costs. No blocker. TODO before rollout: Transkribus upload path + handwriting bake-off, contrast-preprocessing, run remaining pilot folders. Related: [[project-post-war-visits]], [[project-what-we-are-looking-for]], [[reference-transkribus-htr-status]].
