# Omeka S — CSV Import Instructions

**Goal:** Ingest the missing Jecke records via the CSV Import module, bypassing the broken `POST /api/items` endpoint.

**Server:** https://omeka.dijest.net → Admin → **Modules → CSV Import**.

---

## ⚠ Combined-upload path is broken on this server

Earlier this file recommended a single `combined_all.csv` with per-row resource template, item set, and class. That triggered a **CSV Import bug on this Omeka instance**:

```
Duplicate entry '14-10' for key 'resource_template_property.UNIQ_...'
EntityManagerClosed
```

When the importer assigns a resource template per row, it tries to attach each row's mapped properties to the template — without an existence check — and dies on the second row that hits the same template+property pair. This may share a root cause with the `POST /api/items` 500 (see [../HANDOFF.md](../HANDOFF.md)) and should be diagnosed via the server error log.

**Use the per-class workflow below instead.** Each import sets one template + item set + class **globally**, so the buggy code path doesn't fire.

---

## Recommended order (smallest first)

| Order | File | Rows | Template | Item Set | Resource class (term) |
|---:|---|---:|---|---:|---|
| ~~1~~ | ~~academic_paper.csv~~ | ~~5~~ | ~~Academic Papers~~ | ~~7623~~ | ~~`bibo:AcademicArticle`~~ ✅ done |
| 2 | [school_material.csv](school_material.csv) | 5 | School Materials | 7627 | *(none)* |
| 3 | [translated_document.csv](translated_document.csv) | 5 | Translated Documents | 7624 | `arkivo:Meta_Document` |
| 4 | [article.csv](article.csv) | 7 | Articles | 7622 | `bibo:Article` |
| 5 | [catalog.csv](catalog.csv) | 10 | Catalogs | 7625 | *(none)* |
| 6 | [religious_material.csv](religious_material.csv) | 10 | Religious Materials | 7626 | *(none)* |
| 7 | [medical_document.csv](medical_document.csv) | 11 | Medical Documents | 7620 | `arkivo:Medical_Document` |
| 8 | [newspaper.csv](newspaper.csv) | 11 | Newspapers | 7621 | `bibo:Newspaper` |
| 9 | [object.csv](object.csv) | 20 | Objects | 7619 | `dctype:PhysicalObject` |
| 10 | [misc.csv](misc.csv) | 22 | Misc | 7629 | *(none)* |
| 11 | [unrecognized.csv](unrecognized.csv) | 47 | Unrecognized | 7628 | *(none)* |
| 12 | [financial_document.csv](financial_document.csv) | 51 | Financial Documents | 7618 | `arkivo:Financial_Document` |
| 13 | [report.csv](report.csv) | 65 | Reports | 7617 | `arkivo:Report` |
| 14 | [organization_papertrail.csv](organization_papertrail.csv) | 119 | Organization Papertrails | 7616 | `arkivo:Organization_Papertrail` |
| 15 | [legal_document.csv](legal_document.csv) | 150 | Legal Documents | 7615 | `bibo:LegalDocument` |
| 16 | [creative_fiction.csv](creative_fiction.csv) | 197 | Creative Fiction | 7614 | `arkivo:Creative_Fiction` |
| 17 | [ephemera.csv](ephemera.csv) | 348 | Ephemera | 7613 | `arkivo:Ephemera` |
| 18 | [certificate.csv](certificate.csv) | 421 | Certificates | 7612 | `arkivo:Certificate` |
| 19 | [image.csv](image.csv) | 481 | Images | 7611 | `dctype:Image` |
| 20 | [egodocument.csv](egodocument.csv) | 710 | EgoDocuments | 7610 | `arkivo:EgoDocument` |

**Remaining: 2,690 rows across 19 files.**

---

## Per-file workflow

### Screen 1: Import Settings
- **Spreadsheet:** the CSV for this class.
- **CSV column delimiter:** comma.
- **CSV column enclosure:** double quote.
- **Import type:** Items.
- **Automap with simple labels:** checked.
- **Comment:** `Jecke <class> ingest 2026-06-08` (helpful for tracking in Past Imports).

Click **Next**.

### Screen 2 — Tab "Basic Settings" (set these FIRST, before column mapping)
- **Owner:** your admin account.
- **Visibility:** Public.
- **Resource template:** pick the **Template** value from the row in the table above.
- **Item sets:** pick the matching **Item Set** number.
- **Resource class:** if the row shows a class term, pick that class. If it shows *(none)*, leave blank.
- **Sites:** add the main public site.

### Screen 2 — Tab "Map to Omeka S data"
Most columns auto-map. You'll only need to act on the three description columns.

| CSV column | Action |
|---|---|
| `dcterms:identifier` | already mapped to Identifier ✓ |
| `dcterms:isPartOf` | already mapped to Is Part Of ✓ |
| `dcterms:title` | already mapped to Title ✓ |
| `description_he` | click **+** → Properties → **"general description"** (RiC-O). Then click the wrench/spanner next to the mapping → set **Language** = `he`. |
| `description_de` | same as above, set Language = `de`. |
| `description_en` | same as above, leave Language blank. |
| `ric-o:hasOrHadLanguage` | auto-mapped ✓ |
| `ric-o:hasDocumentaryFormType` | auto-mapped ✓ |
| `ric-o:hasProductionTechniqueType` | auto-mapped ✓ |
| `ric-o:hasRecordState` | auto-mapped ✓ |
| `ric-o:hasOrHadMainSubject` | auto-mapped ✓ |
| `ric-o:hasCreationDate` | auto-mapped ✓ |
| `ric-o:hasPublicationDate` | auto-mapped ✓ |
| `arkivo:creationPlace` | auto-mapped ✓ |
| `bibo:numPages` | auto-mapped ✓ |

All three `description_*` columns map to the **same** property (`ric-o:generalDescription`); the per-column Language is what distinguishes them.

### Screen 2 — Tab "Advanced Settings"
- If asked for an identifier column to enable deduplication: pick `dcterms:identifier`.
- Leave other defaults.

### Run
Click **Import** (top right). Watch the **Past Imports** page until status flips from "Job started" to **Completed**.

### Validate
1. Items list filtered by item set: `https://omeka.dijest.net/admin/item?item_set_id=<ID>` — count matches the expected row count.
2. Open one item. Confirm title, identifier, parent, and at least one description show.
3. On the items list, **filter by type** (resource class) — the class shows up and lists your items (only for classes where this file has a term assigned).

If anything's off, use the **Undo** column on the Past Imports page.

---

## Post-import housekeeping

1. **Composite extras** — 2 records need a secondary item set added by hand:
   - `IL-MTFN-001-G-F-0401-001-R0003` (Certificate) → also add to item set **7613** (Ephemera).
   - `IL-MTFN-001-G-F-0480-001-R0016` (Image) → also add to item set **7613** (Ephemera).

   For each: open the item in admin → "Item sets" tab → add the extra set ID → save. (See [composite_extras.tsv](composite_extras.tsv) for source-of-truth.)

2. **Junk item set 7645** — delete via curl (command in [../HANDOFF.md](../HANDOFF.md) Step 5).

3. **Refresh the missing-identifier list** per [../HANDOFF.md](../HANDOFF.md) Step 4 to confirm the missing count drops to ~0.

4. **TODO — fix the API.** The CSV Import duplicate-key error is a strong hint about what may also be breaking `POST /api/items`. Get the server-side application log around the time of either failure; the stack trace will name the offending module. See [../HANDOFF.md](../HANDOFF.md) for log locations.

---

## Files in this directory

- 19 `*.csv` per-class files (academic_paper.csv already used)
- `combined_all.csv` — **don't use** (triggers the duplicate-key bug); retained only as a record
- `manifest.json` — programmatic class → file/template/set/class mapping
- `composite_extras.tsv`, `composite_extras_combined.tsv` — secondary item-set assignments
- `unmapped_classes.tsv` — 22 records routed to **MISC** because their `item_class` value isn't in the 20-class map
- `INSTRUCTIONS.md` — this file
