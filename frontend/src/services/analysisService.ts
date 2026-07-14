import { apiClient } from '@/services/apiClient'
import type { AnalyzeRequest, PaperAnalysis } from '@/types/analysis'
import type { PaperResult } from '@/types/paper'

export async function analyzePaper(request: AnalyzeRequest): Promise<PaperAnalysis> {
  const { data } = await apiClient.post<PaperAnalysis>('/analyze', request)
  return data
}

// Analyzes many papers concurrently, tolerating individual failures (no
// abstract available, a transient provider error) rather than letting one
// bad paper fail the whole batch. Mirrors what
// backend/services/export_service.py::_analyze_all already does
// server-side, but client-side for features that render analyses directly
// in the browser (search results, paper comparison) instead of only
// inside a server-generated file.
export async function analyzePapers(papers: PaperResult[]): Promise<(PaperAnalysis | null)[]> {
  const settled = await Promise.allSettled(
    papers.map((paper) => {
      if (!paper.abstract) return Promise.reject(new Error('No abstract available'))
      return analyzePaper({ title: paper.title, abstract: paper.abstract })
    }),
  )
  return settled.map((result) => (result.status === 'fulfilled' ? result.value : null))
}
