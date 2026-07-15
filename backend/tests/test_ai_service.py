"""Unit tests for the Gemini retry backoff and JSON-parsing fixes in
ai_service.py. All Gemini calls are mocked - no network access, no API
quota consumed - so these can (and should) be run even when the real
Gemini free-tier quota for the day is exhausted.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.services import ai_service

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-test:generateContent"


class _FakeAsyncClientCM:
    """Stands in for `async with httpx.AsyncClient() as client`."""

    def __init__(self, client):
        self._client = client

    async def __aenter__(self):
        return self._client

    async def __aexit__(self, *exc_info):
        return False


def _install_fake_client(monkeypatch, responses):
    """Patch httpx.AsyncClient so `client.post(...)` returns `responses` in
    order, one per call, instead of hitting the network."""

    fake_client = MagicMock()
    fake_client.post = AsyncMock(side_effect=responses)
    mock_client_cls = MagicMock(return_value=_FakeAsyncClientCM(fake_client))
    monkeypatch.setattr(ai_service.httpx, "AsyncClient", mock_client_cls)
    return fake_client


def _ok_response(payload: dict) -> httpx.Response:
    body = {"candidates": [{"content": {"parts": [{"text": json.dumps(payload)}]}}]}
    return httpx.Response(200, json=body, request=httpx.Request("POST", GEMINI_URL))


def _ok_response_raw_text(text: str) -> httpx.Response:
    body = {"candidates": [{"content": {"parts": [{"text": text}]}}]}
    return httpx.Response(200, json=body, request=httpx.Request("POST", GEMINI_URL))


def _error_response(status: int, message: str, retry_delay: str | None = None, headers=None) -> httpx.Response:
    details = []
    if retry_delay:
        details.append(
            {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": retry_delay}
        )
    body = {"error": {"code": status, "message": message, "status": "ERROR", "details": details}}
    return httpx.Response(
        status, json=body, headers=headers or {}, request=httpx.Request("POST", GEMINI_URL)
    )


@pytest.fixture(autouse=True)
def _configure_settings(monkeypatch):
    monkeypatch.setattr(ai_service.settings, "gemini_api_key", "test-key")
    monkeypatch.setattr(ai_service.settings, "gemini_model", "gemini-test")


@pytest.fixture
def no_sleep(monkeypatch):
    """Replace asyncio.sleep with a recording stub so tests don't actually
    wait out the (now much longer) retry delays."""

    calls: list[float] = []

    async def _fake_sleep(seconds):
        calls.append(seconds)

    monkeypatch.setattr(ai_service.asyncio, "sleep", _fake_sleep)
    return calls


# --- _parse_json_object -----------------------------------------------------


def test_parse_json_object_plain():
    assert ai_service._parse_json_object('{"a": 1}') == {"a": 1}


def test_parse_json_object_ignores_trailing_text():
    """Reproduces the real failure: Gemini's JSON-mode response sometimes has
    extra content appended after the JSON object, which used to blow up
    plain json.loads() with a JSONDecodeError ("Extra data")."""

    text = '{"english_query": "LiFSI", "expanded_terms": ["LiFSI"]}\n\nNote: also consider salts.'
    assert ai_service._parse_json_object(text) == {
        "english_query": "LiFSI",
        "expanded_terms": ["LiFSI"],
    }


def test_parse_json_object_tolerates_leading_whitespace():
    assert ai_service._parse_json_object('\n  {"a": 1}  ') == {"a": 1}


# --- _retry_delay_seconds ----------------------------------------------------


def test_retry_delay_prefers_retry_after_header():
    resp = _error_response(429, "quota exceeded", headers={"retry-after": "90"})
    assert ai_service._retry_delay_seconds(resp) == 90.0


def test_retry_delay_header_clamped_to_minimum():
    resp = _error_response(429, "quota exceeded", headers={"retry-after": "5"})
    assert ai_service._retry_delay_seconds(resp) == ai_service._MIN_RETRY_DELAY_SECONDS


def test_retry_delay_falls_back_to_retry_info_detail():
    resp = _error_response(429, "quota exceeded, please wait", retry_delay="55.18s")
    assert ai_service._retry_delay_seconds(resp) == 55.18


def test_retry_delay_falls_back_to_message_text():
    resp = _error_response(429, "Quota exceeded. Please retry in 48.4s.")
    assert ai_service._retry_delay_seconds(resp) == 48.4


def test_retry_delay_defaults_to_minimum_when_no_info():
    resp = httpx.Response(503, request=httpx.Request("POST", GEMINI_URL))
    assert ai_service._retry_delay_seconds(resp) == ai_service._MIN_RETRY_DELAY_SECONDS


# --- _generate_json retry/backoff behavior -----------------------------------


def test_generate_json_succeeds_on_first_try(monkeypatch, no_sleep):
    client = _install_fake_client(monkeypatch, [_ok_response({"ok": True})])

    result = asyncio.run(ai_service._generate_json("system", {"keyword": "x"}))

    assert result == {"ok": True}
    assert client.post.await_count == 1
    assert no_sleep == []


def test_generate_json_retries_once_on_429_then_succeeds(monkeypatch, no_sleep):
    responses = [
        _error_response(429, "quota exceeded", retry_delay="55s"),
        _ok_response({"ok": True}),
    ]
    client = _install_fake_client(monkeypatch, responses)

    result = asyncio.run(ai_service._generate_json("system", {"keyword": "x"}))

    assert result == {"ok": True}
    assert client.post.await_count == 2
    assert no_sleep == [55.0]


def test_generate_json_429_retry_cap_is_one(monkeypatch, no_sleep):
    """A second consecutive 429 must NOT be retried again (max 1 retry for
    429) - it should propagate as an HTTPStatusError instead of hanging or
    burning further quota."""

    responses = [
        _error_response(429, "quota exceeded", retry_delay="55s"),
        _error_response(429, "quota exceeded", retry_delay="55s"),
    ]
    client = _install_fake_client(monkeypatch, responses)

    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(ai_service._generate_json("system", {"keyword": "x"}))

    assert client.post.await_count == 2
    assert no_sleep == [55.0]


def test_generate_json_retries_twice_on_503_then_succeeds(monkeypatch, no_sleep):
    responses = [
        _error_response(503, "overloaded"),
        _error_response(503, "overloaded"),
        _ok_response({"ok": True}),
    ]
    client = _install_fake_client(monkeypatch, responses)

    result = asyncio.run(ai_service._generate_json("system", {"keyword": "x"}))

    assert result == {"ok": True}
    assert client.post.await_count == 3
    assert no_sleep == [ai_service._MIN_RETRY_DELAY_SECONDS] * 2


def test_generate_json_503_retry_cap_is_three(monkeypatch, no_sleep):
    """A fourth consecutive 503 must NOT be retried again (max 3 retries)."""

    responses = [_error_response(503, "overloaded")] * 4
    client = _install_fake_client(monkeypatch, responses)

    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(ai_service._generate_json("system", {"keyword": "x"}))

    assert client.post.await_count == 4
    assert no_sleep == [ai_service._MIN_RETRY_DELAY_SECONDS] * 3


def test_generate_json_retries_on_timeout_then_succeeds(monkeypatch, no_sleep):
    responses = [
        httpx.ReadTimeout("timed out"),
        _ok_response({"ok": True}),
    ]
    client = _install_fake_client(monkeypatch, responses)

    result = asyncio.run(ai_service._generate_json("system", {"keyword": "x"}))

    assert result == {"ok": True}
    assert client.post.await_count == 2
    assert no_sleep == [ai_service._TIMEOUT_RETRY_DELAY_SECONDS]


def test_generate_json_timeout_retry_cap_is_exhausted(monkeypatch, no_sleep):
    """After _MAX_TIMEOUT_RETRIES consecutive timeouts, the error must
    propagate instead of retrying forever."""

    responses = [httpx.ReadTimeout("timed out")] * (ai_service._MAX_TIMEOUT_RETRIES + 1)
    client = _install_fake_client(monkeypatch, responses)

    with pytest.raises(httpx.ReadTimeout):
        asyncio.run(ai_service._generate_json("system", {"keyword": "x"}))

    assert client.post.await_count == ai_service._MAX_TIMEOUT_RETRIES + 1
    assert no_sleep == [ai_service._TIMEOUT_RETRY_DELAY_SECONDS] * ai_service._MAX_TIMEOUT_RETRIES


def test_generate_json_non_retryable_error_raises_immediately(monkeypatch, no_sleep):
    responses = [_error_response(400, "bad request")]
    client = _install_fake_client(monkeypatch, responses)

    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(ai_service._generate_json("system", {"keyword": "x"}))

    assert client.post.await_count == 1
    assert no_sleep == []


def test_generate_json_tolerates_trailing_text_end_to_end(monkeypatch, no_sleep):
    """Full pipeline through _generate_json: a 429 that's retried once,
    followed by a 200 whose text has trailing content after the JSON."""

    responses = [
        _error_response(429, "quota exceeded", retry_delay="30s"),
        _ok_response_raw_text('{"english_query": "LiFSI"}\nExtra trailing commentary.'),
    ]
    client = _install_fake_client(monkeypatch, responses)

    result = asyncio.run(ai_service._generate_json("system", {"keyword": "x"}))

    assert result == {"english_query": "LiFSI"}
    assert client.post.await_count == 2
