// Mirrors backend/schemas/search.py.
export interface PaperResult {
  title: string
  authors: string[]
  journal: string | null
  year: number | null
  citation_count: number | null
  doi: string | null
  abstract: string | null
  pdf_url: string | null
  published_date: string | null
  source: string
}

export interface SearchQuery {
  keyword: string
  year_from: number | null
  year_to: number | null
  limit: number
}

export interface SearchResponse {
  query: SearchQuery
  source: string
  count: number
  results: PaperResult[]
}

export interface SearchParams {
  keyword: string
  yearFrom?: number
  yearTo?: number
  limit: number
}
