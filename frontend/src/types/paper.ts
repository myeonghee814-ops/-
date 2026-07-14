// Mirrors backend/schemas/paper.py::PaperRead. Placeholder shape for the
// future paper search/organization features — not wired to a page yet.
export interface Paper {
  id: number
  title: string
  authors: string
  abstract: string
  doi: string | null
  source: string
  url: string | null
}
