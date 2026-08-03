'use client';

import type { Annotation, Relevance, TagVocab } from '@/lib/types';

const RELEVANCE_LABEL: Record<Relevance, string> = {
  irrelevant: 'Marked irrelevant — folded away',
  contextual: 'Marked contextual — kept, but not the subject',
};

/**
 * One line of prose for whatever the body turns out to be.
 *
 * Every kind is named explicitly and the fallthrough returns a string. An
 * earlier version let anything that was not a comment or a tag fall through to
 * `.keywords.join()`, so the first relevance mark ever saved read `undefined`
 * off its body and took the whole page down with it.
 */
function describe(a: Annotation, vocab: TagVocab): string {
  if (a.kind === 'comment') return (a.body as { text: string }).text ?? '';
  if (a.kind === 'tag') {
    const id = (a.body as { tag: string }).tag;
    const t = vocab.index[id];
    return t ? `${id} — ${t.label}` : id;
  }
  if (a.kind === 'relevance') {
    const level = (a.body as { relevance: Relevance }).relevance;
    return RELEVANCE_LABEL[level] ?? level ?? '';
  }
  const kws = (a.body as { keywords?: string[] }).keywords;
  return Array.isArray(kws) ? kws.join(' · ') : '';
}

export default function AnnotationList({
  annotations,
  vocab,
  focusId,
  onFocus,
  onDelete,
}: {
  annotations: Annotation[];
  vocab: TagVocab;
  focusId: number | null;
  onFocus: (id: number) => void;
  onDelete: (id: number) => void;
}) {
  if (!annotations.length) {
    return (
      <section className="rail">
        <h3>Annotations</h3>
        <p style={{ fontSize: 13, color: 'var(--ink-muted)', margin: 0 }}>
          Select a word or passage in either pane to add a comment, a tag from
          the scheme, or keywords.
        </p>
      </section>
    );
  }

  return (
    <section className="rail">
      <h3>Annotations ({annotations.length})</h3>
      {annotations.map((a) => (
        <div
          key={a.id}
          className={`anno${a.status === 'orphan' ? ' orphan' : ''}`}
          onClick={() => onFocus(a.id)}
          style={focusId === a.id ? { borderInlineStartColor: 'var(--accent)' } : undefined}
        >
          <button
            className="del"
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onDelete(a.id);
            }}
          >
            delete
          </button>
          <div className="q" dir="auto">
            “{a.quote.length > 160 ? `${a.quote.slice(0, 160)}…` : a.quote}”
          </div>
          <div className="body" dir="auto">
            {describe(a, vocab)}
          </div>
          <div className="meta">
            <span>{a.kind}</span>
            <span>{a.pane === 'source' ? 'source' : 'תרגום'}</span>
            <span>
              {a.start_offset}–{a.end_offset}
            </span>
            {a.status === 'relocated' && <span>re-anchored after a rebuild</span>}
            {a.status === 'orphan' && (
              <span style={{ color: 'var(--accent)' }}>
                text changed — this quote is no longer in the document
              </span>
            )}
          </div>
        </div>
      ))}
    </section>
  );
}
