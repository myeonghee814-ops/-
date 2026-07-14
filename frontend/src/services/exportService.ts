import { apiClient } from '@/services/apiClient'
import type { PaperResult } from '@/types/paper'

const DEFAULT_FILENAME = 'blip-papers-export.xlsx'

export interface ExportResult {
  blob: Blob
  filename: string
}

export async function exportPapers(papers: PaperResult[]): Promise<ExportResult> {
  const response = await apiClient.post('/export', { papers }, { responseType: 'blob' })
  return {
    blob: response.data as Blob,
    filename: extractFilename(response.headers['content-disposition']) ?? DEFAULT_FILENAME,
  }
}

function extractFilename(contentDisposition: unknown): string | null {
  if (typeof contentDisposition !== 'string') return null
  return /filename="?([^"]+)"?/.exec(contentDisposition)?.[1] ?? null
}
