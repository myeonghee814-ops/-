import type { PaperDetail, SearchResponse } from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `Request failed with status ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export async function searchPapers(keyword: string): Promise<SearchResponse> {
  const res = await fetch(`${API_BASE_URL}/api/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ keyword }),
  });
  return handleResponse<SearchResponse>(res);
}

export async function getSearch(searchId: string): Promise<SearchResponse> {
  const res = await fetch(`${API_BASE_URL}/api/search/${searchId}`);
  return handleResponse<SearchResponse>(res);
}

export async function getPaperDetail(resultId: string): Promise<PaperDetail> {
  const res = await fetch(`${API_BASE_URL}/api/results/${resultId}`);
  return handleResponse<PaperDetail>(res);
}
