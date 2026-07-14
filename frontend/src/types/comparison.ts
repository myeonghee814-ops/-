import type { PaperAnalysis } from '@/types/analysis'

// Mirrors backend/schemas/comparison.py.
export interface ComparisonRequest {
  analyses: PaperAnalysis[]
}

export interface ComparisonTableRow {
  title: string | null
  electrolyte: string | null
  salt: string | null
  additive: string | null
  cathode: string | null
  anode: string | null
  separator: string | null
  cell_type: string | null
  voltage_window: string | null
  temperature: string | null
  cycle_condition: string | null
  main_finding: string | null
  advantages: string | null
  limitations: string | null
}

export interface ComparisonResult {
  paper_count: number
  common_experimental_conditions: string[]
  differences: string[]
  frequently_used_electrolytes: string[]
  frequently_used_additives: string[]
  most_common_cathode: string | null
  most_common_anode: string | null
  research_trend: string | null
  research_gap: string | null
  potential_future_direction: string | null
  comparison_table: ComparisonTableRow[]
}
