"""Unit tests for the Semantic Scholar 429 retry/backoff added to
semantic_scholar_service.py. All calls are mocked - no network access, no
shared rate-limit pool consumed.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.services import semantic_scholar_service

SEARCH_URL = semantic_scholar_service.SEARCH_URL


class _FakeAsyncClientCM:
    """Stands in for `async with httpx.AsyncClient() as client`."""

    def __init__(self, client):
        self._client = client

    async def __aenter__(self):
        return self._client

    async def __aexit__(self, *exc_info):
        return False


def _install_fake_client(monkeypatch, responses):
    """Patch httpx.AsyncClient so `client.get(...)` returns `responses` in
    order, one per call, instead of hitting the network."""

    fake_client = MagicMock()
    fake_client.get = AsyncMock(side_effect=responses)
    mock_client_cls = MagicMock(return_value=_FakeAsyncClientCM(fake_client))
    monkeypatch.setattr(semantic_scholar_service.httpx, "AsyncClient", mock_client_cls)
    return fake_client


def _ok_response(papers: list[dict]) -> httpx.Response:
    body = {"data": papers}
    return httpx.Response(200, json=body, request=httpx.Request("GET", SEARCH_URL))


def _rate_limited_response(headers=None) -> httpx.Response:
    return httpx.Response(
        429, json={"message": "Too Many Requests"}, headers=headers or {},
        request=httpx.Request("GET", SEARCH_URL),
    )


@pytest.fixture
def no_sleep(monkeypatch):
    """Replace asyncio.sleep with a recording stub so tests don't actually
    wait out the retry delays."""

    calls: list[float] = []

    async def _fake_sleep(seconds):
        calls.append(seconds)

    monkeypatch.setattr(semantic_scholar_service.asyncio, "sleep", _fake_sleep)
    return calls


# --- _retry_delay_seconds ----------------------------------------------------


def test_retry_delay_prefers_retry_after_header():
    resp = _rate_limited_response(headers={"retry-after": "5"})
    assert semantic_scholar_service._retry_delay_seconds(resp, attempt=0) == 5.0


def test_retry_delay_falls_back_to_exponential_backoff():
    resp = _rate_limited_response()
    assert semantic_scholar_service._retry_delay_seconds(resp, attempt=0) == 1.0
    assert semantic_scholar_service._retry_delay_seconds(resp, attempt=1) == 2.0
    assert semantic_scholar_service._retry_delay_seconds(resp, attempt=2) == 4.0


# --- search_candidates retry/backoff behavior --------------------------------


def test_search_candidates_succeeds_on_first_try(monkeypatch, no_sleep):
    client = _install_fake_client(monkeypatch, [_ok_response([{"paperId": "1", "title": "Paper"}])])

    result = asyncio.run(semantic_scholar_service.search_candidates("silicon anode"))

    assert len(result) == 1
    assert client.get.await_count == 1
    assert no_sleep == []


def test_search_candidates_retries_on_429_then_succeeds(monkeypatch, no_sleep):
    responses = [
        _rate_limited_response(headers={"retry-after": "2"}),
        _ok_response([{"paperId": "1", "title": "Paper"}]),
    ]
    client = _install_fake_client(monkeypatch, responses)

    result = asyncio.run(semantic_scholar_service.search_candidates("silicon anode"))

    assert len(result) == 1
    assert client.get.await_count == 2
    assert no_sleep == [2.0]


def test_search_candidates_retry_cap_is_exhausted(monkeypatch, no_sleep):
    """After _MAX_RETRIES consecutive 429s, the error must propagate instead
    of retrying forever."""

    responses = [_rate_limited_response()] * (semantic_scholar_service._MAX_RETRIES + 1)
    client = _install_fake_client(monkeypatch, responses)

    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(semantic_scholar_service.search_candidates("silicon anode"))

    assert client.get.await_count == semantic_scholar_service._MAX_RETRIES + 1
    assert len(no_sleep) == semantic_scholar_service._MAX_RETRIES


def test_search_candidates_non_retryable_error_raises_immediately(monkeypatch, no_sleep):
    responses = [httpx.Response(500, request=httpx.Request("GET", SEARCH_URL))]
    client = _install_fake_client(monkeypatch, responses)

    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(semantic_scholar_service.search_candidates("silicon anode"))

    assert client.get.await_count == 1
    assert no_sleep == []
