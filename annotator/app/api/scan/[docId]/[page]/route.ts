import { NextResponse } from 'next/server';
import { getDoc } from '@/lib/corpus';

export const runtime = 'nodejs';

/**
 * Gated proxy to the page scan in Vercel Blob.
 *
 * Blob URLs are public by default and files under public/ bypass middleware, so
 * neither is an acceptable home for images of rights-uncertain material. Going
 * through a route handler means the session cookie is checked (by middleware)
 * before a single byte is served, and the blob URL is never exposed.
 */
export async function GET(
  _req: Request,
  ctx: { params: Promise<{ docId: string; page: string }> }
) {
  const { docId, page } = await ctx.params;
  const doc = await getDoc(docId);
  if (!doc) return NextResponse.json({ error: 'unknown document' }, { status: 404 });

  const block = (doc.panes.source.pages ?? []).find(
    (p) => String(p.page_no) === page
  );
  if (!block?.scan_url) {
    return NextResponse.json({ error: 'no scan for this page' }, { status: 404 });
  }

  const upstream = await fetch(block.scan_url, { cache: 'force-cache' });
  if (!upstream.ok) {
    return NextResponse.json({ error: 'scan unavailable' }, { status: 502 });
  }
  return new NextResponse(upstream.body, {
    headers: {
      'content-type': upstream.headers.get('content-type') ?? 'image/webp',
      'cache-control': 'private, max-age=86400',
    },
  });
}
