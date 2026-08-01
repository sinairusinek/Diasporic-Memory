-- Annotations made by the PI. One row per span-plus-body.
--
-- Offsets alone are not a durable anchor: regenerating a Hebrew translation
-- shifts every offset in that pane. So each row also carries the W3C quote
-- selector (prefix/quote/suffix) and the hash of the pane text it was made
-- against. On load, a hash mismatch triggers relocation by quote; see
-- lib/relocate.ts. `quote` is the anchor of record, not `start_offset`.

create table if not exists annotation (
  id            bigserial primary key,
  doc_id        text        not null,
  pane          text        not null check (pane in ('source', 'translation')),
  kind          text        not null check (kind in ('comment', 'tag', 'keywords')),
  start_offset  int         not null check (start_offset >= 0),
  end_offset    int         not null check (end_offset > start_offset),
  quote         text        not null,
  prefix        text        not null default '',
  suffix        text        not null default '',
  pane_sha256   char(64)    not null,
  body          jsonb       not null,
  status        text        not null default 'ok'
                            check (status in ('ok', 'relocated', 'orphan')),
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

create index if not exists annotation_doc_idx
  on annotation (doc_id, pane, start_offset);
create index if not exists annotation_body_idx
  on annotation using gin (body jsonb_path_ops);

-- The PI's verdict on the machine relevance call, one row per document.
-- Kept separate from `annotation` because it is document-level, not a span.
create table if not exists doc_review (
  doc_id      text primary key,
  verdict     text not null check (verdict in ('relevant', 'not-relevant', 'unsure')),
  note        text not null default '',
  updated_at  timestamptz not null default now()
);
