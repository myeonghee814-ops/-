from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from main import app
from schemas.search import PaperResult, SearchQuery
from services import search_service
from services.external import openalex_client, semantic_scholar_client
from services.external.exceptions import ExternalSearchError, OpenAlexError, SemanticScholarError


@pytest.fixture(autouse=True)
def _clear_search_cache():
    search_service._cache._store.clear()
    yield
    search_service._cache._store.clear()


def _sample_result(source: str) -> PaperResult:
    return PaperResult(
        title="Solid Electrolyte Interphase Formation",
        authors=["A. Researcher"],
        journal="Journal of Power Sources",
        year=2022,
        citation_count=10,
        doi="10.1234/example",
        abstract="An abstract about electrolytes.",
        pdf_url="https://example.com/paper.pdf",
        published_date="2022-05-01",
        source=source,
    )


@pytest.mark.asyncio
async def test_search_uses_semantic_scholar_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        semantic_scholar_client, "search", AsyncMock(return_value=[_sample_result("semantic_scholar")])
    )
    monkeypatch.setattr(openalex_client, "search", AsyncMock(side_effect=AssertionError("should not be called")))

    query = SearchQuery(keyword="electrolyte")
    results, source = await search_service.search_papers(query)

    assert source == "semantic_scholar"
    assert len(results) == 1
    assert results[0].title == "Solid Electrolyte Interphase Formation"


@pytest.mark.asyncio
async def test_search_falls_back_to_openalex(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        semantic_scholar_client, "search", AsyncMock(side_effect=SemanticScholarError("boom"))
    )
    monkeypatch.setattr(
        openalex_client, "search", AsyncMock(return_value=[_sample_result("openalex")])
    )

    query = SearchQuery(keyword="fallback test")
    results, source = await search_service.search_papers(query)

    assert source == "openalex"
    assert results[0].source == "openalex"


@pytest.mark.asyncio
async def test_search_raises_when_both_providers_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(semantic_scholar_client, "search", AsyncMock(side_effect=SemanticScholarError("boom")))
    monkeypatch.setattr(openalex_client, "search", AsyncMock(side_effect=OpenAlexError("also boom")))

    query = SearchQuery(keyword="both fail")

    with pytest.raises(ExternalSearchError):
        await search_service.search_papers(query)


@pytest.mark.asyncio
async def test_search_result_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_search = AsyncMock(return_value=[_sample_result("semantic_scholar")])
    monkeypatch.setattr(semantic_scholar_client, "search", mock_search)

    query = SearchQuery(keyword="cache test")
    await search_service.search_papers(query)
    await search_service.search_papers(query)

    assert mock_search.call_count == 1


@pytest.mark.asyncio
async def test_search_endpoint_returns_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        semantic_scholar_client, "search", AsyncMock(return_value=[_sample_result("semantic_scholar")])
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/search", params={"keyword": "electrolyte", "year_from": 2020, "year_to": 2023, "limit": 5}
        )

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "semantic_scholar"
    assert body["count"] == 1
    assert body["results"][0]["doi"] == "10.1234/example"


@pytest.mark.asyncio
async def test_search_endpoint_rejects_invalid_year_range() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/search", params={"keyword": "electrolyte", "year_from": 2023, "year_to": 2020})

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_search_endpoint_returns_502_when_all_providers_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(semantic_scholar_client, "search", AsyncMock(side_effect=SemanticScholarError("boom")))
    monkeypatch.setattr(openalex_client, "search", AsyncMock(side_effect=OpenAlexError("also boom")))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/search", params={"keyword": "guaranteed to fail everywhere"})

    assert response.status_code == 502
