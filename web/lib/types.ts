export interface KnowledgeSpace {
  id: string;
  name: string;
  description: string;
  language: string;
  created_at: string;
  updated_at: string;
}

export interface RecentQuery {
  id: string;
  question: string;
  confidence: number;
  created_at: string;
}

export interface DashboardSummary {
  document_count: number;
  chunk_count: number;
  trace_count: number;
  eval_run_count: number;
  recent_queries: RecentQuery[];
}

export interface DocumentListItem {
  id: string;
  title: string;
  source_type: string;
  status: string;
  chunk_count: number;
  created_at: string;
}

export interface DocumentListResponse {
  items: DocumentListItem[];
}

export interface ChunkRead {
  id: string;
  fragment_id: string;
  section_title: string;
  heading_path: string[];
  page_number: number | null;
  start_offset: number;
  end_offset: number;
  token_count: number;
  content: string;
}

export interface DocumentRead {
  id: string;
  knowledge_space_id: string;
  title: string;
  source_type: string;
  source_uri: string;
  storage_uri: string | null;
  visibility_scope: string;
  source_acl_refs: string[];
  connector_id: string | null;
  ingestion_job_id: string | null;
  status: string;
  checksum: string | null;
  source_metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  chunks: ChunkRead[];
}

export interface FragmentRead {
  document_id: string;
  fragment_id: string;
  section_title: string;
  heading_path: string[];
  page_number: number | null;
  content: string;
}

export interface Citation {
  citation_id: string;
  document_id: string;
  document_title: string;
  fragment_id: string;
  section_title: string;
  heading_path: string[];
  page_number: number | null;
  quote: string;
  score: number;
}

export interface SourceDocument {
  document_id: string;
  title: string;
  score: number;
}

export interface AnswerResponse {
  answer_trace_id: string;
  answer: string;
  citations: Citation[];
  confidence: number;
  source_documents: SourceDocument[];
  followup_queries: string[];
}

export interface AnswerTrace {
  id: string;
  knowledge_space_id: string;
  question: string;
  answer: string;
  confidence: number;
  citations: Citation[];
  source_documents: SourceDocument[];
  followup_queries: string[];
  created_at: string;
}

export interface SourceImportResponse {
  ingestion_job: {
    id: string;
    knowledge_space_id: string;
    job_kind: string;
    source_uri: string;
    workflow_id: string | null;
    status: string;
    attempt_count: number;
    error_message: string | null;
    imported_document_id: string | null;
    created_at: string;
    updated_at: string;
  };
  document: {
    id: string;
    title: string;
    chunks: Array<{ id: string }>;
  } | null;
}

export interface FeedbackResponse {
  id: string;
  answer_trace_id: string;
  rating: number;
  issue_type: string | null;
  comments: string | null;
  created_at: string;
}

export interface EvalCaseResult {
  name: string;
  question: string;
  returned_document_ids: string[];
  hit: boolean;
  confidence: number;
}

export interface EvalRunResponse {
  id: string;
  knowledge_space_id: string;
  workflow_id: string | null;
  status: string;
  attempt_count: number;
  error_message: string | null;
  total_cases: number;
  completed_cases: number;
  summary: {
    document_recall?: number;
    citation_precision?: number;
    avg_confidence?: number;
    error_message?: string;
  };
  created_at: string;
  completed_at: string | null;
  results: EvalCaseResult[];
}
