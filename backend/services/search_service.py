"""Literature search orchestration.

This module contains no HTTP/parsing details of its own — that lives in
services/external/*_client.py. It only decides which provider to call,
handles fallback, and caches results, keeping provider-specific logic fully
decoupled from the business rule ("try Semantic Scholar, then OpenAlex").
"""

import logging

from core.cache import TTLCache
from core.config import get_settings
from schemas.search import PaperResult, SearchQuery
from services.external import openalex_client, semantic_scholar_client
from services.external.exceptions import ExternalSearchError, OpenAlexError, SemanticScholarError

logger = logging.getLogger(__name__)

_settings = get_settings()
_cache: TTLCache[tuple[list[PaperResult], str]] = TTLCache(ttl_seconds=_settings.SEARCH_CACHE_TTL_SECONDS)


async def search_papers(query: SearchQuery) -> tuple[list[PaperResult], str]:
    """Search literature, preferring Semantic Scholar and falling back to
    OpenAlex if it fails. Returns (results, source_name).

    Raises ExternalSearchError if both providers fail.
    """
    cache_key = _cache_key(query)
    cached = _cache.get(cache_key)
    if cached is not None:
        logger.info("Search cache hit for keyword=%r", query.keyword)
        return cached

    try:
        results = await semantic_scholar_client.search(query.keyword, query.year_from, query.year_to, query.limit)
        source = "semantic_scholar"
    except SemanticScholarError as exc:
        logger.warning("Semantic Scholar search failed (%s); falling back to OpenAlex", exc)
        try:
            results = await openalex_client.search(query.keyword, query.year_from, query.year_to, query.limit)
            source = "openalex"
        except OpenAlexError as fallback_exc:
            logger.error("OpenAlex fallback also failed: %s", fallback_exc)
            raise ExternalSearchError("Both Semantic Scholar and OpenAlex searches failed") from fallback_exc

    _cache.set(cache_key, (results, source))
    return results, source


def _cache_key(query: SearchQuery) -> str:
    return f"{query.keyword.strip().lower()}|{query.year_from}|{query.year_to}|{query.limit}"
