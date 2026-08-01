/**
 * Flatten overlapping highlight spans into a non-overlapping render list.
 *
 * This is the reason the anchoring works. If overlapping spans were rendered as
 * nested elements, the DOM under a pane would depend on which highlights happen
 * to overlap, and the tree walker in offsets.ts would still be correct but far
 * more fragile to reason about. Instead we cut the text at every span boundary
 * and emit one flat sibling per interval, tagged with the ids covering it. The
 * rendered text is then a plain sequence of text nodes in document order,
 * character-identical to the pane's text.
 */

export interface Span {
  id: string;
  start: number;
  end: number;
}

export interface Segment {
  start: number;
  end: number;
  ids: string[];
}

export function segment(textLength: number, spans: Span[]): Segment[] {
  const cuts = new Set<number>([0, textLength]);
  for (const s of spans) {
    if (s.end <= s.start) continue;
    const a = Math.max(0, Math.min(textLength, s.start));
    const b = Math.max(0, Math.min(textLength, s.end));
    if (b > a) {
      cuts.add(a);
      cuts.add(b);
    }
  }
  const points = [...cuts].sort((a, b) => a - b);

  const out: Segment[] = [];
  for (let i = 0; i < points.length - 1; i++) {
    const start = points[i];
    const end = points[i + 1];
    if (end <= start) continue;
    const ids = spans
      .filter((s) => s.start <= start && s.end >= end && s.end > s.start)
      .map((s) => s.id);
    out.push({ start, end, ids });
  }
  return out;
}

/**
 * Trim a selection off surrounding whitespace.
 *
 * A double-click or a drag past the end of a word routinely grabs a trailing
 * space or newline; storing it would make the quote selector match less
 * reliably after a re-render. Returns null if nothing is left.
 */
export function trimRange(
  text: string,
  start: number,
  end: number
): { start: number; end: number } | null {
  let a = start;
  let b = end;
  while (a < b && /\s/.test(text[a])) a++;
  while (b > a && /\s/.test(text[b - 1])) b--;
  return b > a ? { start: a, end: b } : null;
}
