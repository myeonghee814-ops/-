const STORAGE_KEY = "blip_gemini_api_key";

export function getApiKey(): string {
  return localStorage.getItem(STORAGE_KEY) ?? "";
}

export function setApiKey(key: string): void {
  const trimmed = key.trim();
  if (trimmed) {
    localStorage.setItem(STORAGE_KEY, trimmed);
  } else {
    localStorage.removeItem(STORAGE_KEY);
  }
}

export function clearApiKey(): void {
  localStorage.removeItem(STORAGE_KEY);
}
