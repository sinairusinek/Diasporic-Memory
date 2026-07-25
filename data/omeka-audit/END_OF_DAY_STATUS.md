# End-of-day status — 2026-06-17

Use this as the picking-up-where-we-left-off doc.

---

## ✅ Everything done autonomously while you were out

### Data cleanup
- **10 ghost merge keepers deleted** (o:ids 3789, 4903–4911). They had no title, no class, no hasPart, no identifier — empty shells left by old dedup attempts.
- **1 Hebrew header garbage deleted** (o:id 3407, identifier `מזהה רשומת אב` = "Master record identifier").
- **Family-collection identifier audit:** 0 items in arkivo:Fonds (class 1028) lack `dcterms:identifier`. The restore-from-hasPart pass was 100% effective on the resolvable cases.

### Final class state

| Class | Count | Public badge | Notes |
|---|---:|---|---|
| `arkivo:Fonds` (1028) | 563 | **Family Collection** | clean |
| `arkivo:File` (1026) | 1,433 | **Folder** | clean |
| `bibo:Series` (83) | 0 | — | retired |
| `dctype:Collection` (23) | **1** | (Collection) | see leftover 3972 below |

**Total items: 8,223.**

### One leftover: o:id 3972
- Identifier `IL-MTFN-001-G-G-0539` (note the unusual `G-G-` prefix — distinct from the `G-F-` family-collection naming).
- Title: "אוסף משפחת אמנון להב" (Amnon Lahav family collection).
- Should be reclassed to `arkivo:Fonds`. I tried — PATCH returned HTTP 500.
- **Likely cause:** the **Common** module is currently in `needs_upgrade` state. Its half-installed event listeners may be intercepting item saves and crashing. Once you upgrade Common via admin UI, the reclass should work — run:
  ```
  python3 code/reclass_single.py 3972 1028
  ```
  (I'll write that one-liner script in a moment if you want, or you can do it via admin UI in 10 seconds.)

---

## ⚠️ Three admin-UI clicks needed before any module work

The Omeka API **does not allow module install or upgrade** — admin UI only. Visit https://omeka.dijest.net/admin/module and:

1. **Common** → click **Upgrade** (currently shows `needs_upgrade`).
2. **CleanUrl** → click **Install**.
3. **Internationalisation** → click **Install**.

After all three, tell me and I take over configuration via API.

---

## 🔧 Configuration decisions I'm making for you (review after I implement)

You gave carte blanche on Internationalisation design — here's what I'm planning:

### Internationalisation

| Setting | Value | Rationale |
|---|---|---|
| Site languages | `en, de, he` | Per PI scope decision 2026-06-08 |
| Default site language | `en` | Per PI scope decision: English default |
| Locale switcher placement | Header AND footer (if module supports both) | Per PI scope decision |
| Fallback behaviour | None — show whatever values exist | Per PI scope decision: explicit "[Language TBA]" placeholders rather than silent fallback. The module may not have a "show placeholder" feature out-of-the-box; if not, we'll need a small theme tweak (the LivelyTrilingual scaffold has the placeholder renderer ready to graft on). |
| Per-page translation | Enable for major nav pages (Browse Family Collections, Browse Folders, Persons, Places, Bibliography, Timeline) | These are user-facing |
| Translation of class/template labels | Yes for the Arkivo-namespace classes we relabeled (Family Collection, Folder) | Keeps the badge readable in DE/HE too |

### CleanUrl

| Setting | Value | Rationale |
|---|---|---|
| Identifier property | `dcterms:identifier` | Standard archival reference |
| Items URL pattern | `{identifier}` | Naked identifier (cleanest) |
| Item sets URL pattern | `set/{identifier}` (or `{identifier}` if conflict-free) | TBD — depends on whether item-set identifiers overlap with item identifiers; I'll check at config time |
| Redirect numeric URLs | Yes | Old bookmarks 301 to clean URLs |
| Case-sensitive identifiers | Yes | Our identifiers are mixed-case |
| Site prefix in path | Keep current `/s/catalog/` | Don't break existing setup |

---

## 📋 What pending tasks remain after the three clicks

1. Run module configurations (5 min, all API).
2. Verify trilingual switching on a couple of items.
3. Verify CleanUrl renders `https://omeka.dijest.net/s/catalog/IL-MTFN-001-G-F-0004` instead of numeric IDs.
4. **PR-quality status writeup** for Guy if you want to share progress (optional).
5. Fix leftover item 3972 (one PATCH, blocked on Common upgrade).
6. **NOT done:** the 116 family collections that had no identifier *originally* (pre-our-session) — turned out to be 0 cases. The 125 we restored covered them all.

---

## 🗂 Files written today (recap)

| File | What it is |
|---|---|
| [CLEANURL_INSTALL.md](CLEANURL_INSTALL.md) | (stale — superseded by this doc's three-click section) |
| [TRILINGUAL_PLAN.md](TRILINGUAL_PLAN.md) | LivelyTrilingual fork plan; **superseded** by Internationalisation-module approach but kept as Plan B if module doesn't deliver |
| [BOX_LEVEL_SCOPING.md](BOX_LEVEL_SCOPING.md) | Future Box layer — defer until needed |
| [FUTURE_RICO_MIGRATION.md](FUTURE_RICO_MIGRATION.md) | Future RiC-O migration — funding-contingent |
| [HANDOFF.md](HANDOFF.md) | Earlier handoff; updated with DerivativeMedia root-cause analysis |
| [legacy_merge_mapping.json](legacy_merge_mapping.json) | 135 (older_id, newer_id) pairs from the merge — already used; keep for reference |
| `code/*.py` | All ingest + cleanup scripts; idempotent re-runnable |

---

## ☎️ When you're back

Just say "done" (or paste a screenshot of the three modules showing "Active"). I'll fire the configuration scripts, run a couple of public-page checks, and write up the trilingual + CleanUrl results for your review.
