'use client';

import { useEffect, useMemo, useRef } from 'react';
import { assertPaneIntegrity, offsetsToRange, rangeToOffsets } from '@/lib/offsets';
import { segment, trimRange, type Span } from '@/lib/segments';
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
  onSelect,
  onAnnotationClick,
}: Props) {
  const rootRef = useRef<HTMLDivElement>(null);
  const text = pane.text;

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
    return { segments: segment(text.length, spans), spanMeta: meta };
  }, [text, prehighlights, annotations, paneName]);

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

  const blocks = pane.pages ?? pane.segments ?? [];

  return (
    <div className="pane">
      <div className="pane-title">
        <span>{title}</span>
        <span style={{ opacity: 0.7 }}>
          {pane.lang.toUpperCase()} · {text.length.toLocaleString()} chars
        </span>
        {pane.model && <span style={{ opacity: 0.6 }}>{pane.model}</span>}
      </div>
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
        {segments.map((seg) => {
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
        })}
      </div>
      {blocks.length > 1 && (
        <div style={{ marginTop: 12, fontSize: 11.5, color: 'var(--ink-muted)' }}>
          {pane.pages
            ? `${blocks.length} pages · ${pane.pages[0].page_no}–${
                pane.pages[pane.pages.length - 1].page_no
              }`
            : `${blocks.length} speaker turns`}
        </div>
      )}
    </div>
  );
}
