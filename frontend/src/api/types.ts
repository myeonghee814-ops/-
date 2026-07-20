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
  battery_snapshot: BatterySnapshot;
}

export interface PaperDetail extends PaperCard {
  experimental_conditions: string;
  result_summary: string;
  abstract: string;
  keyword: string;
}

export type SortBy = "relevance" | "recency";
export type MaterialNoticeLevel = "info" | "warning";

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
  material_notice_level: MaterialNoticeLevel | null;
  performance: string;
  additive_or_solvent: string;
  sort_by: SortBy;
  expanded_query: string;
  results: PaperCard[];
  ai_degraded: boolean;
}
