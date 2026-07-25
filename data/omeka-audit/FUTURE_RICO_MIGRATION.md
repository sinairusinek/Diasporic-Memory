# Future: Migrate to RiC-O archival ontology

**Status:** TODO — contingent on funding (2026-06-08 decision).
**Trigger:** when the pilot moves from feasibility study to funded buildout, or when the catalog needs to be deposited to a standards-conscious aggregator (e.g. EHRI, Archives Portal Europe).

## Why move

The current setup uses a pragmatic mix of `dctype:`, `bibo:`, and `arkivo:` classes. Works for in-house display but isn't archival-native. RiC-O (Records in Contexts Ontology, ICA standard) is the international standard for describing archival materials and their relationships, succeeding ISAD(G).

## Mapping target

| Current level | Current class | Proposed RiC-O class | Type qualifier |
|---|---|---|---|
| Family Collection (e.g. `…-F-0001`) | `dctype:Collection` | `rico:RecordSet` | `rico:RecordSetType` "Fonds" |
| Folder (e.g. `…-F-0001-001`) | `bibo:Series` | `rico:RecordSet` | "File" or "Series" |
| Item (e.g. `…-F-0001-001-R0003`) | varies (`arkivo:*`, `bibo:*`, `dctype:*`) | `rico:Record` (or `rico:Instantiation` for media) | preserve current item-class as `rico:hasRecordSetType` or via custom term |

## What it requires

1. **Install RiC-O vocabulary** in Omeka S admin (importable as RDF — file is at gitlab.com/ica-ric/RiC-O).
2. **Create new resource templates** mirroring the RiC-O hierarchy (Fonds template, File template, Record template).
3. **Re-class existing items**: bulk PATCH the ~135 family collections, ~unknown number of folders, and 2,695 items to the new RiC-O classes — preserving the current class as a secondary property for backwards reference.
4. **Update site templates** so RiC-O properties render correctly (e.g. `rico:hasOrHadHolder`, `rico:isPartOf`).
5. **Map identifiers and dates** to the RiC-O equivalents (`rico:hasOrHadIdentifier`, `rico:hasOrHadStartDate`, etc.).
6. **Re-issue any exports** (CSV, MARC, EAD) so consumers see the new model.

## Effort estimate

| Task | Days |
|---|---:|
| Install + configure RiC-O vocab | 0.5 |
| Build new templates (Fonds / File / Record / Instantiation) | 1 |
| Migration scripts + dry-runs | 1 |
| Bulk re-classification + verification | 1 |
| Site template updates for new vocabulary | 0.5 |
| EAD/MARC export integration | 0.5 |
| **Total** | **~4-5 days** |

## What we keep from current state

- All identifiers (`dcterms:identifier`).
- All descriptions (Hebrew, German, English language tags).
- All relationships (`dcterms:hasPart`, etc.) — these become `rico:includes` / `rico:isPartOf` in RiC-O.
- All item sets (re-purposed as RiC-O instantiation groupings or kept as collections).

## What changes for users

- More precise class facet on the public site (Fonds, File, Record instead of generic Collection/Series).
- Site URLs unchanged if CleanUrl is identifier-based by then (it should be).
- Search and browse behave the same; faceted browse gains archival fidelity.

## Decision criteria for triggering this

Migrate when **any** of:
- Project secures funding for the buildout phase (post-feasibility study).
- An archival aggregator we want to feed (EHRI, APE) requires standards-conformant metadata.
- Cross-archive interoperability (NLI Israel, Bundesarchiv) becomes a priority.

Until then, the Option 1 renames (template + nav-page labels, completed 2026-06-08) keep the in-house vocabulary internally consistent.
