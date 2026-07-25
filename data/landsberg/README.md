# Landsberg collection — items↔pages mapping

Working directory for the deeper page-level mapping of `IL-MTFN-001-G-F-0047` (Landsberg Alfred Abraham & Leoni family collection).

## Files

- `items_to_pages_G-F-0047-023.tsv` — first join table, covers subseries `-023` ("דיווחים ויומנים" / Reports & Diaries), Transkribus docId 942484, 311 pages.

## Schema

| column | meaning |
|---|---|
| `section_id` | Local identifier for a distinct text-section (`023-S01`, `023-S02`, …). Finer than the existing Omeka R-items. |
| `parent_r_item` | The existing catalog R-item this section belongs to (`R0001`–`R0007`), or `UNCATALOGED` if no current Omeka item covers it. |
| `transkribus_doc_id` | Source HTR document. |
| `page_start` / `page_end` | Page range (Transkribus `pageNr`, 1-indexed). |
| `divider_page` | Page number of the Hebrew/divider title card that opens the section (when present). |
| `title_he`, `title_de_or_en` | Section titles as transcribed. |
| `author`, `language`, `doc_type`, `date_text` | Bibliographic metadata. |
| `in_existing_catalog` | `yes` / `no` / `partial` — whether this content is reflected in current Omeka items. |
| `heimat_relevant` | Whether the section bears on the diasporic-memory / Heimat axis. |
| `notes` | Free text. |

## How sections were identified

1. Extracted plaintext for all 311 pages from PAGE XML (already in `data/transkribus/htr/942484/pages/*.txt`).
2. Built a one-line-per-page index keyed on char count + first three lines.
3. Identified divider pages by a strong signal: short page (<400 chars), Hebrew-only title card, often containing a date and author/title.
4. Cross-referenced with the existing R0001–R0007 descriptions in the catalog (`data/Subseries Records2024-12-13.tsv` + the Classified_Missing parsed items) to assign `parent_r_item`.

## Catalog deltas surfaced

The existing seven R-items are at *physical envelope* granularity. The page-level mapping surfaces sections that have no discrete R-item and should be considered for new catalog entries:

| section | suggested new R-item | reason |
|---|---|---|
| `023-S02` (pp 33–51) | Accession Register from Zionist Archive | Provenance metadata, distinct genre (ArchivalRecord), 19 pages |
| `023-S07`–`023-S11` (pp 75–89) | 1924 Jerusalem / Tel Aviv reports | Distinct dated reports (8.10.1924, 19.10.1924); currently bundled implicitly with R0007 |
| `023-S22` (p 165) | ZVfD May 1932 publication announcement | Different author (organisational), mentioned in subseries description but not R-itemised |
| `023-S27` (pp 187–194) | 1925 USA travel diary — Hebrew translation | R0003 catalogs only the *envelope/photo*; the translated content is its own piece |
| `023-S28` (pp 199–200) | 1928 Weizmann memoir — Hebrew translation | Distinct text, explicit Wiesbaden (Heimat) anchor; not in current catalog |

These should be presented to the cataloguer for confirmation before being added to `data/omeka-audit/csv-import/`.

## Heimat-relevance summary for `-023`

24 of 29 sections (~83%) are Heimat-relevant. Strongest signals:
- 1932 Berichte (III–VII): German Zionist's pre-aliyah inspection of Yishuv (return-to-Heimat in inverse — the diasporic gaze).
- 1951 Deutschlandfahrt + 1956 Berlin + 1959 Ostberlin essays: postwar Heimat return cycle.
- 1928 Wiesbaden→Weizmann memoir: explicit toponym anchor.

## Next subseries

Pending join tables for the other four HTR'd Landsberg documents:

- `-019` (docId 1242509, 99 pages) — קורות החיים / Life-course materials
- `-042` (docId 853306, 184 pages) — Correspondence to Leoni Landsberg
- `-004` (docId 3657816, 106 pages) — Letters (Ruppin et al.)
- `-045` (docId 4008066, 59 pages) — Letters and postcards to Ruppin

Images for all five are being pulled into `data/transkribus/htr/<docId>/pages/`.
