import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import ValidationError

from schemas.search import SearchQuery, SearchResponse
from services.external.exceptions import ExternalSearchError
from services.search_service import search_papers

logger = logging.getLogger(__name__)

# Mounted at /api (not the versioned /api/v1 prefix) in main.py, per spec.
router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=SearchResponse)
async def search(
    keyword: str = Query(..., min_length=1, description="Search keyword, e.g. a topic or title fragment"),
    year_from: int | None = Query(default=None, ge=1900, description="Earliest publication year (inclusive)"),
    year_to: int | None = Query(default=None, ge=1900, description="Latest publication year (inclusive)"),
    limit: int = Query(default=20, ge=1, le=100, description="Maximum number of papers to return"),
) -> SearchResponse:
    try:
        query = SearchQuery(keyword=keyword, year_from=year_from, year_to=year_to, limit=limit)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        results, source = await search_papers(query)
    except ExternalSearchError as exc:
        logger.error("Literature search failed: %s", exc)
        raise HTTPException(
            status_code=502, detail="Literature search providers are currently unavailable"
        ) from exc

    return SearchResponse(query=query, source=source, count=len(results), results=results)
