import ReviewBox from '@/components/ReviewBox';
import type { Archival, CaseEntry, DocBundle } from '@/lib/types';

export default function DocHeader({
  doc,
  caseEntry,
  archival,
  position,
  total,
  review,
}: {
  doc: DocBundle;
  caseEntry: CaseEntry | undefined;
  archival: Archival | undefined;
  position: number;
  total: number;
  review: { verdict: string; note: string } | null;
}) {
  const m = doc.meta;
  // The register's names are Hebrew; keep them in their own direction so they
  // do not reorder against the English archive name beside them.
  const heb = archival?.title_lang === 'he';
  const facts: [string, string][] = [
    ['Date', m.date_text],
    ['Type', m.doc_type.replace(/_/g, ' ')],
    ['Languages', m.languages.join(', ')],
    ['From', m.from_person],
    ['To', m.to_person],
    ['Places', m.places.slice(0, 6).join(' · ')],
    [
      'Folder',
      archival?.folder_id
        ? `${archival.folder_id}${m.page_range ? `, ${m.page_range}` : ''}`
        : `${m.folder} ${m.page_range}`,
    ],
  ];

  return (
    <header className="dochead">
      <div className="kicker">
        {doc.case_id}
        {caseEntry?.person ? ` · ${caseEntry.person}` : ''}
        {caseEntry?.city_region ? ` · ${caseEntry.city_region}` : ''}
        {' — '}
        {position} of {total}
      </div>

      {archival && (
        <div className="archline">
          <span className="arch">{archival.archive}</span>
          {archival.collection && (
            <>
              <span className="sep">›</span>
              <span
                className="coll"
                dir={heb ? 'rtl' : 'ltr'}
                lang={heb ? 'he' : undefined}
              >
                {archival.collection}
              </span>
            </>
          )}
          {archival.folder_title && (
            <>
              <span className="sep">›</span>
              <span
                className="ftitle"
                dir={heb ? 'rtl' : 'ltr'}
                lang={heb ? 'he' : undefined}
              >
                {archival.folder_title}
              </span>
            </>
          )}
          {archival.folder_id && (
            <span className="ref" title={archival.folder_ref}>
              {archival.folder_id}
            </span>
          )}
        </div>
      )}

      <h2>{m.title}</h2>

      {doc.summary_he ? (
        <div className="summary-he" dir="rtl" lang="he">
          {doc.summary_he}
        </div>
      ) : doc.summary_en ? (
        <div className="summary-he" dir="ltr" lang="en">
          {doc.summary_en}
        </div>
      ) : null}

      <div className="facts">
        {facts
          .filter(([, v]) => v)
          .map(([k, v]) => (
            <span key={k}>
              <b>{k}</b>
              {v}
            </span>
          ))}
        {m.full_text_url && (
          <span>
            <b>Full text</b>
            <a href={m.full_text_url} target="_blank" rel="noreferrer">
              open in Drive ↗
            </a>
          </span>
        )}
      </div>

      {m.heimat_rationale && <p className="rationale">{m.heimat_rationale}</p>}

      <ReviewBox docId={doc.doc_id} initial={review} />
    </header>
  );
}
