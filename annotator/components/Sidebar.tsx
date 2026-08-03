'use client';

import Link from 'next/link';
import { useLayoutEffect, useRef } from 'react';
import type { CorpusIndex } from '@/lib/types';

export default function Sidebar({
  index,
  activeDocId,
  counts,
}: {
  index: CorpusIndex;
  activeDocId: string;
  counts: Record<string, number>;
}) {
  const navRef = useRef<HTMLElement>(null);

  // Every document click is a full navigation, so the list comes back scrolled
  // to the top and the reader loses their place. Put the active row back in
  // the middle of the list — scroll the nav itself, not scrollIntoView, which
  // would also drag the page when the sidebar is stacked above the document.
  useLayoutEffect(() => {
    const nav = navRef.current;
    const el = nav?.querySelector<HTMLElement>('.doc-link.active');
    if (!nav || !el) return;
    const navRect = nav.getBoundingClientRect();
    const elRect = el.getBoundingClientRect();
    nav.scrollTop += elRect.top - navRect.top - (nav.clientHeight - elRect.height) / 2;
  }, [activeDocId]);

  const byId = new Map(index.docs.map((d) => [d.doc_id, d]));
  const annotated = index.docs.filter((d) => counts[d.doc_id]).length;

  // A case is one person's papers and in practice sits in a single folder, so
  // the archival line belongs to the case head rather than repeating on every
  // document. Where a case ever does straddle folders, say so instead of
  // silently showing the first one as if it covered all of them.
  const archivalFor = (docIds: string[]) => {
    const found = docIds
      .map((id) => byId.get(id)?.archival)
      .filter((a): a is NonNullable<typeof a> => Boolean(a));
    if (!found.length) return null;
    const uniform = found.every((a) => a.folder_id === found[0].folder_id);
    return uniform ? found[0] : { ...found[0], folder_title: '', folder_id: '' };
  };

  return (
    <nav className="sidebar" ref={navRef}>
      <h1>
        <Link href="/" className="allcases">
          ← Post-war visits
        </Link>
        <small>
          {index.docs.length} sources · {index.cases.length} cases ·{' '}
          {annotated} annotated
        </small>
      </h1>

      {index.cases.map((c) => {
        const a = archivalFor(c.doc_ids);
        const heb = a?.title_lang === 'he';
        return (
        <div className="case-group" key={c.case_id}>
          <div className="case-head">
            <strong>
              {c.person || c.case_id}
              {c.city_region ? ` · ${c.city_region}` : ''}
            </strong>
            {c.case_id} {c.year && `· ${c.year}`}{' '}
            {c.kind === 'oral' && <span className="badge oral">oral</span>}
            {a && (
              <span className="case-arch">
                <span className="arch">{a.archive_short}</span>
                {a.collection && (
                  <span dir={heb ? 'rtl' : 'ltr'} lang={heb ? 'he' : undefined}>
                    {a.collection}
                  </span>
                )}
                {a.folder_title && (
                  <span
                    className="ftitle"
                    dir={heb ? 'rtl' : 'ltr'}
                    lang={heb ? 'he' : undefined}
                  >
                    {a.folder_title}
                  </span>
                )}
                {a.folder_id && <span className="ref">{a.folder_id}</span>}
              </span>
            )}
          </div>
          {c.doc_ids.map((id) => {
            const d = byId.get(id);
            if (!d) return null;
            const n = counts[id] ?? 0;
            const poor = d.grades?.poor ?? 0;
            return (
              <Link
                key={id}
                href={`/doc/${id}`}
                className={`doc-link${id === activeDocId ? ' active' : ''}`}
              >
                {d.title || id}
                <span className="row2">
                  {d.date_text && <span>{d.date_text}</span>}
                  <span>{d.page_range}</span>
                  {d.n_strict > 0 && <span>{d.n_strict} signals</span>}
                  {poor > 0 && <span className="badge poor">{poor} unreadable</span>}
                  {n > 0 && <span className="badge count">{n}</span>}
                </span>
              </Link>
            );
          })}
        </div>
        );
      })}
    </nav>
  );
}
