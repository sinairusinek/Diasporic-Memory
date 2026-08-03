'use client';

// The landing view: the corpus as it is thought about — return-visit cases,
// each holding its documents — read by summary. The pages themselves (scan,
// source, translation) only appear once a document is chosen, in the reading
// view to the right of the case list.

import Link from 'next/link';
import { useEffect, useState } from 'react';
import type { CorpusIndex } from '@/lib/types';

type Lang = 'he' | 'en';
const LANG_KEY = 'catalogue-lang';

export default function Catalogue({
  index,
  counts,
}: {
  index: CorpusIndex;
  counts: Record<string, number>;
}) {
  // Hebrew is the PI's working language; English is the fallback wherever a
  // Hebrew summary was never written (the oral corpus).
  const [lang, setLang] = useState<Lang>('he');
  useEffect(() => {
    const saved = window.localStorage.getItem(LANG_KEY);
    if (saved === 'he' || saved === 'en') setLang(saved);
  }, []);
  const switchLang = (l: Lang) => {
    setLang(l);
    window.localStorage.setItem(LANG_KEY, l);
  };

  const byId = new Map(index.docs.map((d) => [d.doc_id, d]));
  const annotated = index.docs.filter((d) => counts[d.doc_id]).length;

  // Same rule as the reading view's sidebar: the archival trail belongs to the
  // case, unless its documents genuinely straddle folders.
  const archivalFor = (docIds: string[]) => {
    const found = docIds
      .map((id) => byId.get(id)?.archival)
      .filter((a): a is NonNullable<typeof a> => Boolean(a));
    if (!found.length) return null;
    const uniform = found.every((a) => a.folder_id === found[0].folder_id);
    return uniform ? found[0] : { ...found[0], folder_title: '', folder_id: '' };
  };

  // A summary in the asked-for language, or the English one, and which of the
  // two it turned out to be — the direction and font follow the text, not the
  // toggle.
  const pick = (he: string, en: string) =>
    lang === 'he' && he.trim()
      ? { text: he, hebrew: true }
      : { text: en, hebrew: false };

  return (
    <main className="catalog">
      <header className="catalog-head">
        <div>
          <h1>Post-war visits to Germany</h1>
          <p className="catalog-sub">
            {index.cases.length} cases · {index.docs.length} documents ·{' '}
            {annotated} annotated
          </p>
        </div>
        <div className="lang-toggle" role="group" aria-label="Summary language">
          {(['he', 'en'] as Lang[]).map((l) => (
            <button
              key={l}
              type="button"
              aria-pressed={lang === l}
              onClick={() => switchLang(l)}
            >
              {l === 'he' ? 'עברית' : 'English'}
            </button>
          ))}
        </div>
      </header>

      {index.cases.map((c) => {
        const a = archivalFor(c.doc_ids);
        const heb = a?.title_lang === 'he';
        const cs = pick(c.summary_he, c.summary_en);
        return (
          <section className="case-card" key={c.case_id}>
            <header>
              <div className="case-title">
                <strong>{c.person || c.case_id}</strong>
                {c.city_region && <span>· {c.city_region}</span>}
                {c.year && <span>· {c.year}</span>}
                {c.kind === 'oral' && <span className="badge oral">oral</span>}
                <span className="case-id">{c.case_id}</span>
              </div>
              {a && (
                <div className="archline">
                  <span className="arch">{a.archive_short}</span>
                  {a.collection && (
                    <>
                      <span className="sep">›</span>
                      <span dir={heb ? 'rtl' : 'ltr'} lang={heb ? 'he' : undefined}>
                        {a.collection}
                      </span>
                    </>
                  )}
                  {a.folder_title && (
                    <>
                      <span className="sep">›</span>
                      <span
                        className="ftitle"
                        dir={heb ? 'rtl' : 'ltr'}
                        lang={heb ? 'he' : undefined}
                      >
                        {a.folder_title}
                      </span>
                    </>
                  )}
                  {a.folder_id && <span className="ref">{a.folder_id}</span>}
                </div>
              )}
              {cs.text && (
                <p
                  className="case-summary"
                  dir={cs.hebrew ? 'rtl' : 'ltr'}
                  lang={cs.hebrew ? 'he' : 'en'}
                >
                  {cs.text}
                </p>
              )}
            </header>

            {c.doc_ids.map((id) => {
              const d = byId.get(id);
              if (!d) return null;
              const n = counts[id] ?? 0;
              const poor = d.grades?.poor ?? 0;
              const ds = pick(d.summary_he, d.summary_en);
              return (
                <Link key={id} href={`/doc/${id}`} className="cat-doc">
                  <span className="cat-doc-title">{d.title || id}</span>
                  <span className="cat-doc-meta">
                    {d.date_text && <span>{d.date_text}</span>}
                    <span>{d.doc_type.replace(/_/g, ' ')}</span>
                    {d.page_range && <span>pp. {d.page_range}</span>}
                    {d.n_strict > 0 && <span>{d.n_strict} signals</span>}
                    {poor > 0 && (
                      <span className="badge poor">{poor} unreadable</span>
                    )}
                    {n > 0 && <span className="badge count">{n}</span>}
                  </span>
                  {ds.text && (
                    <span
                      className="cat-doc-summary"
                      dir={ds.hebrew ? 'rtl' : 'ltr'}
                      lang={ds.hebrew ? 'he' : 'en'}
                    >
                      {ds.text}
                    </span>
                  )}
                </Link>
              );
            })}
          </section>
        );
      })}
    </main>
  );
}
