// Single shared password, no user table.
//
// Everything here uses Web Crypto only, so the same code runs in middleware
// (edge runtime) and in route handlers. `jsonwebtoken` and `bcrypt` would both
// force the login check out of middleware and into a node-only route.

export const COOKIE = 'annot_session';
const TTL_SECONDS = 60 * 60 * 24 * 30;

const enc = new TextEncoder();

function b64urlEncode(bytes: Uint8Array): string {
  let s = '';
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

function b64urlDecode(s: string): Uint8Array {
  const pad = s.replace(/-/g, '+').replace(/_/g, '/');
  const raw = atob(pad + '='.repeat((4 - (pad.length % 4)) % 4));
  return Uint8Array.from(raw, (c) => c.charCodeAt(0));
}

async function key(secret: string): Promise<CryptoKey> {
  return crypto.subtle.importKey(
    'raw',
    enc.encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign', 'verify']
  );
}

/** `<base64url(payload)>.<base64url(hmac)>` */
export async function signSession(secret: string, now = Date.now()): Promise<string> {
  const payload = JSON.stringify({ exp: Math.floor(now / 1000) + TTL_SECONDS });
  const body = b64urlEncode(enc.encode(payload));
  const sig = await crypto.subtle.sign('HMAC', await key(secret), enc.encode(body));
  return `${body}.${b64urlEncode(new Uint8Array(sig))}`;
}

export async function verifySession(
  secret: string,
  token: string | undefined,
  now = Date.now()
): Promise<boolean> {
  if (!token) return false;
  const dot = token.lastIndexOf('.');
  if (dot < 1) return false;
  const body = token.slice(0, dot);
  let sig: Uint8Array;
  try {
    sig = b64urlDecode(token.slice(dot + 1));
  } catch {
    return false;
  }
  const ok = await crypto.subtle.verify(
    'HMAC',
    await key(secret),
    sig as BufferSource,
    enc.encode(body)
  );
  if (!ok) return false;
  try {
    const { exp } = JSON.parse(new TextDecoder().decode(b64urlDecode(body)));
    return typeof exp === 'number' && exp * 1000 > now;
  } catch {
    return false;
  }
}

/**
 * Constant-time password comparison.
 *
 * Comparing the SHA-256 digests rather than the strings means the compared
 * buffers are always 32 bytes, so the loop below leaks neither the password's
 * length nor the position of the first differing character.
 */
export async function passwordMatches(input: string, expected: string): Promise<boolean> {
  if (!expected) return false;
  const [a, b] = await Promise.all([
    crypto.subtle.digest('SHA-256', enc.encode(input)),
    crypto.subtle.digest('SHA-256', enc.encode(expected)),
  ]);
  const x = new Uint8Array(a);
  const y = new Uint8Array(b);
  let diff = 0;
  for (let i = 0; i < x.length; i++) diff |= x[i] ^ y[i];
  return diff === 0;
}

export const cookieOptions = {
  httpOnly: true,
  secure: process.env.NODE_ENV === 'production',
  sameSite: 'lax' as const,
  path: '/',
  maxAge: TTL_SECONDS,
};
