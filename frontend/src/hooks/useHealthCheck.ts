import { useQuery } from '@tanstack/react-query'

import { getHealth } from '@/services/healthService'

export function useHealthCheck() {
  return useQuery({
    queryKey: ['health'],
    queryFn: getHealth,
  })
}
