// Server-side access to the built corpus in content/.
//
// Bundles are read from disk and cached in module scope rather than imported,
// so a rebuild does not require a redeploy in dev and the serverless bundle
// does not inline a megabyte of JSON into every route.

import { readFile } from 'node:fs/promises';
import { join } from 'node:path';
import type { CorpusIndex, DocBundle } from './types';

const CONTENT = join(process.cwd(), 'content');

let indexCache: CorpusIndex | null = null;
const docCache = new Map<string, DocBundle>();

export async function getIndex(): Promise<CorpusIndex> {
  if (!indexCache) {
    indexCache = JSON.parse(
      await readFile(join(CONTENT, 'index.json'), 'utf8')
    ) as CorpusIndex;
  }
  return indexCache;
}

/**
 * The bundle as the browser may see it.
 *
 * The scans Blob store is public: its URLs fetch without auth, forever, by
 * anyone who has them. Handing the bundle straight to a client component puts
 * every one of them in the RSC payload, so the password gates the page but not
 * the images behind it. The client never needs the URL — `<img>` loads through
 * `/api/scan/<docId>/<page>`, which re-checks the session — so it only needs to
 * know whether a facsimile exists at all.
 *
 * Call this on anything crossing into a client component. `getDoc` itself must
 * keep the URL: the /api/scan proxy is what resolves it.
 */
export function forClient(doc: DocBundle): DocBundle {
  const src = doc.panes.source;
  if (!src?.pages) return doc;
  return {
    ...doc,
    panes: {
      ...doc.panes,
      source: {
        ...src,
        pages: src.pages.map((p) =>
          'scan_url' in p
            ? { ...p, scan_url: null, has_scan: Boolean(p.scan_url) }
            : p
        ),
      },
    },
  };
}

export async function getDoc(docId: string): Promise<DocBundle | null> {
  // doc_id reaches us from the URL; keep it to the shape the build emits so a
  // crafted id cannot walk out of content/docs.
  if (!/^[A-Za-z0-9_.-]+$/.test(docId)) return null;
  const hit = docCache.get(docId);
  if (hit) return hit;
  try {
    const doc = JSON.parse(
      await readFile(join(CONTENT, 'docs', `${docId}.json`), 'utf8')
    ) as DocBundle;
    docCache.set(docId, doc);
    return doc;
  } catch {
    return null;
  }
}

/** Reading order: cases by number, documents by id within a case. */
export async function getNeighbours(
  docId: string
): Promise<{ prev: string | null; next: string | null; position: number; total: number }> {
  const index = await getIndex();
  const ids = index.docs.map((d) => d.doc_id);
  const i = ids.indexOf(docId);
  return {
    prev: i > 0 ? ids[i - 1] : null,
    next: i >= 0 && i < ids.length - 1 ? ids[i + 1] : null,
    position: i + 1,
    total: ids.length,
  };
}
