import { useMutation } from '@tanstack/react-query'

import { analyzePaper } from '@/services/analysisService'

// Single-paper counterpart to useAnalyzePapers (search results) and
// useComparePapers -- used by the paper detail page's "Analyze This Paper" action.
export function useAnalyzePaper() {
  return useMutation({
    mutationFn: analyzePaper,
  })
}
