import { apiRootClient } from '@/services/apiClient'
import type { SearchParams, SearchResponse } from '@/types/paper'

export async function searchPapers(params: SearchParams): Promise<SearchResponse> {
  const { data } = await apiRootClient.get<SearchResponse>('/search', {
    params: {
      keyword: params.keyword,
      year_from: params.yearFrom,
      year_to: params.yearTo,
      limit: params.limit,
    },
  })
  return data
}
