/**
 * Re-anchor an annotation whose pane text has changed since it was made.
 *
 * Regenerating a Hebrew translation shifts every offset in that pane, so
 * offsets are the fast path, not the anchor of record — the quote is. This
 * implements the usual three-step fallback:
 *
 *   1. prefix + quote + suffix — near-certain identification
 *   2. quote alone, nearest to the old offset if it occurs more than once
 *   3. give up: mark orphan, keep the frozen quote, show it in the rail
 *
 * Step 3 is deliberately loud. An annotation quietly re-anchored to the wrong
 * passage is worse than one the PI is told has come loose.
 */

import type { Annotation } from './types';

export interface Relocated extends Annotation {
  relocated: boolean;
}

function allIndexesOf(haystack: string, needle: string): number[] {
  if (!needle) return [];
  const out: number[] = [];
  let i = haystack.indexOf(needle);
  while (i !== -1) {
    out.push(i);
    i = haystack.indexOf(needle, i + 1);
  }
  return out;
}

export function relocate(a: Annotation, paneText: string): Relocated {
  // Fast path: the pane is unchanged, or the offsets still hold the quote.
  if (paneText.slice(a.start_offset, a.end_offset) === a.quote) {
    return { ...a, status: a.status === 'orphan' ? 'ok' : a.status, relocated: false };
  }

  // 1. The full context triple is unique in all but pathological cases.
  if (a.prefix || a.suffix) {
    const hits = allIndexesOf(paneText, a.prefix + a.quote + a.suffix);
    if (hits.length === 1) {
      const start = hits[0] + a.prefix.length;
      return {
        ...a,
        start_offset: start,
        end_offset: start + a.quote.length,
        status: 'relocated',
        relocated: true,
      };
    }
  }

  // 2. The quote alone; if ambiguous, prefer the occurrence nearest to where
  //    it used to be, since edits rarely move text far.
  const hits = allIndexesOf(paneText, a.quote);
  if (hits.length > 0) {
    const start = hits.reduce((best, h) =>
      Math.abs(h - a.start_offset) < Math.abs(best - a.start_offset) ? h : best
    );
    return {
      ...a,
      start_offset: start,
      end_offset: start + a.quote.length,
      status: 'relocated',
      relocated: true,
    };
  }

  // 3. Lost. Keep everything, highlight nothing.
  return { ...a, status: 'orphan', relocated: true };
}

export function relocateAll(
  annotations: Annotation[],
  paneTexts: Record<string, { text: string; sha256: string }>
): Relocated[] {
  return annotations.map((a) => {
    const pane = paneTexts[a.pane];
    if (!pane) return { ...a, status: 'orphan' as const, relocated: false };
    if (pane.sha256 === a.pane_sha256) {
      return { ...a, relocated: false };
    }
    return relocate(a, pane.text);
  });
}
