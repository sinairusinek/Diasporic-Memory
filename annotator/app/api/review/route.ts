import { NextResponse } from 'next/server';
import { getReview, setReview } from '@/lib/store';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const VERDICTS = ['relevant', 'not-relevant', 'unsure'];

export async function GET(req: Request) {
  const docId = new URL(req.url).searchParams.get('docId');
  if (!docId) return NextResponse.json({ error: 'docId required' }, { status: 400 });
  return NextResponse.json({ review: await getReview(docId) });
}

/**
 * The PI's verdict on the machine relevance call. Recorded per document because
 * overturning a false positive or negative is itself a research finding, not
 * just navigation state.
 */
export async function POST(req: Request) {
  const { docId, verdict, note } = (await req.json().catch(() => ({}))) as {
    docId?: string;
    verdict?: string;
    note?: string;
  };
  if (!docId || !verdict || !VERDICTS.includes(verdict)) {
    return NextResponse.json({ error: 'docId and a valid verdict required' }, { status: 400 });
  }
  await setReview(docId, verdict, note ?? '');
  return NextResponse.json({ ok: true });
}
