"""Thin client for the Semantic Scholar Graph API.

Owns everything specific to this provider — endpoint, request params, and
response parsing — so the service layer never needs to know its shape.
Any failure (network, HTTP status, unexpected payload) is normalized into
SemanticScholarError for the caller to handle.
"""

import httpx

from core.config import get_settings
from core.http_clients import get_http_client
from schemas.search import PaperResult
from services.external.exceptions import SemanticScholarError

_BASE_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
_FIELDS = "title,authors,venue,year,citationCount,externalIds,abstract,openAccessPdf,publicationDate"


async def search(keyword: str, year_from: int | None, year_to: int | None, limit: int) -> list[PaperResult]:
    """Search Semantic Scholar and return normalized results.

    Raises SemanticScholarError on any request failure or unexpected response
    shape, so search_service can fall back to OpenAlex.
    """
    settings = get_settings()
    params: dict[str, str | int] = {"query": keyword, "limit": limit, "fields": _FIELDS}
    if year_from or year_to:
        params["year"] = _year_range(year_from, year_to)

    headers = {"x-api-key": settings.SEMANTIC_SCHOLAR_API_KEY} if settings.SEMANTIC_SCHOLAR_API_KEY else {}

    try:
        client = get_http_client()
        response = await client.get(_BASE_URL, params=params, headers=headers)
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPError as exc:
        raise SemanticScholarError(f"Semantic Scholar request failed: {exc}") from exc

    try:
        return [_to_paper_result(item) for item in payload.get("data", [])]
    except (KeyError, TypeError, ValueError) as exc:
        raise SemanticScholarError(f"Unexpected Semantic Scholar response shape: {exc}") from exc


def _year_range(year_from: int | None, year_to: int | None) -> str:
    """Semantic Scholar's `year` filter accepts "YYYY-YYYY", "YYYY-", or "-YYYY"."""
    if year_from and year_to:
        return f"{year_from}-{year_to}"
    if year_from:
        return f"{year_from}-"
    return f"-{year_to}"


def _to_paper_result(item: dict) -> PaperResult:
    external_ids = item.get("externalIds") or {}
    open_access_pdf = item.get("openAccessPdf") or {}

    return PaperResult(
        title=item.get("title") or "",
        authors=[author.get("name", "") for author in item.get("authors") or []],
        journal=item.get("venue") or None,
        year=item.get("year"),
        citation_count=item.get("citationCount"),
        doi=external_ids.get("DOI"),
        abstract=item.get("abstract"),
        pdf_url=open_access_pdf.get("url"),
        published_date=item.get("publicationDate"),
        source="semantic_scholar",
    )
