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
  performance_summary: string;
  innovation: string;
  advantages: string;
  limitations: string;
  abstract: string;
  keyword: string;
}

export interface SearchResponse {
  search_id: number;
  keyword: string;
  expanded_query: string;
  results: PaperCard[];
  ai_degraded: boolean;
}
