import { neon } from '@neondatabase/serverless';
import type { Annotation, AnnotationBody, AnnotationKind, PaneName } from './types';

// Neon's HTTP driver: one round trip per query, no pool to keep warm, which is
// what a serverless function wants. The connection string is read lazily so
// importing this module does not throw when the app is only serving corpus
// pages (see the try/catch around countsByDoc in app/doc/[docId]/page.tsx).
function db() {
  const url =
    process.env.POSTGRES_URL ??
    process.env.DATABASE_URL ??
    process.env.POSTGRES_URL_NON_POOLING;
  if (!url) throw new Error('POSTGRES_URL is not set');
  return neon(url);
}

export interface NewAnnotation {
  doc_id: string;
  pane: PaneName;
  kind: AnnotationKind;
  start_offset: number;
  end_offset: number;
  quote: string;
  prefix: string;
  suffix: string;
  pane_sha256: string;
  body: AnnotationBody;
}

const COLUMNS =
  'id, doc_id, pane, kind, start_offset, end_offset, quote, prefix, suffix, ' +
  'pane_sha256, body, status, created_at, updated_at';

export async function listAnnotations(docId: string): Promise<Annotation[]> {
  const sql = db();
  const rows = await sql`
    select ${sql.unsafe(COLUMNS)} from annotation
     where doc_id = ${docId}
     order by pane, start_offset, id`;
  return rows as Annotation[];
}

export async function countsByDoc(): Promise<Record<string, number>> {
  const sql = db();
  const rows = (await sql`
    select doc_id, count(*)::int as n from annotation group by doc_id`) as {
    doc_id: string;
    n: number;
  }[];
  return Object.fromEntries(rows.map((r) => [r.doc_id, r.n]));
}

export async function insertAnnotation(a: NewAnnotation): Promise<Annotation> {
  const sql = db();
  const rows = await sql`
    insert into annotation
      (doc_id, pane, kind, start_offset, end_offset,
       quote, prefix, suffix, pane_sha256, body)
    values
      (${a.doc_id}, ${a.pane}, ${a.kind}, ${a.start_offset}, ${a.end_offset},
       ${a.quote}, ${a.prefix}, ${a.suffix}, ${a.pane_sha256},
       ${JSON.stringify(a.body)}::jsonb)
    returning ${sql.unsafe(COLUMNS)}`;
  return rows[0] as Annotation;
}

export async function updateAnnotationBody(
  id: number,
  body: AnnotationBody
): Promise<Annotation | null> {
  const sql = db();
  const rows = await sql`
    update annotation
       set body = ${JSON.stringify(body)}::jsonb, updated_at = now()
     where id = ${id}
    returning ${sql.unsafe(COLUMNS)}`;
  return (rows[0] as Annotation) ?? null;
}

/**
 * Persist a successful relocation so the next load takes the fast path.
 * Orphans deliberately keep their original offsets: if a later rebuild restores
 * the text, the fast-path check rescues them without any special handling.
 */
export async function persistRelocation(
  id: number,
  start: number,
  end: number,
  paneSha: string
): Promise<void> {
  const sql = db();
  await sql`
    update annotation
       set start_offset = ${start}, end_offset = ${end},
           pane_sha256 = ${paneSha}, status = 'relocated', updated_at = now()
     where id = ${id}`;
}

export async function deleteAnnotation(id: number): Promise<boolean> {
  const sql = db();
  const rows = await sql`delete from annotation where id = ${id} returning id`;
  return rows.length > 0;
}

export async function getReview(
  docId: string
): Promise<{ verdict: string; note: string } | null> {
  const sql = db();
  const rows = await sql`select verdict, note from doc_review where doc_id = ${docId}`;
  return (rows[0] as { verdict: string; note: string }) ?? null;
}

export async function setReview(
  docId: string,
  verdict: string,
  note: string
): Promise<void> {
  const sql = db();
  await sql`
    insert into doc_review (doc_id, verdict, note)
    values (${docId}, ${verdict}, ${note})
    on conflict (doc_id) do update
      set verdict = excluded.verdict, note = excluded.note, updated_at = now()`;
}
