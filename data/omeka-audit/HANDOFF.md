# Omeka Bulk-Ingest — Handoff

**Last touched:** 2026-06-08
**Status:** Infrastructure built and ready. Blocked on server-side HTTP 500 from `POST /api/items`.
**Goal:** Ingest 2,695 missing Jecke records from `data/JeckeArchive/Jecke-items.tsv` into Omeka S at https://omeka.dijest.net.

---

## What's already done

### In Omeka (live)
| Thing | Count | IDs |
|---|---|---|
| New resource templates | 20 | 11–30 |
| New item sets | 20 | 7610–7629 |
| Junk item set (couldn't delete) | 1 | 7645 |

All 20 templates share the same 18-field RiC superset; they differ only in **label** and **`o:resource_class`**. The class→IDs map is at [class_map.json](class_map.json).

### In the repo
| File | Purpose |
|---|---|
| [../../code/omeka.py](../../code/omeka.py) | API client. Sets `User-Agent: jecke-cli/1.0` (server WAF blocks `python-requests/*`). Idempotent retries. |
| [../../code/create_templates.py](../../code/create_templates.py) | Creates the 20 templates + sets. Idempotent — re-running won't duplicate. |
| [../../code/ingest_jecke.py](../../code/ingest_jecke.py) | The ingest. Dry-run mode verified; will POST when unblocked. |
| [../../.env](../../.env) | Omeka API creds (gitignored, chmod 600). |
| [open_records_missing_from_omeka.txt](open_records_missing_from_omeka.txt) | The 2,695 IDs to ingest. |
| [class_map.json](class_map.json) | `item_class → {template_id, item_set_id, resource_class_id}`. |

---

## The blocker

`POST /api/items` returns **HTTP 500** with HTML body (no JSON detail) for **every payload**, including minimal ones with only required fields.

Notable: `POST /api/item_sets` and `POST /api/resource_templates` both work. **The failure is specific to item create (and DELETE on item sets).**

### Black-box probing results (2026-06-08)

| Payload | Status | What it tells us |
|---|---|---|
| Empty / minimal (no template) | 500 HTML | Crashes before template validation |
| Template set, required props missing | 422 JSON (`"requires X value"`) | Validation works |
| Template + class + item_set + all required props | 500 HTML | **Crashes at save time** |

So the crash is **after** validation, in a save-time listener. Not in the API layer, not in the validator.

### CSV Import gives a strong corroborating hint

The bulk-import module fails with:

```
PDOException: SQLSTATE[23000]: Integrity constraint violation: 1062
Duplicate entry '14-10' for key 'resource_template_property.UNIQ_4689E2F116131EA549213EC'
→ Doctrine\ORM\Exception\EntityManagerClosed
```

That's an unconditional INSERT into `resource_template_property` for a (template_id, property_id) pair that already exists. A module is hooking item save and trying to attach the row's mapped properties to the resource template — without checking if they're already attached.

**Likely culprit modules** (any that hook item save + touch `resource_template_property`):
- AdvancedResourceTemplate
- AutoSuggestProperties / similar
- BulkEdit / EasyAdmin extensions
- A custom Solr/Elasticsearch indexer (less likely for the resource_template_property error)

A `SHOW PROCESSLIST` during a POST attempt + `SELECT * FROM module WHERE is_active = 1` from the Omeka DB would shortlist the candidate.

The real cause is in the server-side Omeka error log — almost certainly the module hook described above.

### How to get the error message

SSH (or otherwise log in) to the server hosting `omeka.dijest.net`, then check (in order of likelihood):

1. **Omeka's own log:** `<omeka-install>/application/logs/application.log` — usually the most informative.
2. **PHP error log:** path varies; common ones are `/var/log/php/error.log`, `/var/log/php-fpm/error.log`, or `/var/log/apache2/error.log`.
3. **Web server log:** `/var/log/nginx/error.log` or `/var/log/apache2/error.log`.

Look for entries with a recent timestamp (around the failing POST). Copy the **full stack trace** — the top frame names the exact PHP file/class that crashed (typically a module under `<omeka-install>/modules/<ModuleName>/`).

If you don't have server access: ask whoever administers the host (sysadmin / hosting provider / Tomer / whoever set up Omeka).

---

## How to resume (step-by-step)

### Step 1: Get and share the error log line

Paste the stack trace (or the relevant log lines) into a new Claude session along with this handoff. The fix is usually one of:
- Disable a faulty module in admin UI → Modules.
- Fix a module's configuration.
- Reinstall a broken module.

### Step 2: Verify a single live POST works

Once the server is fixed:

```bash
cd /Users/sinairusinek/Documents/GitHub/JeckeArchive
python3 code/ingest_jecke.py --limit 1
```

Expected output:
```
Missing IDs: 2695, matched in TSV: 2695
OK   IL-MTFN-001-G-F-0003-002-R0001 -> o:id=NNNN

 {'posted': 1, 'skipped': 0, 'errors': 0}
```

Inspect the new item at `https://omeka.dijest.net/admin/item/NNNN` to confirm fields render correctly.

### Step 3: Verify a few classes

```bash
python3 code/ingest_jecke.py --limit 5
```

This will hit the next 4 missing records — likely a mix of Ephemera, EgoDocument, Image classes. Confirm each lands in the right item set in Omeka admin UI.

### Step 4: Bulk ingest

```bash
python3 code/ingest_jecke.py 2>&1 | tee /tmp/ingest.log
```

This posts all remaining ~2,690 records. Expect it to take 30–60 minutes (HTTP latency).
The script writes a TSV log at [ingest_log.tsv](ingest_log.tsv) with `item_id`, `omeka_id`, `error` per row — re-run safe: posts skip nothing automatically, so if you re-run you'd get duplicates. **To safely re-run only failures**, regenerate the missing-list:

```bash
# After bulk run, refresh the missing list from Omeka
python3 -c "
import os, json, urllib.request, urllib.parse, pathlib
base=os.environ['OMEKA_BASE_URL']; ki=os.environ['OMEKA_KEY_IDENTITY']; kc=os.environ['OMEKA_KEY_CREDENTIAL']
ids=set(); page=1
while True:
    q=urllib.parse.urlencode({'key_identity':ki,'key_credential':kc,'per_page':100,'page':page})
    req=urllib.request.Request(f'{base}/items?{q}', headers={'User-Agent':'jecke-cli/1.0'})
    data=json.load(urllib.request.urlopen(req))
    if not data: break
    for it in data:
        for v in (it.get('dcterms:identifier') or []):
            if isinstance(v,dict) and '@value' in v: ids.add(v['@value'])
    if len(data)<100: break
    page+=1
open('data/omeka-audit/omeka_all_identifiers.txt','w').write('\n'.join(sorted(ids)))
"
# Then rebuild the missing list (see how it was originally built — search 'open_records_missing_from_omeka' in git log)
```

### Step 5: Clean up the junk item set

After the API is fixed, delete the test set:

```bash
set -a; . .env; set +a
curl -X DELETE -A "jecke-cli/1.0" \
  "$OMEKA_BASE_URL/item_sets/7645?key_identity=$OMEKA_KEY_IDENTITY&key_credential=$OMEKA_KEY_CREDENTIAL"
```

---

## Field mapping reference

What the ingest script writes per item:

| TSV column | Omeka property | property_id |
|---|---|---|
| item_id | dcterms:identifier | 10 |
| parent | dcterms:isPartOf | 33 |
| title | dcterms:title | 1 |
| item_description | ric-o:generalDescription @he | 3502 |
| german_translation | ric-o:generalDescription @de | 3502 |
| english_translation | ric-o:generalDescription | 3502 |
| language | ric-o:hasOrHadLanguage | 3201 |
| document_type | ric-o:hasDocumentaryFormType | 3163 |
| production_technique_type | ric-o:hasProductionTechniqueType | 3240 |
| record_state | ric-o:hasRecordState | 3245 |
| main_subject | ric-o:hasOrHadMainSubject | 3205 |
| creation_date | ric-o:hasCreationDate | 3150 |
| publication_date | ric-o:hasPublicationDate | 3241 |
| creation_place | arkivo:creationPlace | 1663 |
| number_of_pages | bibo:numPages | 106 |

Composite item_classes (e.g. `Image|Creative Nonfiction`) → use the first class's template; add to **both** item sets.

---

## Fallback path: CSV Import UI

If the API stays broken, Omeka S ships a **CSV Import** module (admin → Modules → CSV Import). It's UI-based and bypasses `POST /api/items` entirely. I can prep a CSV from `Jecke-items.tsv` with proper header→property mapping for upload — ask in the next session.

---

## Reference: what was discovered in the audit

- **Drive (open)** = `JeckeData/JPG/` in the "Jeckes" Google Drive folder → 1,018 normalized folder IDs ([drive_open_folders.txt](drive_open_folders.txt)).
- **TSV** = `data/JeckeArchive/Jecke-items.tsv` → 6,855 records across 1,080 folder-subs ([tsv_item_ids.txt](tsv_item_ids.txt)).
- **Omeka (before this work)** → 5,672 items across 4 item sets; identifier overlap with TSV = 2,676.
- **Open & missing from Omeka** = 2,695 records ([open_records_missing_from_omeka.txt](open_records_missing_from_omeka.txt)) — what we plan to ingest.
- **Closed-folder records** = 2,337 records ([closed_folder_records.txt](closed_folder_records.txt)) — intentionally excluded.

Full report context: see `[Omeka ingest state]` memory note.
