// Mirrors the JSON written by code/annotator/*.py. Keep the two in step: the
// Python side is authoritative, this is the reader's view of the same contract.

export type PaneName = 'source' | 'translation';
export type AnnotationKind = 'comment' | 'tag' | 'keywords';
export type Grade = 'clean' | 'mixed' | 'poor';

/** A page of a written document, in the pane's flat offset space. */
export interface PageBlock {
  page_no: number;
  start: number;
  end: number;
  scan_file: string | null;
  scan_url: string | null;
  /** Which engine's transcription won this page. */
  ocr_engine: 'tesseract' | 'transkribus';
  /** null for Transkribus HTR, which reports no per-page confidence. */
  ocr_conf: number | null;
  needs_escalation: boolean;
  grade: Grade;
  signals: { wordfrac: number; shortline: number; tokens: number };
  translatable: boolean;
}

/** A speaker turn of an oral testimony, in the same flat offset space. */
export interface SegmentBlock {
  n: number;
  speaker: string;
  speaker_name: string;
  start_sec: number | null;
  start: number;
  end: number;
}

export interface Pane {
  pane: PaneName;
  lang: string;
  dir: 'ltr' | 'rtl';
  text: string;
  sha256: string;
  pages?: PageBlock[];
  segments?: SegmentBlock[];
  model?: string;
  generated_at?: string;
}

export interface Prehighlight {
  id: string;
  pane: PaneName;
  start: number;
  end: number;
  quote: string;
  source: 'keyword' | 'claude';
  category: string;
  match: string;
  strict: boolean;
  confidence: number;
  rationale: string;
}

export interface DocMeta {
  title: string;
  date_text: string;
  doc_type: string;
  languages: string[];
  from_person: string;
  to_person: string;
  places: string[];
  persons: string[];
  heimat_rationale: string;
  notes: string;
  folder: string;
  page_range: string;
  is_heimat_relevant: string;
  event_id?: string;
  signal_categories?: string[];
  restricted?: string;
}

export interface DocBundle {
  doc_id: string;
  catalog_doc_id: string;
  case_id: string;
  kind: 'written' | 'oral';
  public: boolean;
  meta: DocMeta;
  summary_he: string;
  summary_de: string;
  summary_en: string;
  panes: { source: Pane; translation: Pane | null };
  prehighlights: Prehighlight[];
  built_at: string;
}

export interface Tag {
  id: string;
  label: string;
  description: string;
  facet?: string;
  group?: string;
}

export interface TagVocab {
  facets: {
    id: string;
    name: string;
    title: string;
    cardinality: 'one' | 'zero-or-one';
    hint_he: string;
    tags: Tag[];
  }[];
  themes: { id: string; title: string; tags: Tag[] }[];
  index: Record<string, Tag>;
  source: string;
}

export interface CaseEntry {
  case_id: string;
  person: string;
  city_region: string;
  year: string;
  category: string;
  evidence: string;
  drive_url: string;
  kind: 'written' | 'oral';
  doc_ids: string[];
}

export interface DocEntry {
  doc_id: string;
  case_id: string;
  kind: 'written' | 'oral';
  public: boolean;
  title: string;
  date_text: string;
  doc_type: string;
  languages: string[];
  folder: string;
  page_range: string;
  chars: number;
  blocks: number;
  has_translation: boolean;
  n_prehighlights: number;
  n_strict: number;
  grades: Partial<Record<Grade, number>>;
}

export interface CorpusIndex {
  built_at: string;
  tags: TagVocab;
  cases: CaseEntry[];
  docs: DocEntry[];
}

export type AnnotationBody =
  | { text: string }
  | { tag: string }
  | { keywords: string[] };

export interface Annotation {
  id: number;
  doc_id: string;
  pane: PaneName;
  kind: AnnotationKind;
  start_offset: number;
  end_offset: number;
  quote: string;
  prefix: string;
  suffix: string;
  pane_sha256: string;
  body: AnnotationBody;
  status: 'ok' | 'relocated' | 'orphan';
  created_at: string;
  updated_at: string;
}
