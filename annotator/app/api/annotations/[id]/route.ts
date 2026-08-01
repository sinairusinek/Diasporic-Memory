import { NextResponse } from 'next/server';
import { deleteAnnotation, updateAnnotationBody } from '@/lib/store';
import type { AnnotationBody } from '@/lib/types';

export const runtime = 'nodejs';

type Ctx = { params: Promise<{ id: string }> };

export async function PATCH(req: Request, ctx: Ctx) {
  const id = Number((await ctx.params).id);
  if (!Number.isInteger(id)) {
    return NextResponse.json({ error: 'bad id' }, { status: 400 });
  }
  const payload = (await req.json().catch(() => null)) as { body?: AnnotationBody } | null;
  if (!payload?.body) {
    return NextResponse.json({ error: 'body required' }, { status: 400 });
  }
  const updated = await updateAnnotationBody(id, payload.body);
  if (!updated) return NextResponse.json({ error: 'not found' }, { status: 404 });
  return NextResponse.json({ annotation: updated });
}

export async function DELETE(_req: Request, ctx: Ctx) {
  const id = Number((await ctx.params).id);
  if (!Number.isInteger(id)) {
    return NextResponse.json({ error: 'bad id' }, { status: 400 });
  }
  const ok = await deleteAnnotation(id);
  return NextResponse.json({ ok }, { status: ok ? 200 : 404 });
}
