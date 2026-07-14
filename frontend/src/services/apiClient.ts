import axios from 'axios'

// Falls back to relative paths so the Vite dev-server proxy (see
// vite.config.ts) handles requests without needing the env vars set.
//
// Two clients because the backend intentionally mounts most resources
// under the versioned /api/v1 prefix but literature search unversioned at
// /api/search (see backend/main.py and docs/ARCHITECTURE.md).
export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
})

export const apiRootClient = axios.create({
  baseURL: import.meta.env.VITE_API_ROOT_URL || '/api',
})
