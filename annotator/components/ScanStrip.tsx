'use client';

import { useState } from 'react';
import type { PageBlock } from '@/lib/types';

/**
 * Page facsimiles as the leftmost column, beside the source and the
 * translation rather than under them.
 *
 * Checking a suspicious OCR reading against the page is the common move, not
 * the exceptional one — most of all where the transcription is graded `poor` —
 * so the image should be in view while reading, not a scroll away. Click to
 * enlarge.
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

  const i = open === null ? -1 : withScans.findIndex((p) => p.page_no === open);
  const step = (d: number) => {
    const next = withScans[i + d];
    if (next) setOpen(next.page_no);
  };

  return (
    <section className="pane scans">
      <div className="pane-title">
        Facsimile
        <span style={{ opacity: 0.7 }}>{withScans.length} pages</span>
      </div>

      <div className="scancol">
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
          className="lightbox"
          onClick={() => setOpen(null)}
          role="dialog"
          aria-label={`page ${open}`}
        >
          {/* Paging inside the lightbox: comparing consecutive pages of one
              letter is the point, and closing to reopen loses the zoom. */}
          <button
            type="button"
            className="lb-nav prev"
            disabled={i <= 0}
            onClick={(e) => {
              e.stopPropagation();
              step(-1);
            }}
          >
            ‹
          </button>
          <img
            src={`/api/scan/${encodeURIComponent(docId)}/${open}`}
            alt={`page ${open}`}
            onClick={(e) => e.stopPropagation()}
          />
          <button
            type="button"
            className="lb-nav next"
            disabled={i < 0 || i >= withScans.length - 1}
            onClick={(e) => {
              e.stopPropagation();
              step(1);
            }}
          >
            ›
          </button>
        </div>
      )}
    </section>
  );
}
