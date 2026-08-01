'use client';

import { useCallback, useEffect, useState } from 'react';
import AnnotationPopover from './AnnotationPopover';
import AnnotationList from './AnnotationList';
import ScanStrip from './ScanStrip';
import TextPane, { type Selected } from './TextPane';
import type {
  Annotation,
  AnnotationBody,
  AnnotationKind,
  DocBundle,
  TagVocab,
} from '@/lib/types';

type ViewMode = 'both' | 'source' | 'translation';

export default function Workspace({
  doc,
  vocab,
  prevId,
  nextId,
}: {
  doc: DocBundle;
  vocab: TagVocab;
  prevId: string | null;
  nextId: string | null;
}) {
  const [annotations, setAnnotations] = useState<Annotation[]>([]);
  const [selection, setSelection] = useState<Selected | null>(null);
  const [focusId, setFocusId] = useState<number | null>(null);
  const [view, setView] = useState<ViewMode>(
    doc.panes.translation ? 'both' : 'source'
  );
  // Strict lexical signals are on; the loose co-occurrence tier is off, because
  // over-highlighting silently biases the reading and under-highlighting does
  // not — the PI can always select an unmarked passage herself.
  const [showStrict, setShowStrict] = useState(true);
  const [showLoose, setShowLoose] = useState(false);
  const [notice, setNotice] = useState('');

  const load = useCallback(async () => {
    const res = await fetch(`/api/annotations?docId=${encodeURIComponent(doc.doc_id)}`);
    if (!res.ok) return;
    const data = await res.json();
    setAnnotations(data.annotations);
    if (data.orphaned || data.relocated) {
      setNotice(
        [
          data.relocated ? `${data.relocated} annotation(s) re-anchored` : '',
          data.orphaned ? `${data.orphaned} could not be re-anchored` : '',
        ]
          .filter(Boolean)
          .join(' · ')
      );
    } else {
      setNotice('');
    }
  }, [doc.doc_id]);

  useEffect(() => {
    setAnnotations([]);
    setSelection(null);
    setFocusId(null);
    load();
  }, [load]);

  const save = useCallback(
    async (kind: AnnotationKind, body: AnnotationBody): Promise<string | null> => {
      if (!selection) return 'nothing selected';
      const res = await fetch('/api/annotations', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          docId: doc.doc_id,
          pane: selection.pane,
          kind,
          start: selection.start,
          end: selection.end,
          quote: selection.quote,
          body,
        }),
      });
      if (!res.ok) {
        const { error } = await res.json().catch(() => ({ error: 'save failed' }));
        return error ?? 'save failed';
      }
      const { annotation } = await res.json();
      setAnnotations((prev) =>
        [...prev, annotation].sort(
          (a, b) => a.pane.localeCompare(b.pane) || a.start_offset - b.start_offset
        )
      );
      window.getSelection()?.removeAllRanges();
      return null;
    },
    [doc.doc_id, selection]
  );

  const remove = useCallback(async (id: number) => {
    const res = await fetch(`/api/annotations/${id}`, { method: 'DELETE' });
    if (res.ok) setAnnotations((prev) => prev.filter((a) => a.id !== id));
  }, []);

  // Left/right move through the corpus; the PI works source by source.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const t = e.target as HTMLElement | null;
      if (t && /input|textarea/i.test(t.tagName)) return;
      if (e.key === 'ArrowRight' && nextId) window.location.href = `/doc/${nextId}`;
      if (e.key === 'ArrowLeft' && prevId) window.location.href = `/doc/${prevId}`;
    }
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [prevId, nextId]);

  const source = doc.panes.source;
  const translation = doc.panes.translation;
  const pages = source.pages ?? [];
  const poor = pages.filter((p) => p.grade === 'poor');
  const mixed = pages.filter((p) => p.grade === 'mixed');
  const showBoth = view === 'both' && translation;

  return (
    <>
      {!doc.public && (
        <div className="warn restricted">
          <b>Restricted source.</b> Israelkorpus (Betten) transcript excerpt,
          DGD-licensed. Usable for this analysis; not for public display or
          redistribution.
        </div>
      )}

      {poor.length > 0 && (
        <div className="warn">
          <b>
            {poor.length} of {pages.length} pages are not reliably transcribed
          </b>{' '}
          (page{poor.length > 1 ? 's' : ''}{' '}
          {poor.map((p) => p.page_no).join(', ')}). Tesseract fails on German
          cursive, and dense press montages come back with the columns shredded.
          These pages are excluded from the Hebrew translation — read them
          against the scan, and do not annotate on the transcription.
          {mixed.length > 0 && (
            <>
              {' '}
              A further {mixed.length} page{mixed.length > 1 ? 's are' : ' is'}{' '}
              partly garbled.
            </>
          )}
        </div>
      )}

      {!translation && (
        <div className="warn">
          No Hebrew translation has been generated for this document yet. Run{' '}
          <code>python code/annotator/translate_he.py --docs {doc.doc_id}</code>.
        </div>
      )}

      {notice && <div className="warn">{notice}</div>}

      <div className="toolbar">
        <label>
          <input
            type="checkbox"
            checked={showStrict}
            onChange={(e) => setShowStrict(e.target.checked)}
          />
          Explicit signals ({doc.prehighlights.filter((p) => p.strict).length})
        </label>
        <label title="Loose co-occurrence: 'Deutschland' near a travel verb. Noisy by design.">
          <input
            type="checkbox"
            checked={showLoose}
            onChange={(e) => setShowLoose(e.target.checked)}
          />
          Possible signals ({doc.prehighlights.filter((p) => !p.strict).length})
        </label>

        <span className="spacer" />

        {translation && (
          <>
            {(['both', 'source', 'translation'] as ViewMode[]).map((v) => (
              <button
                key={v}
                type="button"
                aria-pressed={view === v}
                onClick={() => setView(v)}
                style={
                  view === v
                    ? { background: 'var(--accent)', color: '#fff', borderColor: 'var(--accent)' }
                    : undefined
                }
              >
                {v === 'both' ? 'Both' : v === 'source' ? 'Source' : 'עברית'}
              </button>
            ))}
          </>
        )}
        <button type="button" disabled={!prevId} onClick={() => prevId && (window.location.href = `/doc/${prevId}`)}>
          ← Previous
        </button>
        <button type="button" disabled={!nextId} onClick={() => nextId && (window.location.href = `/doc/${nextId}`)}>
          Next →
        </button>
      </div>

      <div className={`panes${showBoth ? '' : ' single'}`}>
        {view !== 'translation' && (
          <TextPane
            pane={source}
            paneName="source"
            title="Source"
            prehighlights={doc.prehighlights}
            annotations={annotations}
            showStrict={showStrict}
            showLoose={showLoose}
            focusId={focusId}
            onSelect={setSelection}
            onAnnotationClick={setFocusId}
          />
        )}
        {translation && view !== 'source' && (
          <TextPane
            pane={translation}
            paneName="translation"
            title="תרגום לעברית"
            prehighlights={doc.prehighlights}
            annotations={annotations}
            showStrict={showStrict}
            showLoose={showLoose}
            focusId={focusId}
            onSelect={setSelection}
            onAnnotationClick={setFocusId}
          />
        )}
      </div>

      {pages.length > 0 && <ScanStrip docId={doc.doc_id} pages={pages} />}

      <AnnotationList
        annotations={annotations}
        vocab={vocab}
        focusId={focusId}
        onFocus={setFocusId}
        onDelete={remove}
      />

      {selection && (
        <AnnotationPopover
          selection={selection}
          vocab={vocab}
          onSave={save}
          onClose={() => setSelection(null)}
        />
      )}
    </>
  );
}
