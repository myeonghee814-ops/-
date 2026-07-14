import { isAxiosError } from 'axios'

// Backend errors are FastAPI's standard {"detail": "..."} shape. Falls back
// to the raw Error message, then a generic string, so every mutation error
// handler in the app can display something reasonable with one call.
export function getErrorMessage(error: unknown, fallback: string): string {
  if (isAxiosError(error)) {
    const detail = error.response?.data?.detail
    if (typeof detail === 'string') return detail
  }
  if (error instanceof Error && error.message) return error.message
  return fallback
}
