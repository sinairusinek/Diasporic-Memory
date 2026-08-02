/**
 * What each stretch of a pane is worth, and how that carries across languages.
 *
 * Two things end up on the same axis: the model's page segmentation (regions —
 * which article on a scanned sheet is the document) and the PI's own judgement
 * (irrelevant / contextual). Where they disagree the hand-made mark wins; the
 * model's is a guess and hers is a decision.
 *
 * Nothing here removes text. Marks drive how a run is displayed, and every
 * display state is reversible with a click.
 */
import type { Annotation, Pane, PaneName, Region } from './types';

export type Level = 'keep' | 'contextual' | 'irrelevant' | 'drop' | 'chrome';

export interface Mark {
  start: number;
  end: number;
  level: Level;
  what: string;
  /** Set when the mark came from a hand judgement, so it can be undone. */
  annotationId?: number;
  /** True when the mark was carried over from the other language. */
  projected?: boolean;
}

/**
 * Carry a span from one pane to the other through the page/turn alignment.
 *
 * The alignment is block-level — translate_he.py works a page at a time — so
 * within a block the position is interpolated by character proportion. That is
 * an estimate, and it is only ever used to decide how to *display* the other
 * pane. It is never stored, and never becomes an annotation anchor: those stay
 * in the pane the PI actually selected in.
 */
export function projectSpan(
  align: { src: [number, number]; tgt: [number, number] }[] | undefined,
  span: { start: number; end: number },
  direction: 'toTranslation' | 'toSource'
): { start: number; end: number }[] {
  if (!align?.length) return [];
  const out: { start: number; end: number }[] = [];
  for (const a of align) {
    const [fa, fb] = direction === 'toTranslation' ? a.src : a.tgt;
    const [ta, tb] = direction === 'toTranslation' ? a.tgt : a.src;
    const lo = Math.max(span.start, fa);
    const hi = Math.min(span.end, fb);
    if (hi <= lo) continue;
    const fromLen = fb - fa;
    const toLen = tb - ta;
    if (fromLen <= 0 || toLen <= 0) continue;
    // A block covered end to end projects to the whole block, so a page marked
    // irrelevant folds the whole page rather than 98% of it.
    const startFrac = lo <= fa ? 0 : (lo - fa) / fromLen;
    const endFrac = hi >= fb ? 1 : (hi - fa) / fromLen;
    out.push({
      start: Math.round(ta + startFrac * toLen),
      end: Math.round(ta + endFrac * toLen),
    });
  }
  return out.filter((s) => s.end > s.start);
}

const PRIORITY: Record<Level, number> = {
  irrelevant: 3,
  contextual: 3,
  drop: 1,
  chrome: 1,
  keep: 0,
};

/**
 * Flatten possibly-overlapping marks into a sorted, non-overlapping list.
 *
 * Higher priority claims its span first; lower-priority marks are clipped
 * around what is already taken. Ties go to whichever came first in the input,
 * which is why callers pass hand marks ahead of model regions.
 */
export function flatten(marks: Mark[]): Mark[] {
  const ordered = [...marks]
    .filter((m) => m.end > m.start)
    .sort((a, b) => PRIORITY[b.level] - PRIORITY[a.level] || a.start - b.start);

  const claimed: Mark[] = [];
  for (const m of ordered) {
    let pieces = [{ start: m.start, end: m.end }];
    for (const c of claimed) {
      const next: typeof pieces = [];
      for (const p of pieces) {
        if (c.end <= p.start || c.start >= p.end) {
          next.push(p);
          continue;
        }
        if (p.start < c.start) next.push({ start: p.start, end: c.start });
        if (p.end > c.end) next.push({ start: c.end, end: p.end });
      }
      pieces = next;
      if (!pieces.length) break;
    }
    for (const p of pieces) claimed.push({ ...m, ...p });
  }
  return claimed.sort((a, b) => a.start - b.start);
}

/** Every hand-made relevance judgement on a document, in its own pane. */
export function relevanceMarks(annotations: Annotation[]): Annotation[] {
  return annotations.filter(
    (a) => a.kind === 'relevance' && a.status !== 'orphan'
  );
}

/**
 * The display marks for one pane: hand judgements first (its own, then those
 * carried over from the other language), then the model's regions.
 */
export function marksForPane(
  paneName: PaneName,
  translation: Pane | null,
  annotations: Annotation[],
  regions: Region[]
): Mark[] {
  const hand = relevanceMarks(annotations);
  const marks: Mark[] = [];

  for (const a of hand) {
    const level = (a.body as { relevance: Level }).relevance;
    if (a.pane === paneName) {
      marks.push({
        start: a.start_offset,
        end: a.end_offset,
        level,
        what: level === 'irrelevant' ? 'Marked irrelevant' : 'Marked contextual',
        annotationId: a.id,
      });
    } else {
      const dir = paneName === 'translation' ? 'toTranslation' : 'toSource';
      const span = { start: a.start_offset, end: a.end_offset };
      for (const s of projectSpan(translation?.align, span, dir)) {
        marks.push({
          ...s,
          level,
          what:
            (level === 'irrelevant' ? 'Marked irrelevant' : 'Marked contextual') +
            ' in the other language',
          annotationId: a.id,
          projected: true,
        });
      }
    }
  }

  // The model's page segmentation only exists for, and only means anything in,
  // the source pane.
  if (paneName === 'source') {
    for (const r of regions) {
      if (r.label === 'keep') continue;
      marks.push({
        start: r.start,
        end: r.end,
        level: r.label,
        what: r.what,
      });
    }
  }

  return flatten(marks);
}
