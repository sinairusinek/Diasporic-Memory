import { NextResponse, type NextRequest } from 'next/server';
import { COOKIE, verifySession } from '@/lib/auth';

export async function middleware(req: NextRequest) {
  const secret = process.env.ANNOTATOR_SECRET;
  if (!secret) {
    return NextResponse.json(
      { error: 'ANNOTATOR_SECRET is not set on the server' },
      { status: 500 }
    );
  }

  if (await verifySession(secret, req.cookies.get(COOKIE)?.value)) {
    return NextResponse.next();
  }

  // API callers get a status they can act on; browsers get the login form.
  if (req.nextUrl.pathname.startsWith('/api/')) {
    return NextResponse.json({ error: 'unauthenticated' }, { status: 401 });
  }
  const url = req.nextUrl.clone();
  url.pathname = '/login';
  url.search = `?next=${encodeURIComponent(
    req.nextUrl.pathname + req.nextUrl.search
  )}`;
  return NextResponse.redirect(url);
}

export const config = {
  // Everything except the login form itself and Next's own static output.
  // Note this deliberately covers /api/scan: page images are served through a
  // route handler rather than public/, because files in public/ bypass
  // middleware entirely and the oral material must not be reachable ungated.
  matcher: [
    '/((?!_next/static|_next/image|favicon.ico|login|api/login|api/health).*)',
  ],
};
