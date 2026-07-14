import { useQuery } from '@tanstack/react-query'

import { searchPapers } from '@/services/searchService'
import type { SearchParams } from '@/types/paper'

// `query` is null until the user submits the search form, so nothing is
// fetched on page load or on every keystroke.
export function useSearchPapers(query: SearchParams | null) {
  return useQuery({
    queryKey: ['search', query],
    queryFn: () => searchPapers(query as SearchParams),
    enabled: query !== null,
    staleTime: 5 * 60 * 1000,
  })
}
