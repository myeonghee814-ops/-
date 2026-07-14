// Mirrors backend/schemas/analysis.py.
export interface AnalyzeRequest {
  title: string
  abstract?: string
  pdf_text?: string
}

export interface PaperAnalysis {
  title: string | null
  authors: string[]
  journal: string | null
  battery_system: string | null
  electrolyte: string | null
  salt: string | null
  solvent: string | null
  additive: string | null
  cathode: string | null
  anode: string | null
  separator: string | null
  cell_type: string | null
  voltage_window: string | null
  temperature: string | null
  formation_protocol: string | null
  cycle_condition: string | null
  rate_capability: string | null
  main_findings: string[]
  innovation: string | null
  advantages: string[]
  limitations: string[]
  future_work: string[]
}
