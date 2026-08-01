import { NextResponse } from 'next/server';
import { COOKIE, cookieOptions, passwordMatches, signSession } from '@/lib/auth';

export const runtime = 'nodejs';

// One user, so an in-process counter is proportionate. It resets on cold start,
// which is fine: the point is to make an online guessing attack slow, not to be
// a durable rate limiter.
const attempts = new Map<string, { n: number; until: number }>();
const MAX = 8;
const WINDOW_MS = 10 * 60 * 1000;

export async function POST(req: Request) {
  const ip = req.headers.get('x-forwarded-for')?.split(',')[0]?.trim() ?? 'local';
  const now = Date.now();
  const rec = attempts.get(ip);
  if (rec && rec.until > now && rec.n >= MAX) {
    return NextResponse.json(
      { error: 'too many attempts, try again later' },
      { status: 429 }
    );
  }

  const secret = process.env.ANNOTATOR_SECRET;
  const expected = process.env.ANNOTATOR_PASSWORD;
  if (!secret || !expected) {
    return NextResponse.json(
      { error: 'ANNOTATOR_SECRET / ANNOTATOR_PASSWORD are not set' },
      { status: 500 }
    );
  }

  const { password } = (await req.json().catch(() => ({}))) as { password?: string };
  if (!password || !(await passwordMatches(password, expected))) {
    const next = rec && rec.until > now ? rec.n + 1 : 1;
    attempts.set(ip, { n: next, until: now + WINDOW_MS });
    return NextResponse.json({ error: 'wrong password' }, { status: 401 });
  }

  attempts.delete(ip);
  const res = NextResponse.json({ ok: true });
  res.cookies.set(COOKIE, await signSession(secret), cookieOptions);
  return res;
}
