// Apply db/schema.sql. Idempotent (every statement is IF NOT EXISTS), so it is
// safe to re-run against a database that already holds annotations.
//
// This runs as part of the build, not only by hand. `relevance` was added to
// the `kind` check constraint in schema.sql and shipped in the app, but nobody
// ran db:push against production, so every relevance save failed on a check
// constraint that predated the kind. Code and schema now deploy together.
import { readFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { neon } from '@neondatabase/serverless';

const here = dirname(fileURLToPath(import.meta.url));

const url =
  process.env.POSTGRES_URL ??
  process.env.DATABASE_URL ??
  process.env.POSTGRES_URL_NON_POOLING;

// A laptop's .env.local holds redacted placeholders — `vercel env pull` will
// not hand back a Neon marketplace secret — so a local build has no database
// to migrate and should still succeed. A skip here is only ever local: on
// Vercel the connection string is real, and `--require-db` makes its absence
// fatal rather than quietly shipping code ahead of its schema.
const usable = url && /^postgres(ql)?:\/\/\S+/.test(url);
if (!usable) {
  const why = url ? 'is not a connection string' : 'is not set';
  if (process.argv.includes('--require-db')) {
    console.error(`migrate: POSTGRES_URL ${why} — refusing to build.`);
    process.exit(1);
  }
  console.log(`migrate: skipped — POSTGRES_URL ${why} (see .env.example).`);
  process.exit(0);
}

const sql = neon(url);
const schema = await readFile(resolve(here, '../db/schema.sql'), 'utf8');

// Comments are stripped per line rather than per statement: every `create
// table` here is preceded by a comment block, so testing whether the whole
// chunk starts with `--` silently skipped every table in the file.
let applied = 0;
for (const stmt of schema
  .split(/;\s*$/m)
  .map((s) =>
    s
      .split('\n')
      .filter((line) => !line.trim().startsWith('--'))
      .join('\n')
      .trim()
  )
  .filter(Boolean)) {
  await sql.query(stmt);
  applied += 1;
}

const tables = await sql`
  select tablename from pg_tables where schemaname = 'public' order by tablename`;
console.log(
  `schema applied — ${applied} statements, tables: ${tables
    .map((t) => t.tablename)
    .join(', ')}`
);
