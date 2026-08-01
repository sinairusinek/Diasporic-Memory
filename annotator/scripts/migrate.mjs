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

for (const stmt of schema
  .split(/;\s*$/m)
  .map((s) => s.trim())
  .filter((s) => s && !s.startsWith('--'))) {
  await sql.query(stmt);
}
console.log('schema applied');
