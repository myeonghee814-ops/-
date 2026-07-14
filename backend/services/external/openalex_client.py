"""Thin client for the OpenAlex Works API.

Used as the automatic fallback when Semantic Scholar is unavailable. Like
its sibling client, this module owns all OpenAlex-specific request/response
handling and only ever raises OpenAlexError.
"""

import httpx

from core.config import get_settings
from schemas.search import PaperResult
from services.external.exceptions import OpenAlexError

_BASE_URL = "https://api.openalex.org/works"


async def search(keyword: str, year_from: int | None, year_to: int | None, limit: int) -> list[PaperResult]:
    """Search OpenAlex and return normalized results.

    Raises OpenAlexError on any request failure or unexpected response shape.
    """
    settings = get_settings()
    params: dict[str, str | int] = {"search": keyword, "per-page": limit}

    date_filters = []
    if year_from:
        date_filters.append(f"from_publication_date:{year_from}-01-01")
    if year_to:
        date_filters.append(f"to_publication_date:{year_to}-12-31")
    if date_filters:
        params["filter"] = ",".join(date_filters)
    if settings.OPENALEX_MAILTO:
        params["mailto"] = settings.OPENALEX_MAILTO

    try:
        async with httpx.AsyncClient(timeout=settings.EXTERNAL_API_TIMEOUT_SECONDS) as client:
            response = await client.get(_BASE_URL, params=params)
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPError as exc:
        raise OpenAlexError(f"OpenAlex request failed: {exc}") from exc

    try:
        return [_to_paper_result(item) for item in payload.get("results", [])]
    except (KeyError, TypeError, ValueError) as exc:
        raise OpenAlexError(f"Unexpected OpenAlex response shape: {exc}") from exc


def _to_paper_result(item: dict) -> PaperResult:
    primary_location = item.get("primary_location") or {}
    source = primary_location.get("source") or {}
    open_access = item.get("open_access") or {}

    doi = item.get("doi")
    if doi:
        doi = doi.removeprefix("https://doi.org/")

    return PaperResult(
        title=item.get("title") or item.get("display_name") or "",
        authors=[
            authorship.get("author", {}).get("display_name", "") for authorship in item.get("authorships") or []
        ],
        journal=source.get("display_name"),
        year=item.get("publication_year"),
        citation_count=item.get("cited_by_count"),
        doi=doi,
        abstract=_reconstruct_abstract(item.get("abstract_inverted_index")),
        pdf_url=open_access.get("oa_url") or primary_location.get("pdf_url"),
        published_date=item.get("publication_date"),
        source="openalex",
    )


def _reconstruct_abstract(inverted_index: dict[str, list[int]] | None) -> str | None:
    """OpenAlex stores abstracts as a word -> positions inverted index (for
    copyright reasons) instead of plain text; rebuild the plain text form."""
    if not inverted_index:
        return None

    positions: dict[int, str] = {}
    for word, indexes in inverted_index.items():
        for index in indexes:
            positions[index] = word

    return " ".join(positions[i] for i in sorted(positions))
