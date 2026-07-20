import type { PaperDetail, SearchRequest, SearchResponse } from "./types";
import { mockGetPaperDetail, mockGetSearch, mockSearchPapers } from "./mockData";
import { getApiKey } from "../lib/apiKey";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

// Offline UI-preview mode (no backend/API key needed) - only ever true in a
// build made with `VITE_MOCK_API=true npm run build`. The real app (dev or
// packaged) always talks to the real backend.
const MOCK_API = import.meta.env.VITE_MOCK_API === "true";

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `요청이 실패했습니다. (상태 코드: ${res.status})`);
  }
  return res.json() as Promise<T>;
}

export async function searchPapers(request: SearchRequest): Promise<SearchResponse> {
  if (MOCK_API) return mockSearchPapers(request);

  const apiKey = getApiKey();
  const res = await fetch(`${API_BASE_URL}/api/search`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(apiKey ? { "X-Gemini-Api-Key": apiKey } : {}),
    },
    body: JSON.stringify(request),
  });
  return handleResponse<SearchResponse>(res);
}

export async function getSearch(searchId: string): Promise<SearchResponse> {
  if (MOCK_API) return mockGetSearch(searchId);

  const res = await fetch(`${API_BASE_URL}/api/search/${searchId}`);
  return handleResponse<SearchResponse>(res);
}

export async function getPaperDetail(resultId: string): Promise<PaperDetail> {
  if (MOCK_API) return mockGetPaperDetail(resultId);

  const res = await fetch(`${API_BASE_URL}/api/results/${resultId}`);
  return handleResponse<PaperDetail>(res);
}
