import { useMutation } from '@tanstack/react-query'

import { analyzePapers } from '@/services/analysisService'
import { comparePapers } from '@/services/comparisonService'
import type { PaperAnalysis } from '@/types/analysis'
import type { ComparisonResult } from '@/types/comparison'
import type { PaperResult } from '@/types/paper'

export interface CompareFlowResult {
  papers: PaperResult[]
  analyses: PaperAnalysis[]
  comparison: ComparisonResult
}

// The full "Compare Selected" flow: analyze every selected paper (client-side,
// concurrent, tolerating individual failures -- see analysisService.ts),
// keep only the papers that succeeded, then run the comparison engine over
// those. No new backend endpoints needed -- this just orchestrates the
// existing /analyze and /compare endpoints from the browser.
export function useComparePapers() {
  return useMutation({
    mutationFn: async (papers: PaperResult[]): Promise<CompareFlowResult> => {
      const analysisResults = await analyzePapers(papers)

      const succeeded = papers
        .map((paper, index) => ({ paper, analysis: analysisResults[index] }))
        .filter((pair): pair is { paper: PaperResult; analysis: PaperAnalysis } => pair.analysis !== null)

      if (succeeded.length === 0) {
        throw new Error('None of the selected papers could be analyzed (check they have an abstract).')
      }

      const comparison = await comparePapers(succeeded.map((pair) => pair.analysis))

      return {
        papers: succeeded.map((pair) => pair.paper),
        analyses: succeeded.map((pair) => pair.analysis),
        comparison,
      }
    },
  })
}
