import { useMutation } from '@tanstack/react-query'

import { exportPapers } from '@/services/exportService'

// Triggers a browser download on success rather than exposing the blob to
// the caller — exporting is a fire-and-forget action, not data a component
// needs to render.
export function useExportPapers() {
  return useMutation({
    mutationFn: exportPapers,
    onSuccess: ({ blob, filename }) => {
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = filename
      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(url)
    },
  })
}
