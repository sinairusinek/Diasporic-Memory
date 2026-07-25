# CleanUrl module install — make identifiers the URL slug

Goal: change item URLs from `/s/catalog/item/3411` to `/s/catalog/IL-MTFN-001-G-F-0004` (or similar) by installing Daniel Berthereau's CleanUrl module.

**Prerequisite:** dedupe must be complete (no two items share a `dcterms:identifier`). The legacy-merge run handles this.

---

## Step 1 — Download the module

1. Go to https://gitlab.com/Daniel-KM/Omeka-S-module-CleanUrl/-/releases.
2. Find the **latest release** that supports your Omeka S version. (Check Omeka version at Admin → System Information.)
3. Download the `.zip` (e.g. `CleanUrl-x.y.z.zip`).

## Step 2 — Upload to the server

In cPanel → File Manager:

1. Navigate to `/home/thedigin/omeka_s/modules/`.
2. Click **Upload** (top toolbar) → select the downloaded `.zip` → upload.
3. Back in `modules/`, right-click the uploaded zip → **Extract** → into the current folder.
4. After extract, the folder must be named exactly **`CleanUrl`** (no version suffix). If extraction created `CleanUrl-x.y.z/`, right-click → **Rename** → `CleanUrl`.
5. Delete the .zip.

## Step 3 — Install via admin UI

1. https://omeka.dijest.net/admin → **Modules**.
2. Find **Clean URL** in the list — it'll show as **Not installed**.
3. Click **Install**.
4. If prompted for database changes, accept.

## Step 4 — Configure

After install, go to **Modules → Clean URL → Configure** (or admin → Site settings → Clean URL).

Key settings to set:

| Setting | Value |
|---|---|
| **Property for resource identifier** | `dcterms:identifier` |
| **Identifier prefix** | leave blank (we don't use prefixes) |
| **Main path / sites prefix** | as already configured for your site |
| **Items URL pattern** | `{identifier}` (or `item/{identifier}` if you want to keep the `/item/` prefix) |
| **Item sets URL pattern** | `{identifier}` or `set/{identifier}` |
| **Allow alphanumeric identifiers** | yes |
| **Case sensitive identifiers** | yes (our identifiers have hyphens and uppercase) |
| **Redirect numeric URLs** | yes (so old `/item/3411` 301s to the clean URL) |

Save.

## Step 5 — Verify

Open a few items and check:
- Browser URL bar shows `…/IL-MTFN-001-G-F-0004` instead of `…/3411`.
- Old numeric URL still resolves (301 redirect).
- "Browse Series" page links use the new pattern.

## Step 6 — Caveats and post-install fixes

- **Folder-level identifiers** like `IL-MTFN-001-G-F-0004` and item-level like `IL-MTFN-001-G-F-0004-001-R0001` share a prefix. CleanUrl is fine with this — it does exact-match lookup.
- **No identifier?** A handful of items might lack `dcterms:identifier`. Those will fall back to the numeric URL. You can spot them with this query (run in cPanel → phpMyAdmin if you want):
  ```sql
  SELECT r.id FROM resource r
  LEFT JOIN value v ON v.resource_id = r.id AND v.property_id = 10
  WHERE r.resource_type = 'Omeka\\Entity\\Item' AND v.id IS NULL;
  ```
- **Duplicates** (post-dedupe should be zero): if two items share an identifier, CleanUrl picks one and the other becomes unreachable except by numeric URL. Verify post-install with `python code/dedupe_items.py --dry-run` — should still report 0 duplicates.

## What it changes for users

- Cleaner URLs that include the archival reference number, which is what scholars cite anyway.
- Linkable: someone can email a colleague `https://omeka.dijest.net/s/catalog/IL-MTFN-001-G-F-0145-001-R0001` instead of `…/item/8362`.
- Stable: numeric IDs change between installations (e.g. if you restore from backup); identifiers don't.

## What it does NOT do

- Doesn't change the admin URLs (those stay numeric for safety).
- Doesn't auto-generate identifiers for items that lack one — they keep numeric URLs.
- Doesn't affect the API (which still uses `/api/items/{id}`).
