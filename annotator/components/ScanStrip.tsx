'use client';

import { useState } from 'react';
import type { PageBlock } from '@/lib/types';

/**
 * Page facsimiles, served through /api/scan so the session gate applies.
 * The strip is the only way to check a suspicious OCR reading against the
 * actual page without leaving the tool, which matters most exactly where the
 * transcription is graded `poor`.
 */
export default function ScanStrip({
  docId,
  pages,
}: {
  docId: string;
  pages: PageBlock[];
}) {
  const [open, setOpen] = useState<number | null>(null);
  const withScans = pages.filter((p) => p.scan_url);
  if (!withScans.length) return null;

  return (
    <section style={{ padding: '4px 26px 0' }}>
      <div className="pane-title">
        Facsimile · {withScans.length} pages
        <span style={{ opacity: 0.7 }}>click to enlarge</span>
      </div>
      <div className="scanstrip">
        {withScans.map((p) => (
          <figure key={p.page_no} className={p.grade === 'poor' ? 'hit' : undefined}>
            <img
              src={`/api/scan/${encodeURIComponent(docId)}/${p.page_no}`}
              alt={`page ${p.page_no}`}
              loading="lazy"
              onClick={() => setOpen(p.page_no)}
            />
            <figcaption>
              {p.page_no}
              {p.grade === 'poor' && ' ⚠'}
            </figcaption>
          </figure>
        ))}
      </div>

      {open !== null && (
        <div
          onClick={() => setOpen(null)}
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(20,16,10,0.86)',
            zIndex: 200,
            display: 'grid',
            placeItems: 'center',
            padding: 20,
            cursor: 'zoom-out',
          }}
        >
          <img
            src={`/api/scan/${encodeURIComponent(docId)}/${open}`}
            alt={`page ${open}`}
            style={{ maxWidth: '100%', maxHeight: '100%', background: '#fff' }}
          />
        </div>
      )}
    </section>
  );
}
