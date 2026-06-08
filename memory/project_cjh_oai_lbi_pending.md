---
name: project-cjh-oai-lbi-pending
description: Status of CJH ArchivesSpace OAI harvest and pending request to include Leo Baeck Institute records
metadata:
  type: project
---

CJH ArchivesSpace OAI-PMH endpoint at https://archives.cjh.org/oai is harvested. As of 2026-06-07: 3,710 resource-level records in `oai_dc` covering four partners — YIVO (repo 7, 2,325), American Jewish Historical Society (repo 3, 1,335), American Sephardi Federation (repo 4, 37), Yeshiva University Museum (repo 6, 10) — plus 3 CJH umbrella records (repo 2). Stored under `data/cjh-oai/` with raw envelopes, split per-record XML, and `index.tsv`. Harvester: `code/harvest_cjh.py`.

Leo Baeck Institute (LBI, repository 5) is excluded from the OAI publisher upstream: `GetRecord` returns `idDoesNotExist`. LBI is the primary target for this project, so on 2026-06-07 Sinai emailed Eric Fritzler (Director of Metadata & Discovery Services at CJH, eafritzler@cjh.org) asking whether LBI can be added to `full_as_oai` or whether the exclusion is an LBI policy choice. Awaiting reply.

**Why:** LBI is the most important partner for this project's German-Jewish focus; without OAI access we'd need either CJH cooperation, Primo scraping at search.cjh.org, or a headless-browser scrape of the AWS-WAF-protected Public User Interface — all heavier than the polite ask.

**How to apply:** Until Fritzler replies, treat the four-partner corpus as the working CJH dataset and don't invest in WAF-bypass scraping. If reply is negative or stalls past ~3 weeks (2026-06-28), revisit the Primo / headless-browser fallbacks. See [[project-what-we-are-looking-for]] for the document types being sought.

**Pipeline status (2026-06-07):**
- Full Dublin Core harvest complete (3,710 records).
- Full Encoded Archival Description harvest complete: **3,709 of 3,710 records** on disk under `data/cjh-oai/records/oai_ead/`. One record (3/20071) returned persistent HTTP 500 server-side and is logged in `data/cjh-oai/records/fill_ead_failures.tsv`.
- ListRecords pagination on the CJH server is fragile — cursor tokens expire and start returning 500 within minutes. **Use `code/fill_ead.py`** (individual GetRecord calls, idempotent by file-exists) for any future top-up; `code/harvest_cjh.py` ListRecords pass is only useful for the first ~1,500 records before tokens go stale.
- Scorers: `code/score_cjh.py` (Dublin Core), `code/score_ead.py` (Encoded Archival Description; implements 1933 unitdate filter, Palestine-vector exclusion, organizational filter via `<origination>` persname/corpname + title patterns, Galician-birthplace exclusion via Habsburg-era phrasing and town-name list).
- Latest scorer output: **118 candidates** in `data/cjh-oai/ead_candidates.tsv`. Strong confirmed Jecke matches at the top: Adolf Lorch, John Stern, Ernest Michel, John Langeloth Loeb family, Horace Meyer Kallen, Ludwig Wolpert, Rudolf Martin Cheim, Channa Kleinerman Goldstein, Marvin Lowenthal, Phillips Family, Bruckheimer Family, Walter Hart Blumenthal, Florence Lowenstein Marshall.
- Persistent borderline cases (worth human review, not auto-droppable): Nachman Zonabend (Łódź ghetto rescue documents), Philip Friedman (Galician Holocaust historian), Shmuel Zygielbojm (Polish Bund leader), Autobiographies of Jewish Youth in Poland (YIVO contest collection).
