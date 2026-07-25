# Future: adding a "Box" level to the hierarchy

**Status:** scoping only — not actively pursued. Decision deferred pending evidence that box-level browsing matters scholarly.

## The question

Your physical reality is **4 levels**: Family Collection → Box → Folder → Item. Your current Omeka hierarchy is **3 levels**: Family Collection → Folder → Item. The Box level is implicit.

Is the missing layer a problem? Three perspectives:

### Yes, add Box — if any of these are true
- Researchers regularly need to **cite specific boxes** (e.g. "Asch Family papers, Box 4") for archival traceability.
- The boxes carry **independent metadata** — box-level finding aids, conservation notes, accession dates that are box-specific not folder-specific.
- You want to be able to **query "everything in Box X"** as a unit.
- The boxes correspond to NLI archive shelf locations and that needs to be preserved.

### No, leave it — if all of these are true
- Boxes are physical-only containers with no independent intellectual identity.
- Researchers cite at folder granularity (`IL-MTFN-001-G-F-NNNN-MMM`), not box.
- The current identifier scheme already implies the box hierarchy if needed (e.g. all `…-F-0001-XXX` folders are in the same box).
- Adding a tier means re-cataloging ~135 family collections and re-keying ~1,500 folder records.

### Maybe later
- Defer until a researcher actually asks for box-level browsing.

## If we do add it

### Identifier scheme

Option A — implicit boxes from existing folder numbers:

```
IL-MTFN-001-G-F-0001        Family Collection (Asch)
IL-MTFN-001-G-F-0001-B1     Box 1 of Asch
IL-MTFN-001-G-F-0001-B1-001 Folder 001 in Box 1
IL-MTFN-001-G-F-0001-B1-001-R0001  Item
```

This breaks existing identifiers; every folder/item identifier gets a `-BN` segment inserted. Existing URL bookmarks and external citations would 404 (or need CleanUrl redirects to map old → new).

Option B — keep current identifiers; add `dcterms:isPartOf` to Box-level items separately:

```
IL-MTFN-001-G-F-0001        Family Collection
IL-MTFN-001-G-F-0001-Box01  Box (new entry, links via isPartOf)
IL-MTFN-001-G-F-0001-001    Folder (existing; gains an isPartOf -> Box01)
```

Identifiers stay stable. Box becomes an additional structural entry, not in the path. **Recommended.**

### Class

- `arkivo:Box` already exists in your Arkivo vocab (worth checking).
- If not: create `arkivo:Box` (label "Box") via admin UI similar to today's exercise.

### Template

Create a "Box" resource template with:
- `dcterms:identifier`
- `dcterms:isPartOf` (links to parent Family Collection)
- `dcterms:hasPart` (links to child Folders)
- `rico:hasOrHadPhysicalLocation` (the shelf address at NLI/Tefen) — optional
- `arkivo:storageContainer` (the box number) — optional
Default class: `arkivo:Box`.

### Data sourcing — the hard part

Where do the box assignments come from? Three possibilities:

1. **NLI catalog** — if NLI's MARC/EAD records encode box-level structure (`852$h` shelf marks, etc.), we could parse them.
2. **Folder-number ranges** — if every continuous block of folder numbers in a family collection is a box (e.g. F-0001-001 through F-0001-050 = Box 1, F-0001-051+ = Box 2), we can derive boxes from folder numbering. Crude but auto-mappable.
3. **Manual inventory** — someone reads each box label.

(1) is the cleanest if NLI data is available; (3) is reliable but slow; (2) is a guess.

### Estimated effort

| Task | Days |
|---|---:|
| Decide identifier strategy (Option A vs B) | 0.5 (discussion) |
| Create/verify `arkivo:Box` class | 0.1 |
| Build Box template | 0.1 |
| Source box assignments (depending on path) | 0.5–5 |
| Bulk-create Box records + link folders to them via isPartOf | 0.5 |
| Update site templates to render the new level | 0.5 |
| **Total** | **~2–6 days** depending on data path |

## Recommendation today

**Don't pursue right now.** The current 3-level hierarchy (Family Collection > Folder > Item) is internally consistent and scholarly usable. Add Box level only when:

- A researcher specifically requests it, or
- Cross-archive standards work (RiC-O migration, EHRI deposit) requires it.

Roll this in with the RiC-O migration TODO (see [FUTURE_RICO_MIGRATION.md](FUTURE_RICO_MIGRATION.md)) if it ever happens — RiC-O's `rico:RecordSet` naturally accommodates any number of intermediate levels, so the box layer would fall in naturally then.
