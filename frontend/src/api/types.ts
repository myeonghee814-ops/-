export interface BatterySnapshot {
  cathode: string;
  anode: string;
  electrolyte: string;
  voltage_window: string;
  cell_type: string;
}

export interface PaperCard {
  result_id: number;
  rank: number;
  relevance_score: number;
  why_selected: string;
  title: string;
  authors: string;
  journal: string;
  year: number | null;
  doi: string;
  external_paper_id: string;
  open_access_pdf_url: string;
  battery_snapshot: BatterySnapshot;
}

export interface DeepAnalysis {
  base_electrolyte: string;
  test_electrolyte: string;
  voltage_range: string;
  cell_type_detail: string;
  key_findings: string;
  summary: string;
}

export interface PaperDetail extends PaperCard {
  experimental_conditions: string;
  result_summary: string;
  abstract: string;
  keyword: string;
  deep_analysis: DeepAnalysis | null;
}

export type SortBy = "relevance" | "recency";
export type NoticeLevel = "info" | "warning";

export interface SearchRequest {
  material: string;
  performance: string;
  additive_or_solvent: string;
  sort_by: SortBy;
}

export interface SearchResponse {
  search_id: number;
  keyword: string;
  material: string;
  material_notice: string;
  material_notice_level: NoticeLevel | null;
  performance: string;
  additive_or_solvent: string;
  additive_notice: string;
  additive_notice_level: NoticeLevel | null;
  sort_by: SortBy;
  expanded_query: string;
  results: PaperCard[];
  ai_degraded: boolean;
}
