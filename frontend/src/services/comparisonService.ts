import { apiClient } from '@/services/apiClient'
import type { PaperAnalysis } from '@/types/analysis'
import type { ComparisonResult } from '@/types/comparison'

export async function comparePapers(analyses: PaperAnalysis[]): Promise<ComparisonResult> {
  const { data } = await apiClient.post<ComparisonResult>('/compare', { analyses })
  return data
}
