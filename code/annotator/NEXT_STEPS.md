# Annotator — handoff and open decisions

State as of 2026-08-01. The corpus builds, the app runs, and the annotation
loop is verified end to end. Two things are unfinished, both waiting on a
decision rather than on code.

```sh
python code/annotator/build_all.py --free-only   # rebuild the corpus, no cost
cd annotator && npm install && npm run dev       # http://localhost:3000
```

`84 documents in 23 cases · written 30 (808K chars) · oral 54 (201K chars) ·
280 pre-highlights · 65 tags · translated 1/84`

---

## 1. Hebrew translation — switching to Gemini 3

**Status 2026-08-01: the swap below has been made.** `llm.py` imports
`google.genai` and `MODEL` defaults to `gemini-3.1-pro-preview`
(override with `ANNOTATOR_MODEL`); `google-genai` is in `code/requirements.txt`.
One document has been translated as a smoke test (`0276-D17`, 1/84). The rest
of this section is kept as the record of what changed and what still needs
re-verifying on a full run — see *Re-verify these two after the swap*.

The three model-backed stages had never run (the Anthropic key had no credit).
`translate_he.py`, `prehighlight_claude.py` and `project_highlights.py` are
written, cached and wired into `build_all.py`; the app degrades visibly without
them, showing *"No Hebrew translation has been generated for this document
yet"* per document rather than pretending.

**Only [`llm.py`](llm.py) is provider-specific.** Every script goes through one
function, so this is a single-file swap:

```python
llm.ask(system, user, task, usage=None, max_tokens=..., effort=..., force=False) -> str
llm.MODEL          # recorded into each bundle's translation.model, and into cache keys
llm.Usage          # .add(resp.usage) / .hit() / .report()
```

| Caller | task | max_tokens | effort |
|---|---|--:|---|
| `translate_he.py` | `translate_he` | 16000 | medium |
| `prehighlight_claude.py` | `prehighlight` | 8000 | medium |
| `project_highlights.py` | `project_he` | 2000 | low |

### What to change in `llm.py`

1. `client()` → `google.genai` client; `pip install google-genai`, add to
   `code/requirements.txt`.
2. `ask()` body → `generate_content`. The `system` argument is a list of
   content blocks (so the Anthropic version could put `cache_control` on the
   last one) — collapse it to a single `system_instruction` string.
3. `effort` → whatever thinking-budget knob Gemini exposes, or drop it.
4. `Usage.add()` expects `.input_tokens` / `.output_tokens` /
   `.cache_read_input_tokens`. Adapt from Gemini's `usage_metadata`
   (`prompt_token_count`, `candidates_token_count`).
5. `Usage.report()` has Opus 5 list pricing hardcoded — update the numbers.
6. The refusal branch checks `resp.stop_reason == "refusal"`. Replace with
   Gemini's `finish_reason` / `prompt_feedback.block_reason`.

**Leave the cache alone.** `cache_key()` already includes `MODEL`, so Gemini
results land beside any Anthropic ones instead of colliding — and re-running a
stage after the swap re-translates from scratch, as it should.

**The prompts are provider-neutral** and worth keeping verbatim: the
translation prompt's seven rules (`translate_he.py`), the no-forced-Heimat
rules in `prehighlight_claude.py`, and the copy-don't-paraphrase instruction in
`project_highlights.py`.

### Re-verify these two after the swap

- **`prehighlight_claude.py` drops any quote it cannot locate by exact string
  search.** That guard is what stops a model-invented quote becoming a
  highlight, and the drop rate is a good health signal — if Gemini normalizes
  whitespace or fixes OCR errors when quoting, the drop rate will spike. Watch
  the `N dropped` column on the first run.
- **`project_highlights.py` asks the model to copy a Hebrew substring
  verbatim** and drops anything that doesn't match. Same failure mode.

### Optional tidy

If you want the provenance field to stop saying "claude", rename
`source: "claude"` → `"model"` and touch four places:

- `code/annotator/prehighlight_claude.py` (sets it, and strips prior rows by it)
- `code/annotator/build_all.py` — the `STAGES` list names the file
- `annotator/lib/types.ts` — `source: 'keyword' | 'claude'`
- `annotator/components/TextPane.tsx` — the `(Claude)` tooltip suffix

Cosmetic; nothing breaks if you leave it.

### Cost

~740K chars of German across 225 translatable pages, plus one call per document
for pre-highlights and one per strict highlight for projection. Budget for the
translation pass to dominate. Run one document first:

```sh
python code/annotator/translate_he.py --docs 0276-D17   # 2 pages, ~5K chars
```

---

## 2. Database

Vercel's filesystem is ephemeral and read-only, so the local JSON store under
`annotator/.dev-data/` can never ship — `lib/store.ts` refuses to run it in
production. Something real is needed before deploying.

`lib/store.ts` dispatches on `POSTGRES_URL`, so **only `lib/db.ts` changes**;
the API routes, relocation logic and export all stay put.

| Option | Effort | Notes |
|---|---|---|
| **Neon** (Vercel-native Postgres) | **none** | `db/schema.sql`, `scripts/migrate.mjs` and `lib/db.ts` are already written against `@neondatabase/serverless`. Add the integration, `npm run db:push`, done. Free tier is far beyond what one annotator needs. |
| Supabase | small | Also Postgres, but the Neon HTTP driver only talks to Neon — swap in `pg` or `postgres` in `lib/db.ts`. Buys auth you don't need (the password gate already works). |
| Commit to GitHub via the API | medium | No database, fully version-controlled. But saves take ~2s, the history gets noisy, and **this repo is public** — DGD-restricted oral quotes would be published on every save. Not advisable while that question is open. |

Neon is the path of least resistance and the one the code already assumes.

Whichever you pick, the export is unaffected:

```sh
python code/annotator/export_annotations.py --dsn "$POSTGRES_URL"
```

Postgres stays a cache; `data/annotator/annotations.{tsv,json}` is the record.

---

## 3. Two findings worth acting on independently

**~~`0047-2` is unreadable as transcribed.~~ Fixed 2026-08-01.** The Sharett↔Frank
Wiesbaden letters were almost entirely graded `poor` — German cursive, which
Tesseract cannot read at all. All 28 pages have been run through Transkribus
HTR (model 50870, German Giant I) and the cluster now grades 8 clean / 14 mixed
/ 6 poor, up from 2 / 10 / 16. The six that remain `poor` are envelopes and
blank envelope versos with no prose on them; they are correctly graded.

`build_written.py` now reads both engines per page and keeps whichever grades
better, so a targeted HTR run can rescue a folder without regressing the pages
Tesseract already handled. Each page records `ocr_engine`, and `ocr_conf` is
`null` for Transkribus pages — the Processing API returns plain text with no
per-page confidence, so `grade_page` falls back to its two text-shape signals.

To rescue another folder:

```sh
python code/recatalog/transkribus_htr.py --folder 0047-2 --pages 19,21,33 --model 50870
python code/annotator/build_all.py --free-only --docs 0047-2
```

Use `code/recatalog/transkribus_htr.py`, **not** `code/transkribus_client.py` —
the latter only downloads transcripts that already exist on TrpServer and
cannot trigger recognition.

**This repo is public and already contains 2.04M characters of verbatim DGD
transcript** in `data/israelkorpus/structured/`, committed before this work.
The annotator's 54 oral bundles are a 201K-char subset and add no new exposure,
but the DGD publication question recorded as unresolved is, in practice,
already answered by the repository being public. Worth putting to Guy before
the app goes live.
