import Link from 'next/link';
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
  const byId = new Map(index.docs.map((d) => [d.doc_id, d]));
  const annotated = index.docs.filter((d) => counts[d.doc_id]).length;

  return (
    <nav className="sidebar">
      <h1>
        Post-war visits
        <small>
          {index.docs.length} sources · {index.cases.length} cases ·{' '}
          {annotated} annotated
        </small>
      </h1>

      {index.cases.map((c) => (
        <div className="case-group" key={c.case_id}>
          <div className="case-head">
            <strong>
              {c.person || c.case_id}
              {c.city_region ? ` · ${c.city_region}` : ''}
            </strong>
            {c.case_id} {c.year && `· ${c.year}`}{' '}
            {c.kind === 'oral' && <span className="badge oral">oral</span>}
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
      ))}
    </nav>
  );
}
