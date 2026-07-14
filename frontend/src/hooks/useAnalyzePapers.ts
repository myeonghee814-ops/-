import { useMutation } from '@tanstack/react-query'

import { analyzePapers } from '@/services/analysisService'

// Batch-analyzes a set of papers (e.g. the current search results) so
// AI-derived columns can be filled in on demand rather than automatically
// on every search, which would make search slow and expensive.
export function useAnalyzePapers() {
  return useMutation({
    mutationFn: analyzePapers,
  })
}
