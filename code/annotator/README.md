# Annotator build pipeline

Turns the post-war visit corpus into the bundles the annotation app reads, and
exports the PI's annotations back into `data/`.

The app itself lives in [`annotator/`](../../annotator/); this directory builds
its content.

> **Picking this up fresh?** Read [NEXT_STEPS.md](NEXT_STEPS.md) first — it
> covers the two unfinished pieces (the Hebrew translation pane, moving to
> Gemini 3; and choosing a database) and what to re-verify after each.

## Corpus

84 documents across 23 of the 36 cases in `data/post_war_visits.tsv`:

| | Docs | Chars | Source |
|---|--:|--:|---|
| Written | 30 | 803K | `data/recatalog/{0276-6,0047-2,0444-3,0422-3,0113-41,0185-2}/` |
| Oral | 54 | 201K | `data/israelkorpus/structured/` (excerpt windows only) |

The narrowing from `is_heimat_relevant` to *visit-related* is editorial and
lives as an explicit allow-list in `select_docs.py`. Add or remove a line there
and rebuild; `manifest.tsv` is written for review.

## Running it

```sh
python code/annotator/build_all.py --free-only   # no API cost, no credentials
python code/annotator/build_all.py               # everything available
```

Every stage is idempotent and hash-gated, so re-running is cheap. Stage 9
(`build_index`) validates and **exits non-zero** rather than shipping bundles
whose offsets don't hold — a silently wrong offset is worse than a failed build.

| Stage | Cost | Does |
|---|---|---|
| `select_docs` | free | Curate the visit manifest from the six folders' `catalog.tsv` |
| `build_written` | free | Page OCR → one flat offset space; grade each page |
| `build_oral` | free | Group `heimat_scan.tsv` hits into excerpt windows |
| `prehighlight_keywords` | free | Lexical Heimat/return signals, reusing `code/israelkorpus/scan_heimat_signals.py` |
| `prehighlight_claude` | API | Passages carrying each document's `heimat_rationale` |
| `translate_he` | API | Hebrew translation, page by page |
| `project_highlights` | API | Project source highlights onto the Hebrew pane |
| `build_scans` | Blob | 1600px WebP derivatives → Vercel Blob |
| `build_index` | free | Assemble `index.json`, compile the tag vocabulary, validate |

Needs `ANTHROPIC_API_KEY` for the API stages and `BLOB_READ_WRITE_TOKEN` for
scans. Without either, the corresponding stage is skipped and the app degrades
visibly rather than silently — a document with no translation says so.

## Three things that will bite you

**`textnorm.join_pages` is load-bearing.** Every character offset and content
hash in `data/annotator/` depends on it byte-for-byte. Change it and every
stored annotation offset drifts; the app falls back to quote-relocation for the
whole corpus. Never inline or reimplement it.

**Contributions are keyed by `n`, not list index.** In the Israelkorpus JSON,
`contributions[95]["n"] == 96`. Indexing by position silently shifts every oral
excerpt by one turn.

**Tesseract's confidence is not a quality signal on its own.** The press
montages (0444-3 p225, 0422-3 p108) report `conf >= 0.75` while the reading
order is shredded across columns and Hebrew bleeds through the Latin.
`build_written.grade_page` adds two more signals and grades each page
`clean` / `mixed` / `poor`; `poor` pages are never translated and are flagged in
the UI. Of 471 pages in scope: 82 clean, 143 mixed, 62 poor. `0047-2` — the
Sharett↔Frank letters — is almost entirely `poor`, because it is German cursive,
which Tesseract cannot read. Those need Transkribus HTR before they are usable.

## Export

```sh
python code/annotator/export_annotations.py --dsn "$POSTGRES_URL"
```

Postgres is a cache; the repo is the record. Writes `annotations.tsv` (flat,
readable, oral quotes redacted), `annotations.json` (W3C Web Annotation — the
archival form, carrying both a quote selector and a position selector), and
`annotations_unredacted.tsv` (gitignored).

With `POSTGRES_URL` unset it exports the app's local dev file store instead, so
the round trip is testable without a database.
