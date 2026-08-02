'use client';

import { useEffect, useMemo, useRef, useState, type CSSProperties } from 'react';
import { assertPaneIntegrity, offsetsToRange, rangeToOffsets } from '@/lib/offsets';
import { segment, trimRange, type Span } from '@/lib/segments';
import type { Mark } from '@/lib/relevance';
import type { Annotation, Pane, PaneName, Prehighlight } from '@/lib/types';

export interface Selected {
  pane: PaneName;
  start: number;
  end: number;
  quote: string;
  x: number;
  y: number;
}

interface Props {
  pane: Pane;
  paneName: PaneName;
  title: string;
  prehighlights: Prehighlight[];
  annotations: Annotation[];
  showStrict: boolean;
  showLoose: boolean;
  focusId: number | null;
  /** Non-overlapping display marks, sorted; see lib/relevance.ts. */
  marks?: Mark[];
  showPageMatter?: boolean;
  /** 1-based grid column this pane occupies in the shared row grid. */
  col: number;
  onSelect: (s: Selected | null) => void;
  onAnnotationClick: (id: number) => void;
}

export default function TextPane({
  pane,
  paneName,
  title,
  prehighlights,
  annotations,
  showStrict,
  showLoose,
  focusId,
  marks,
  showPageMatter = false,
  col,
  onSelect,
  onAnnotationClick,
}: Props) {
  const rootRef = useRef<HTMLDivElement>(null);
  const [opened, setOpened] = useState<Set<number>>(new Set());
  const text = pane.text;
  const rgs = marks ?? [];
  // Length, not nullishness: translate_he.py writes BOTH keys and leaves the
  // inapplicable one as [], so `pane.pages ?? pane.segments` hands back the
  // empty array for an oral document and its translation never splits.
  const blocks = (pane.pages?.length ? pane.pages : pane.segments) ?? [];

  /**
   * One cell per page, tiling the whole pane text.
   *
   * Each cell runs to the *next* page's start rather than to its own `end`, so
   * the separators join_pages() puts between pages are carried along instead of
   * falling into a gap. Every character of the pane text lands in exactly one
   * cell — which is what keeps root.textContent equal to pane.text, and so
   * keeps every offset derived from a selection correct.
   */
  const cells = useMemo(() => {
    if (blocks.length < 2) return [{ start: 0, end: text.length }];
    const out: { start: number; end: number }[] = [];
    let cursor = 0;
    blocks.forEach((b, i) => {
      const next = i === blocks.length - 1 ? text.length : blocks[i + 1].start;
      const end = Math.min(text.length, Math.max(cursor, next));
      out.push({ start: cursor, end });
      cursor = end;
    });
    if (cursor < text.length) out[out.length - 1].end = text.length;
    return out;
  }, [blocks, text.length]);

  // Runs are computed before segmentation because their boundaries have to be
  // cut points: a segment straddling a run edge would belong to neither run
  // and would vanish from the DOM.
  const runsByCell = useMemo(
    () => cells.map((cell) => runsFor(cell)),
    [cells, rgs, text]
  );

  const { segments, spanMeta } = useMemo(() => {
    const spans: Span[] = [];
    const meta = new Map<string, { kind: 'ph' | 'anno'; ph?: Prehighlight; id?: number }>();
    for (const p of prehighlights) {
      if (p.pane !== paneName) continue;
      spans.push({ id: p.id, start: p.start, end: p.end });
      meta.set(p.id, { kind: 'ph', ph: p });
    }
    for (const a of annotations) {
      if (a.pane !== paneName || a.status === 'orphan') continue;
      const key = `anno-${a.id}`;
      spans.push({ id: key, start: a.start_offset, end: a.end_offset });
      meta.set(key, { kind: 'anno', id: a.id });
    }
    // Cell AND run boundaries are cuts, so every emitted segment lies wholly
    // inside one run and can be placed without being split again.
    const cuts = cells.map((c) => c.start);
    for (const runs of runsByCell) {
      for (const r of runs) cuts.push(r.start, r.end);
    }
    return { segments: segment(text.length, spans, cuts), spanMeta: meta };
  }, [text, prehighlights, annotations, paneName, cells, runsByCell]);

  /**
   * The runs to render inside one page cell.
   *
   * These MUST tile the cell exactly. Regions only span [page.start,
   * page.end), while a cell runs on to the next page's start so the separator
   * between pages is carried — and a blank page has no regions at all. Either
   * way the leftover characters belong to no region, and rendering only the
   * regions would drop them from the DOM and invalidate every offset after
   * them. So gaps are filled with `keep` rather than left out.
   */
  function runsFor(cell: { start: number; end: number }) {
    const blank = { level: 'keep' as const, what: '' };
    const inCell = rgs
      .filter((r) => r.end > cell.start && r.start < cell.end)
      .map((r) => ({
        ...r,
        start: Math.max(r.start, cell.start),
        end: Math.min(r.end, cell.end),
      }))
      .sort((a, b) => a.start - b.start);
    if (!inCell.length) return [{ ...blank, start: cell.start, end: cell.end }];

    const out: typeof inCell = [];
    let cursor = cell.start;
    for (const r of inCell) {
      if (r.start > cursor) out.push({ ...blank, start: cursor, end: r.start });
      if (r.end > cursor) {
        out.push({ ...r, start: Math.max(r.start, cursor) });
        cursor = r.end;
      }
    }
    if (cursor < cell.end) out.push({ ...blank, start: cursor, end: cell.end });

    /* Push each run's leading whitespace back into the run before it.
       Regions start at the blank line that separates them from the previous
       one, and white-space: pre-wrap renders that as two real empty lines. A
       folded run clipped to a couple of lines would then show nothing but
       those blanks — the block reads as a gap in the page rather than as
       greyed-out text. Runs left holding only whitespace disappear into their
       predecessor. Boundaries stay contiguous, so the cell still tiles. */
    const tidy: typeof out = [];
    for (const r of out) {
      let start = r.start;
      while (start < r.end && /\s/.test(text[start])) start++;
      if (start >= r.end) {
        if (tidy.length) tidy[tidy.length - 1].end = r.end;
        else tidy.push({ ...r });
        continue;
      }
      if (tidy.length) tidy[tidy.length - 1].end = start;
      else start = r.start;
      tidy.push({ ...r, start });
    }
    return tidy;
  }

  // If this ever fires, the rendered DOM is not character-identical to the pane
  // text and every offset derived from a selection is wrong.
  useEffect(() => {
    if (process.env.NODE_ENV !== 'production' && rootRef.current) {
      assertPaneIntegrity(rootRef.current, text);
    }
  }, [text, segments]);

  // Scroll to the annotation the rail has focused.
  useEffect(() => {
    if (focusId == null || !rootRef.current) return;
    const a = annotations.find((x) => x.id === focusId && x.pane === paneName);
    if (!a) return;
    const range = offsetsToRange(rootRef.current, a.start_offset, a.end_offset);
    const el = range?.startContainer.parentElement;
    el?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }, [focusId, annotations, paneName]);

  function handleMouseUp() {
    const sel = window.getSelection();
    const root = rootRef.current;
    if (!sel || sel.isCollapsed || sel.rangeCount === 0 || !root) {
      onSelect(null);
      return;
    }
    const range = sel.getRangeAt(0);
    const offsets = rangeToOffsets(root, range);
    if (!offsets) {
      onSelect(null);
      return;
    }
    const trimmed = trimRange(text, offsets.start, offsets.end);
    if (!trimmed) {
      onSelect(null);
      return;
    }
    // The anchor of record. If the slice does not equal what the browser says
    // is selected, the DOM and the text have diverged and we refuse rather
    // than storing a span that points somewhere else.
    const quote = text.slice(trimmed.start, trimmed.end);
    const rect = range.getBoundingClientRect();
    onSelect({
      pane: paneName,
      start: trimmed.start,
      end: trimmed.end,
      quote,
      x: rect.left + rect.width / 2 + window.scrollX,
      y: rect.bottom + window.scrollY + 6,
    });
  }

  function renderSegment(seg: (typeof segments)[number]) {
    const chunk = text.slice(seg.start, seg.end);
    if (!seg.ids.length) {
      return <span key={seg.start}>{chunk}</span>;
    }
    const metas = seg.ids.map((id) => spanMeta.get(id)!).filter(Boolean);
    const anno = metas.find((m) => m.kind === 'anno');
    const phs = metas.filter((m) => m.kind === 'ph').map((m) => m.ph!);
    const strict = phs.some((p) => p.strict);
    const loose = phs.some((p) => !p.strict);
    const cls = [
      anno ? 'hl-anno' : '',
      anno && anno.id === focusId ? 'focus' : '',
      strict ? 'hl-strict' : '',
      !strict && loose ? 'hl-loose' : '',
      strict && phs.some((p) => p.category === 'heimat') ? 'cat-heimat' : '',
    ]
      .filter(Boolean)
      .join(' ');
    const title = phs.length
      ? phs
          .map(
            (p) =>
              `${p.category}${p.source === 'claude' ? ' (Claude)' : ''}` +
              (p.rationale ? ` — ${p.rationale}` : '')
          )
          .join('\n')
      : undefined;
    return (
      <span
        key={seg.start}
        className={cls}
        title={title}
        onClick={anno ? () => onAnnotationClick(anno.id!) : undefined}
      >
        {chunk}
      </span>
    );
  }

  return (
    <>
      <div className="pane-title cell" data-col={col}
        style={{ '--col': col } as CSSProperties}>
        <span>{title}</span>
        <span style={{ opacity: 0.7 }}>
          {pane.lang.toUpperCase()} · {text.length.toLocaleString()} chars
        </span>
        {pane.model && <span style={{ opacity: 0.6 }}>{pane.model}</span>}
      </div>
      {/* display:contents — the cells below are the grid items, so a page lines
          up with the same page in the other columns. The root stays a single
          element whose textContent is the whole pane text, which is what
          lib/offsets.ts requires. */}
      <div
        ref={rootRef}
        className={`text-body${showStrict ? ' show-strict' : ''}${
          showLoose ? ' show-loose' : ''
        }`}
        dir={pane.dir}
        lang={pane.lang}
        data-pane-root={paneName}
        onMouseUp={handleMouseUp}
      >
        {cells.map((cell, i) => (
          <div
            key={cell.start}
            className="cell pageblock"
            data-col={col}
            style={{ '--col': col, '--row': i + 2 } as CSSProperties}
          >
            {runsByCell[i].map((run) => {
              const set = run.level !== 'keep';
              // `contextual` is a shading, not a fold: it says read this as
              // background, which you cannot do if it is rolled up.
              const foldable = set && run.level !== 'contextual';
              const open = showPageMatter || opened.has(run.start);
              return (
                <div
                  key={run.start}
                  className={`run${set ? ` run-${run.level}` : ''}${
                    foldable && !open ? ' folded' : ''
                  }${run.projected ? ' projected' : ''}`}
                  title={
                    set
                      ? `${run.what}${foldable && !open ? ' — click to open' : ''}`
                      : undefined
                  }
                  onClick={
                    foldable && !open
                      ? () => setOpened((p) => new Set(p).add(run.start))
                      : undefined
                  }
                >
                  {segments
                    .filter((s) => s.start >= run.start && s.end <= run.end)
                    .map(renderSegment)}
                </div>
              );
            })}
          </div>
        ))}
      </div>
      {blocks.length > 1 && (
        <div
          className="cell pane-foot"
          data-col={col}
          style={{ '--col': col, '--row': cells.length + 2 } as CSSProperties}
        >
          {pane.pages?.length
            ? `${blocks.length} pages · ${pane.pages[0].page_no}–${
                pane.pages[pane.pages.length - 1].page_no
              }`
            : `${blocks.length} speaker turns`}
        </div>
      )}
    </>
  );
}
