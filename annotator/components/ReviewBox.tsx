'use client';

import { useState } from 'react';

/**
 * The PI's verdict on the whole document, as opposed to a span.
 *
 * Selecting text is the wrong instrument for "this document is not what the
 * pipeline thought it was" — there is no passage to point at, and that
 * judgement is itself a finding (see app/api/review/route.ts). The note is
 * saved with the verdict rather than separately, because a bare
 * `not-relevant` a year from now is not reconstructable.
 */
const VERDICTS: { value: Verdict; label: string }[] = [
  { value: 'relevant', label: 'Relevant' },
  { value: 'not-relevant', label: 'Not relevant' },
  { value: 'unsure', label: 'Unsure' },
];

type Verdict = 'relevant' | 'not-relevant' | 'unsure';

export default function ReviewBox({
  docId,
  initial,
}: {
  docId: string;
  initial: { verdict: string; note: string } | null;
}) {
  const [verdict, setVerdict] = useState<Verdict | null>(
    (initial?.verdict as Verdict) ?? null
  );
  const [note, setNote] = useState(initial?.note ?? '');
  const [saved, setSaved] = useState(Boolean(initial));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  // The note alone is not a verdict, so there is nothing to save until one is
  // picked; picking one saves immediately, since that is the common case and
  // an unsaved radio button is a trap.
  async function save(nextVerdict: Verdict, nextNote: string) {
    setBusy(true);
    setError('');
    try {
      const res = await fetch('/api/review', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ docId, verdict: nextVerdict, note: nextNote }),
      });
      if (!res.ok) {
        const { error: msg } = await res.json().catch(() => ({}));
        setError(msg ?? 'could not save');
        return;
      }
      setSaved(true);
    } catch {
      setError('could not save — check your connection');
    } finally {
      setBusy(false);
    }
  }

  function pick(v: Verdict) {
    setVerdict(v);
    setSaved(false);
    void save(v, note);
  }

  return (
    <div className="review">
      <span className="review-label">This document:</span>

      <div className="review-verdicts">
        {VERDICTS.map((v) => (
          <button
            key={v.value}
            type="button"
            disabled={busy}
            aria-pressed={verdict === v.value}
            onClick={() => pick(v.value)}
          >
            {v.label}
          </button>
        ))}
      </div>

      <input
        type="text"
        className="review-note"
        placeholder="Why? (optional)"
        value={note}
        disabled={busy || !verdict}
        onChange={(e) => {
          setNote(e.target.value);
          setSaved(false);
        }}
        // Saved on blur rather than per keystroke: one row per document, and a
        // write per character would be noise.
        onBlur={() => verdict && !saved && void save(verdict, note)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') e.currentTarget.blur();
        }}
      />

      <span className="review-state">
        {error ? (
          <b className="bad">{error}</b>
        ) : busy ? (
          'saving…'
        ) : saved ? (
          'saved'
        ) : verdict ? (
          'unsaved'
        ) : (
          ''
        )}
      </span>
    </div>
  );
}
