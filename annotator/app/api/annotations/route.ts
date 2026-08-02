import { NextResponse } from 'next/server';
import { getDoc } from '@/lib/corpus';
import { insertAnnotation, listAnnotations, persistRelocation } from '@/lib/store';
import { relocateAll } from '@/lib/relocate';
import type { AnnotationBody, AnnotationKind, PaneName } from '@/lib/types';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const KINDS: AnnotationKind[] = ['comment', 'tag', 'keywords', 'relevance'];
const PANES: PaneName[] = ['source', 'translation'];

export async function GET(req: Request) {
  const docId = new URL(req.url).searchParams.get('docId');
  if (!docId) return NextResponse.json({ error: 'docId required' }, { status: 400 });

  const doc = await getDoc(docId);
  if (!doc) return NextResponse.json({ error: 'unknown document' }, { status: 404 });

  const panes: Record<string, { text: string; sha256: string }> = {
    source: { text: doc.panes.source.text, sha256: doc.panes.source.sha256 },
  };
  if (doc.panes.translation) {
    panes.translation = {
      text: doc.panes.translation.text,
      sha256: doc.panes.translation.sha256,
    };
  }

  const stored = await listAnnotations(docId);
  const fixed = relocateAll(stored, panes);

  // Write successful relocations back so the next load is a straight read.
  await Promise.all(
    fixed
      .filter((a) => a.relocated && a.status === 'relocated')
      .map((a) =>
        persistRelocation(a.id, a.start_offset, a.end_offset, panes[a.pane].sha256)
      )
  );

  return NextResponse.json({
    annotations: fixed.map(({ relocated, ...a }) => a),
    relocated: fixed.filter((a) => a.relocated && a.status === 'relocated').length,
    orphaned: fixed.filter((a) => a.status === 'orphan').length,
  });
}

function validBody(kind: AnnotationKind, body: unknown): AnnotationBody | null {
  if (typeof body !== 'object' || body === null) return null;
  const b = body as Record<string, unknown>;
  if (kind === 'comment') {
    return typeof b.text === 'string' && b.text.trim() ? { text: b.text.trim() } : null;
  }
  if (kind === 'tag') {
    return typeof b.tag === 'string' && b.tag.trim() ? { tag: b.tag.trim() } : null;
  }
  if (kind === 'relevance') {
    return b.relevance === 'irrelevant' || b.relevance === 'contextual'
      ? { relevance: b.relevance }
      : null;
  }
  if (Array.isArray(b.keywords)) {
    const kws = b.keywords
      .filter((k): k is string => typeof k === 'string')
      .map((k) => k.trim())
      .filter(Boolean);
    return kws.length ? { keywords: kws } : null;
  }
  return null;
}

export async function POST(req: Request) {
  const payload = (await req.json().catch(() => null)) as Record<string, unknown> | null;
  if (!payload) return NextResponse.json({ error: 'bad json' }, { status: 400 });

  const { docId, pane, kind, start, end } = payload as {
    docId?: string;
    pane?: PaneName;
    kind?: AnnotationKind;
    start?: number;
    end?: number;
  };

  if (!docId || !pane || !kind) {
    return NextResponse.json({ error: 'docId, pane, kind required' }, { status: 400 });
  }
  if (!PANES.includes(pane) || !KINDS.includes(kind)) {
    return NextResponse.json({ error: 'unknown pane or kind' }, { status: 400 });
  }
  if (typeof start !== 'number' || typeof end !== 'number' || end <= start) {
    return NextResponse.json({ error: 'invalid span' }, { status: 400 });
  }

  const body = validBody(kind, payload.body);
  if (!body) return NextResponse.json({ error: 'invalid body' }, { status: 400 });

  const doc = await getDoc(docId);
  if (!doc) return NextResponse.json({ error: 'unknown document' }, { status: 404 });
  const target = pane === 'source' ? doc.panes.source : doc.panes.translation;
  if (!target) {
    return NextResponse.json({ error: 'document has no such pane' }, { status: 400 });
  }

  // Re-verify the anchor server-side against our own copy of the text. The
  // client already checked; this catches a stale tab whose pane text no longer
  // matches what was built. Refusing is better than storing a wrong anchor.
  const quote = target.text.slice(start, end);
  if (!quote || (typeof payload.quote === 'string' && payload.quote !== quote)) {
    return NextResponse.json(
      { error: 'span does not match the current text — reload the document' },
      { status: 409 }
    );
  }

  const created = await insertAnnotation({
    doc_id: docId,
    pane,
    kind,
    start_offset: start,
    end_offset: end,
    quote,
    prefix: target.text.slice(Math.max(0, start - 32), start),
    suffix: target.text.slice(end, end + 32),
    pane_sha256: target.sha256,
    body,
  });
  return NextResponse.json({ annotation: created }, { status: 201 });
}
