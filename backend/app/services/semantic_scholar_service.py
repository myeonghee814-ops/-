"""Literature search against Semantic Scholar's public Graph API.

Replaces an earlier PubMed-based implementation: PubMed is a biomedical/
life-science database and does not meaningfully index most battery and
materials-science journals (Journal of Power Sources, Advanced Energy
Materials, Joule, Nature Energy, etc.), so it systematically under-covers
exactly the papers a battery researcher needs. Semantic Scholar aggregates
across those publishers in addition to biomedical literature, and exposes
a free, official search API (an optional API key just raises the shared
rate limit - no key is required to use it).

This is the first stage of the pipeline: cast a reasonably wide net
(``candidate_count`` candidates) so the AI re-ranking stage in
``ai_service`` has enough material to do real comparative ranking instead
of just re-sorting a top-10.
"""

import asyncio
from dataclasses import dataclass

import httpx

from app.core.config import settings

SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
FIELDS = "title,abstract,venue,year,authors,externalIds"

# Without an API key, requests share Semantic Scholar's public rate-limit
# pool and get 429s whenever other users are also querying it - unlike
# Gemini's daily quota, this window clears in seconds, so a short
# exponential backoff (not Gemini's ~30s minimum) is enough to ride it out.
_MAX_RETRIES = 3
_BASE_RETRY_DELAY_SECONDS = 1.0


def _retry_delay_seconds(resp: httpx.Response, attempt: int) -> float:
    """How long to wait before retrying a 429. Prefers the server's
    Retry-After header when present, exponential backoff otherwise."""

    retry_after = resp.headers.get("retry-after")
    if retry_after:
        try:
            return max(float(retry_after), _BASE_RETRY_DELAY_SECONDS)
        except ValueError:
            pass
    return _BASE_RETRY_DELAY_SECONDS * (2**attempt)


@dataclass
class Candidate:
    paper_id: str
    title: str
    authors: str
    journal: str
    year: int | None
    doi: str
    abstract: str


def _extract_doi(external_ids: dict | None) -> str:
    if not external_ids:
        return ""
    return external_ids.get("DOI") or ""


async def search_candidates(query: str, max_results: int | None = None) -> list[Candidate]:
    """Search Semantic Scholar and return bibliographic candidates for a query."""

    max_results = max_results or settings.candidate_count
    params = {
        "query": query,
        "limit": min(max_results, 100),
        "fields": FIELDS,
    }
    headers = {"x-api-key": settings.semantic_scholar_api_key} if settings.semantic_scholar_api_key else {}

    attempt = 0
    async with httpx.AsyncClient() as client:
        while True:
            resp = await client.get(SEARCH_URL, params=params, headers=headers, timeout=30)
            if resp.status_code == 429 and attempt < _MAX_RETRIES:
                await asyncio.sleep(_retry_delay_seconds(resp, attempt))
                attempt += 1
                continue
            resp.raise_for_status()
            data = resp.json()
            break

    candidates: list[Candidate] = []
    for item in data.get("data", []):
        title = (item.get("title") or "").strip()
        if not title:
            continue
        authors = ", ".join(a.get("name", "") for a in item.get("authors") or [] if a.get("name"))
        candidates.append(
            Candidate(
                paper_id=item.get("paperId", ""),
                title=title,
                authors=authors,
                journal=item.get("venue") or "",
                year=item.get("year"),
                doi=_extract_doi(item.get("externalIds")),
                abstract=(item.get("abstract") or "").strip(),
            )
        )
    return candidates
