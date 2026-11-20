export const entityTypes = ['Person', 'Case', 'Crime', 'Location', 'Vehicle', 'Organisation', 'Evidence', 'PoliceStation', 'OffenceSection', 'TimeWindow'] as const;
export type EntityType = typeof entityTypes[number];

export interface Citation {
  doc_id: string;
  fir_number: string;
  page_number: number;
  line_start: number;
  line_end: number;
  verbatim_quote: string;
}

export interface Entity {
  id: string;
  type: EntityType;
  name: string;
  properties: Record<string, string | string[]>;
  sources: Citation[];
}
export interface Relation { id: string; source: string; target: string; type: string; citation: Citation; confidence: number }
export interface Graph { nodes: Entity[]; edges: Relation[] }
export interface Status {
  storage: string;
  database: string | null;
  reason: string;
  embedding_model: string;
  llm_configured: boolean;
  total_nodes: number;
  total_documents: number;
  cross_case_links: number;
  pending_reviews: number;
}
export interface RecordDocument {
  doc_id: string;
  fir_number: string;
  file_name: string;
  file_hash_sha256: string;
  document_type: string;
  police_station: string;
  pages: string[][];
  demo: boolean;
}
export interface Candidate {
  id: string; name: string; score: number; reasons: string[]; cases: string[]; stations: string[];
}
export interface ChatTurn { question: string; result: SearchResult }
export interface SearchResult {
  resolution?: 'answer' | 'clarify' | 'confirm';
  pending_question?: string;
  person_id?: string;
  candidates?: Candidate[];
  answer: string;
  citations: Citation[];
  matched_subgraph: Graph;
  cypher_executed: string | null;
  top_k_chunks: (Citation & { chunk_id: string; text: string; score: number; cosine?: number | null })[];
  graph_mode: string;
}
export interface Review {
  review_id: string;
  entity_type: EntityType;
  source_entity: Entity;
  target_entity: Entity;
  confidence_score: number;
  match_rationale: string;
  status: 'PENDING' | 'APPROVED' | 'REJECTED';
}
export interface UploadResult {
  doc_id: string;
  fir_number: string;
  case_id: string | null;
  nodes_extracted: number;
  edges_extracted: number;
  cross_case_links_found: number;
  hitl_flagged: number;
  duplicate: boolean;
}
export interface Job { status: 'running' | 'complete' | 'failed'; stage: string; result?: UploadResult; error?: string }
