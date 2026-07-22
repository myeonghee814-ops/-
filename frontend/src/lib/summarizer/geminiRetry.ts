/**
 * Shared retry-with-backoff primitives for Gemini calls, used by both
 * gemini.ts's generateStructured (text/JSON calls: summarize, research
 * suggestions, trend insight) and figureFinder.ts's own multimodal call
 * (which used to have NO retry at all). Mirrors the BLIP backend's
 * ai_service.py approach (_retry_delay_seconds/_MAX_RETRIES_BY_STATUS):
 * 429 (quota) gets only 1 retry since a short wait rarely clears it, 503
 * (transient overload) gets more since it can clear at any moment - and
 * both prefer the server's own suggested wait time over a guessed one.
 */

/** 429 (quota) is retried once at most - if the free-tier quota is
 * exhausted, a second retry within the same short window won't help
 * either. 503 (transient "high demand") gets more retries since it can
 * clear at any moment. 500 is treated like a lightweight version of 503. */
export const MAX_RETRIES_BY_STATUS: Record<number, number> = { 429: 1, 500: 1, 503: 3 };

/** Gemini's daily quota errors have been observed asking for ~45-60s;
 * a naive short exponential backoff would give up long before that. */
export const MIN_RETRY_DELAY_MS = 30_000;

/** Determine how long to wait before retrying a 429/503 Gemini response.
 * Prefers the server-provided delay (Retry-After header - forwarded by
 * proxy-server/index.mjs - or the RetryInfo/message text in Gemini's own
 * error body) over a fixed backoff. Falls back to MIN_RETRY_DELAY_MS. */
export function retryDelayMs(res: Response, bodyText: string): number {
  const retryAfter = res.headers.get("retry-after");
  if (retryAfter) {
    const seconds = parseFloat(retryAfter);
    if (!Number.isNaN(seconds)) return Math.max(seconds * 1000, MIN_RETRY_DELAY_MS);
  }

  try {
    const error = (JSON.parse(bodyText) as { error?: { details?: unknown[]; message?: string } }).error ?? {};

    for (const detail of error.details ?? []) {
      const d = detail as { "@type"?: string; retryDelay?: string };
      if (d["@type"]?.endsWith("RetryInfo") && d.retryDelay) {
        const match = d.retryDelay.match(/([\d.]+)s?/);
        if (match) return Math.max(parseFloat(match[1]) * 1000, MIN_RETRY_DELAY_MS);
      }
    }

    const match = error.message?.match(/retry in ([\d.]+)s/i);
    if (match) return Math.max(parseFloat(match[1]) * 1000, MIN_RETRY_DELAY_MS);
  } catch {
    // Body wasn't the expected JSON shape - fall through to the default.
  }

  return MIN_RETRY_DELAY_MS;
}

/** Gemini's *daily* free-tier quota exhaustion (quotaId containing
 * "PerDay") can't be fixed by waiting out a short retry window within the
 * same request - unlike a per-minute quota hit, retrying won't help until
 * the next reset. Detected so callers can skip straight to a clear
 * "come back tomorrow" message instead of burning retries on it. */
export function isDailyQuotaExhausted(bodyText: string): boolean {
  try {
    const error = (
      JSON.parse(bodyText) as { error?: { details?: { violations?: { quotaId?: string }[] }[] } }
    ).error;
    const quotaId = error?.details
      ?.flatMap((d) => d.violations ?? [])
      .map((v) => v.quotaId)
      .find((id): id is string => typeof id === "string");
    return !!quotaId && /perday/i.test(quotaId);
  } catch {
    return false;
  }
}
