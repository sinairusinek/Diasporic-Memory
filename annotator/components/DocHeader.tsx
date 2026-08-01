import ReviewBox from '@/components/ReviewBox';
import type { CaseEntry, DocBundle } from '@/lib/types';

export default function DocHeader({
  doc,
  caseEntry,
  position,
  total,
  review,
}: {
  doc: DocBundle;
  caseEntry: CaseEntry | undefined;
  position: number;
  total: number;
  review: { verdict: string; note: string } | null;
}) {
  const m = doc.meta;
  const facts: [string, string][] = [
    ['Date', m.date_text],
    ['Type', m.doc_type.replace(/_/g, ' ')],
    ['Languages', m.languages.join(', ')],
    ['From', m.from_person],
    ['To', m.to_person],
    ['Places', m.places.slice(0, 6).join(' · ')],
    ['Folder', `${m.folder} ${m.page_range}`],
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
      </div>

      {m.heimat_rationale && <p className="rationale">{m.heimat_rationale}</p>}

      <ReviewBox docId={doc.doc_id} initial={review} />
    </header>
  );
}
