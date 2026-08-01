// Storage dispatch: Neon Postgres in production, a JSON file in local dev.
//
// The file store exists so the annotate -> save -> reload -> re-anchor loop can
// be exercised without provisioning a database — the anchoring code is the part
// most worth testing, and it should not be gated behind a Neon signup. It is
// never used when POSTGRES_URL is set, and it refuses to run in production.

import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import * as pg from './db';
import type { Annotation, AnnotationBody } from './types';

export type { NewAnnotation } from './db';
import type { NewAnnotation } from './db';

const FILE = join(process.cwd(), '.dev-data', 'annotations.json');

export function usingPostgres(): boolean {
  return Boolean(
    process.env.POSTGRES_URL ??
      process.env.DATABASE_URL ??
      process.env.POSTGRES_URL_NON_POOLING
  );
}

function assertDevOnly(): void {
  if (process.env.NODE_ENV === 'production') {
    throw new Error(
      'POSTGRES_URL is not set. The file store is for local development only — ' +
        'set POSTGRES_URL to a Neon connection string.'
    );
  }
}

interface FileShape {
  nextId: number;
  annotations: Annotation[];
  reviews: Record<string, { verdict: string; note: string }>;
}

async function readFileStore(): Promise<FileShape> {
  try {
    return JSON.parse(await readFile(FILE, 'utf8')) as FileShape;
  } catch {
    return { nextId: 1, annotations: [], reviews: {} };
  }
}

async function writeFileStore(data: FileShape): Promise<void> {
  await mkdir(dirname(FILE), { recursive: true });
  await writeFile(FILE, JSON.stringify(data, null, 1), 'utf8');
}

/**
 * Serialize every read-modify-write against the file.
 *
 * Postgres gives each UPDATE atomicity for free; a JSON file does not. The
 * relocation pass writes back one row per re-anchored annotation with
 * Promise.all, so without this the concurrent read-modify-write cycles clobber
 * each other and some rows silently keep their stale offsets.
 */
let queue: Promise<unknown> = Promise.resolve();

function serialize<T>(fn: (store: FileShape) => Promise<T> | T): Promise<T> {
  const next = queue.then(async () => {
    const store = await readFileStore();
    const result = await fn(store);
    await writeFileStore(store);
    return result;
  });
  queue = next.catch(() => undefined);
  return next;
}

export async function listAnnotations(docId: string): Promise<Annotation[]> {
  if (usingPostgres()) return pg.listAnnotations(docId);
  assertDevOnly();
  const store = await readFileStore();
  return store.annotations
    .filter((a) => a.doc_id === docId)
    .sort((a, b) => a.pane.localeCompare(b.pane) || a.start_offset - b.start_offset);
}

export async function countsByDoc(): Promise<Record<string, number>> {
  if (usingPostgres()) return pg.countsByDoc();
  assertDevOnly();
  const store = await readFileStore();
  const out: Record<string, number> = {};
  for (const a of store.annotations) out[a.doc_id] = (out[a.doc_id] ?? 0) + 1;
  return out;
}

export async function insertAnnotation(a: NewAnnotation): Promise<Annotation> {
  if (usingPostgres()) return pg.insertAnnotation(a);
  assertDevOnly();
  return serialize((store) => {
    const now = new Date().toISOString();
    const row: Annotation = {
      id: store.nextId++,
      ...a,
      status: 'ok',
      created_at: now,
      updated_at: now,
    };
    store.annotations.push(row);
    return row;
  });
}

export async function updateAnnotationBody(
  id: number,
  body: AnnotationBody
): Promise<Annotation | null> {
  if (usingPostgres()) return pg.updateAnnotationBody(id, body);
  assertDevOnly();
  return serialize((store) => {
    const row = store.annotations.find((a) => a.id === id);
    if (!row) return null;
    row.body = body;
    row.updated_at = new Date().toISOString();
    return row;
  });
}

export async function persistRelocation(
  id: number,
  start: number,
  end: number,
  paneSha: string
): Promise<void> {
  if (usingPostgres()) return pg.persistRelocation(id, start, end, paneSha);
  assertDevOnly();
  await serialize((store) => {
    const row = store.annotations.find((a) => a.id === id);
    if (!row) return;
    row.start_offset = start;
    row.end_offset = end;
    row.pane_sha256 = paneSha;
    row.status = 'relocated';
    row.updated_at = new Date().toISOString();
  });
}

export async function deleteAnnotation(id: number): Promise<boolean> {
  if (usingPostgres()) return pg.deleteAnnotation(id);
  assertDevOnly();
  return serialize((store) => {
    const before = store.annotations.length;
    store.annotations = store.annotations.filter((a) => a.id !== id);
    return store.annotations.length !== before;
  });
}

export async function getReview(
  docId: string
): Promise<{ verdict: string; note: string } | null> {
  if (usingPostgres()) return pg.getReview(docId);
  assertDevOnly();
  return (await readFileStore()).reviews[docId] ?? null;
}

export async function setReview(
  docId: string,
  verdict: string,
  note: string
): Promise<void> {
  if (usingPostgres()) return pg.setReview(docId, verdict, note);
  assertDevOnly();
  await serialize((store) => {
    store.reviews[docId] = { verdict, note };
  });
}
