'use client';

import { useMemo, useState } from 'react';
import type { TagVocab } from '@/lib/types';

/**
 * The whole scheme in one searchable list — F1-F4 facets and T1-T7 themes,
 * ~65 tags. The facets carry their cardinality from the scheme markdown; the
 * UI shows it but does not enforce it, because one span legitimately gets one
 * facet tag per annotation row and the PI may add several rows to a span.
 */
export default function TagPicker({
  vocab,
  value,
  onChange,
}: {
  vocab: TagVocab;
  value: string | null;
  onChange: (tagId: string) => void;
}) {
  const [q, setQ] = useState('');

  const groups = useMemo(() => {
    const all = [
      ...vocab.facets.map((f) => ({
        key: f.id,
        title: `${f.id} · ${f.title} (${f.cardinality === 'one' ? 'exactly one' : 'optional'})`,
        tags: f.tags,
      })),
      ...vocab.themes.map((t) => ({
        key: t.id,
        title: `${t.id} · ${t.title}`,
        tags: t.tags,
      })),
    ];
    const needle = q.trim().toLowerCase();
    if (!needle) return all;
    return all
      .map((g) => ({
        ...g,
        tags: g.tags.filter(
          (t) =>
            t.id.toLowerCase().includes(needle) ||
            t.label.toLowerCase().includes(needle) ||
            t.description.toLowerCase().includes(needle)
        ),
      }))
      .filter((g) => g.tags.length);
  }, [vocab, q]);

  return (
    <div>
      <input
        type="text"
        value={q}
        autoFocus
        placeholder="Search tags — heimat, refusal, protocol…"
        onChange={(e) => setQ(e.target.value)}
        style={{ marginBottom: 6 }}
      />
      <div className="tagpicker">
        {groups.map((g) => (
          <div key={g.key}>
            <div className="grp">{g.title}</div>
            {g.tags.map((t) => (
              <button
                key={t.id}
                type="button"
                className={`opt${value === t.id ? ' sel' : ''}`}
                onClick={() => onChange(t.id)}
              >
                <b>{t.id}</b> {t.label}
                {t.description && <span className="d">{t.description}</span>}
              </button>
            ))}
          </div>
        ))}
        {!groups.length && (
          <div style={{ padding: 10, fontSize: 12, color: 'var(--ink-muted)' }}>
            no tag matches “{q}”
          </div>
        )}
      </div>
    </div>
  );
}
