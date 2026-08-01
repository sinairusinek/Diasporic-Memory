// Apply db/schema.sql. Idempotent (every statement is IF NOT EXISTS), so it is
// safe to re-run against a database that already holds annotations.
import { readFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { neon } from '@neondatabase/serverless';

const here = dirname(fileURLToPath(import.meta.url));

const url =
  process.env.POSTGRES_URL ??
  process.env.DATABASE_URL ??
  process.env.POSTGRES_URL_NON_POOLING;
if (!url) {
  console.error('Set POSTGRES_URL (see .env.example) before running db:push.');
  process.exit(1);
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
