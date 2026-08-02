'use client';

import { useEffect, useRef, useState } from 'react';
import TagPicker from './TagPicker';
import type {
  AnnotationBody,
  AnnotationKind,
  Relevance,
  TagVocab,
} from '@/lib/types';
import type { Selected } from './TextPane';

const MODES: { kind: AnnotationKind; label: string }[] = [
  { kind: 'comment', label: 'Comment' },
  { kind: 'tag', label: 'Tag' },
  { kind: 'keywords', label: 'Keywords' },
  { kind: 'relevance', label: 'Relevance' },
];

const LEVELS: { value: Relevance; label: string; hint: string }[] = [
  {
    value: 'irrelevant',
    label: 'Irrelevant',
    hint: 'Not this document. Folds to a single line here and in the other language.',
  },
  {
    value: 'contextual',
    label: 'Contextual',
    hint: 'Background rather than evidence. Stays open, set in a lighter grey.',
  },
];

export default function AnnotationPopover({
  selection,
  vocab,
  onSave,
  onClose,
}: {
  selection: Selected;
  vocab: TagVocab;
  onSave: (kind: AnnotationKind, body: AnnotationBody) => Promise<string | null>;
  onClose: () => void;
}) {
  const [mode, setMode] = useState<AnnotationKind>('comment');
  const [comment, setComment] = useState('');
  const [tag, setTag] = useState<string | null>(null);
  const [keywords, setKeywords] = useState('');
  const [relevance, setRelevance] = useState<Relevance | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
    }
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  function body(): AnnotationBody | null {
    if (mode === 'comment') return comment.trim() ? { text: comment.trim() } : null;
    if (mode === 'tag') return tag ? { tag } : null;
    if (mode === 'relevance') return relevance ? { relevance } : null;
    const kws = keywords
      .split(/[,;\n]/)
      .map((k) => k.trim())
      .filter(Boolean);
    return kws.length ? { keywords: kws } : null;
  }

  async function save() {
    const b = body();
    if (!b) {
      setError(
        mode === 'tag'
          ? 'Pick a tag first.'
          : mode === 'relevance'
            ? 'Pick irrelevant or contextual.'
            : 'Nothing to save yet.'
      );
      return;
    }
    setBusy(true);
    setError('');
    const err = await onSave(mode, b);
    setBusy(false);
    if (err) setError(err);
    else onClose();
  }

  // Keep the popover on screen when the selection is near the right edge.
  const left = Math.max(12, Math.min(selection.x - 165, window.innerWidth - 350));

  return (
    <div className="popover" ref={ref} style={{ left, top: selection.y }}>
      <div className="quote" dir="auto">
        {selection.quote.length > 260
          ? `${selection.quote.slice(0, 260)}…`
          : selection.quote}
      </div>

      <div className="modes">
        {MODES.map((m) => (
          <button
            key={m.kind}
            type="button"
            aria-pressed={mode === m.kind}
            onClick={() => {
              setMode(m.kind);
              setError('');
            }}
          >
            {m.label}
          </button>
        ))}
      </div>

      {mode === 'comment' && (
        <textarea
          autoFocus
          dir="auto"
          value={comment}
          placeholder="הערה חופשית / free comment…"
          onChange={(e) => setComment(e.target.value)}
        />
      )}

      {mode === 'tag' && (
        <TagPicker vocab={vocab} value={tag} onChange={setTag} />
      )}

      {mode === 'relevance' && (
        <div className="levels">
          {LEVELS.map((l) => (
            <button
              key={l.value}
              type="button"
              className={`level level-${l.value}`}
              aria-pressed={relevance === l.value}
              title={l.hint}
              onClick={() => {
                setRelevance(l.value);
                setError('');
              }}
            >
              <b>{l.label}</b>
              <span>{l.hint}</span>
            </button>
          ))}
        </div>
      )}

      {mode === 'keywords' && (
        <input
          type="text"
          autoFocus
          dir="auto"
          value={keywords}
          placeholder="comma-separated: Wiesbaden, Rathaus, 1959…"
          onChange={(e) => setKeywords(e.target.value)}
        />
      )}

      <div className="actions">
        <button type="button" onClick={onClose}>
          Cancel
        </button>
        <button type="button" className="primary" onClick={save} disabled={busy}>
          {busy ? 'Saving…' : 'Save'}
        </button>
      </div>
      {error && <div className="err">{error}</div>}
    </div>
  );
}
