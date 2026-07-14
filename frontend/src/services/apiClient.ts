import axios from 'axios'

// Falls back to a relative path so the Vite dev-server proxy (see
// vite.config.ts) handles requests without needing VITE_API_BASE_URL set.
export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
})
