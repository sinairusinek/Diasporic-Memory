# Source annotation app

Password-gated Next.js app where the PI reads the post-war visit corpus source
by source and marks it up. Deploys to Vercel with **Root Directory = `annotator`**.

Each source view shows a Hebrew metadata block and summary, the source text
(mostly German OCR), and — once generated — a Hebrew translation with the
relevant passages pre-highlighted. Selecting a word or passage in **either**
pane opens a popover offering a plain-text comment, a tag from
[`annotation_scheme_return_spans.md`](../annotation_scheme_return_spans.md)
(all 65, searchable), or a list of keywords.

Content is built by [`code/annotator/`](../code/annotator/); see its README.

> **Picking this up fresh?** Read
> [code/annotator/NEXT_STEPS.md](../code/annotator/NEXT_STEPS.md) — the
> translation pane and the database are both still open.

## Running locally

```sh
python code/annotator/build_all.py --free-only   # build the corpus
cd annotator && npm install
cp .env.example .env.local                       # set ANNOTATOR_PASSWORD + ANNOTATOR_SECRET
npm run dev                                      # http://localhost:3000
```

`npm run sync` (which `predev`/`prebuild` run for you) copies `data/annotator/`
into `content/`. Vercel builds with the root directory set to `annotator`, and
files outside it are not reliably available — copying is less clever than a
symlink and it is the thing that works identically in both places.

**Without `POSTGRES_URL` the app uses a JSON file under `.dev-data/`**, so the
whole annotate → save → reload → re-anchor loop works before you provision
anything. It refuses to run in production.

## Deploying

1. New Vercel project, Root Directory `annotator`.
2. Add the Neon integration, then `npm run db:push` against `POSTGRES_URL`.
3. Set `ANNOTATOR_PASSWORD`, `ANNOTATOR_SECRET` (`openssl rand -base64 32`),
   `POSTGRES_URL`, and optionally `BLOB_READ_WRITE_TOKEN` — **for Production
   *and* Preview**. Preview deployments are the usual way a gate leaks.

## Why the anchoring code looks the way it does

Annotations are anchored to characters, and the whole design exists to keep
that anchor honest across a rebuild.

- **`lib/segments.ts` never nests highlights.** Overlapping spans are cut into
  flat, non-overlapping siblings, so the rendered text is a plain sequence of
  text nodes in document order.
- **`lib/offsets.ts` maps selections by measuring a `Range`**, the technique
  `rangy` and Hypothesis use. It only works while the rendered DOM is
  character-identical to the pane text — hence `white-space: pre-wrap`, no
  generated content, and `assertPaneIntegrity()` checking it on mount in dev.
- **Every save is verified twice.** The client compares
  `paneText.slice(start,end)` to the selection; the server re-checks against its
  own copy and returns 409 rather than storing a mis-anchored span.
- **Offsets are the fast path, not the anchor of record.** Each row also stores
  a quote plus 32 characters of context and the pane's hash. When a
  re-translation shifts the text, `lib/relocate.ts` finds the passage again and
  the row is marked `relocated`; when the passage is genuinely gone it becomes
  `orphan` and is shown in the rail with its frozen quote. Nothing is lost
  silently, and nothing is re-anchored to the wrong sentence quietly.

Bidi: the chrome is LTR and each pane sets its own `dir` attribute (not CSS
`direction`, which does not drive selection). German is always the left column
and Hebrew the right, so the reading position never flips. Selections crossing a
bidi boundary look visually discontiguous but are logically contiguous — correct
by construction, since everything is computed from logical offsets.

## Restricted material

The 54 oral-testimony bundles are Israelkorpus (Betten) excerpts under DGD
terms. They are `public: false`, never leave the password gate, and their quotes
are redacted in the committed export. Page scans are served through
`/api/scan/…` rather than `public/`, because files in `public/` bypass
middleware entirely.
