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


# --- require_caller_api_key ---------------------------------------------------


def test_generate_json_requires_caller_key_when_flag_set(monkeypatch, no_sleep):
    monkeypatch.setattr(ai_service.settings, "require_caller_api_key", True)
    client = _install_fake_client(monkeypatch, [])

    with pytest.raises(RuntimeError, match="개인 Gemini API 키가 필요"):
        asyncio.run(ai_service._generate_json("system", {"keyword": "x"}, gemini_api_key=None))

    # Fails before ever making the HTTP call - no quota spent on a request
    # that was always going to be rejected.
    assert client.post.await_count == 0


def test_generate_json_allows_caller_key_when_flag_set(monkeypatch, no_sleep):
    monkeypatch.setattr(ai_service.settings, "require_caller_api_key", True)
    client = _install_fake_client(monkeypatch, [_ok_response({"ok": True})])

    result = asyncio.run(ai_service._generate_json("system", {"keyword": "x"}, gemini_api_key="caller-key"))

    assert result == {"ok": True}
    assert client.post.await_count == 1


def test_generate_json_flag_unset_still_falls_back_to_server_key(monkeypatch, no_sleep):
    """Regression: the default (flag False) must keep working exactly as
    before - local dev relies on this fallback."""

    client = _install_fake_client(monkeypatch, [_ok_response({"ok": True})])

    result = asyncio.run(ai_service._generate_json("system", {"keyword": "x"}, gemini_api_key=None))

    assert result == {"ok": True}
    assert client.post.await_count == 1


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


# --- expand_search_query --------------------------------------------------------


def _sent_payload(client) -> dict:
    """Decodes the JSON payload actually sent to Gemini from the last
    `client.post(...)` call - it's embedded as `contents[0].parts[0].text`
    (see `_generate_json`), not a top-level request field."""

    body = client.post.call_args.kwargs["json"]
    return json.loads(body["contents"][0]["parts"][0]["text"])


def test_expand_search_query_omits_focus_hint_when_not_given(monkeypatch):
    client = _install_fake_client(
        monkeypatch, [_ok_response({"english_query": "FEC electrolyte additive", "expanded_terms": ["FEC"]})]
    )

    asyncio.run(ai_service.expand_search_query("FEC"))

    sent = _sent_payload(client)
    assert sent == {"keyword": "FEC"}


def test_expand_search_query_includes_focus_hint_when_given(monkeypatch):
    client = _install_fake_client(
        monkeypatch, [_ok_response({"english_query": "FEC electrolyte additive", "expanded_terms": ["FEC"]})]
    )

    asyncio.run(ai_service.expand_search_query("FEC", focus_hint="전해액 첨가제 위주로 확장"))

    sent = _sent_payload(client)
    assert sent == {"keyword": "FEC", "focus_hint": "전해액 첨가제 위주로 확장"}


def test_expand_search_query_falls_back_to_keyword_when_english_query_missing(monkeypatch):
    _install_fake_client(monkeypatch, [_ok_response({"expanded_terms": []})])

    english_query, expanded_terms = asyncio.run(ai_service.expand_search_query("FEC"))

    assert english_query == "FEC"
    assert expanded_terms == []


# --- rerank_and_extract_candidates --------------------------------------------


def _candidate(paper_id="p1", title="A Paper"):
    from app.services.semantic_scholar_service import Candidate

    return Candidate(
        paper_id=paper_id,
        title=title,
        authors="Author A",
        journal="Journal X",
        year=2024,
        doi="10.1/x",
        abstract="An abstract.",
    )


def test_rerank_and_extract_candidates_empty_input_skips_the_call(monkeypatch):
    client = _install_fake_client(monkeypatch, [])

    result = asyncio.run(ai_service.rerank_and_extract_candidates("keyword", []))

    assert result == []
    assert client.post.await_count == 0


def test_rerank_and_extract_candidates_returns_sorted_tuples_with_battery_info(monkeypatch):
    payload = {
        "rankings": [
            {"index": 0, "relevance_score": 40.0, "why_selected": "관련성 낮음", "cathode": "LFP"},
            {"index": 1, "relevance_score": 90.0, "why_selected": "관련성 높음", "cathode": "NCA"},
        ]
    }
    _install_fake_client(monkeypatch, [_ok_response(payload)])
    candidates = [_candidate("p1", "First"), _candidate("p2", "Second")]

    result = asyncio.run(ai_service.rerank_and_extract_candidates("keyword", candidates))

    assert [c.title for c, _, _, _ in result] == ["Second", "First"]
    assert result[0][1] == 90.0
    assert result[0][2] == "관련성 높음"
    assert result[0][3]["cathode"] == "NCA"


def test_rerank_and_extract_candidates_ignores_out_of_range_index(monkeypatch):
    payload = {
        "rankings": [
            {"index": 0, "relevance_score": 50.0, "why_selected": "", "cathode": "NCA"},
            {"index": 5, "relevance_score": 50.0, "why_selected": "", "cathode": "LFP"},
        ]
    }
    _install_fake_client(monkeypatch, [_ok_response(payload)])

    result = asyncio.run(ai_service.rerank_and_extract_candidates("keyword", [_candidate()]))

    assert len(result) == 1
    assert result[0][3]["cathode"] == "NCA"


def test_rerank_and_extract_candidates_wraps_http_error_as_runtime_error(monkeypatch, no_sleep):
    _install_fake_client(monkeypatch, [_error_response(400, "bad request")])

    with pytest.raises(RuntimeError):
        asyncio.run(ai_service.rerank_and_extract_candidates("keyword", [_candidate()]))


# --- extract_deep_analysis ----------------------------------------------------


def test_extract_deep_analysis_returns_parsed_result(monkeypatch):
    payload = {
        "base_electrolyte": "1M LiPF6 in EC/DMC",
        "test_electrolyte": "1M LiPF6 in EC/DMC + 2wt% FEC",
        "voltage_range": "3.0-4.3 V",
        "cell_type_detail": "coin cell (half-cell), 2032 type",
        "key_findings": "FEC 첨가 시 용량 유지율이 개선되었습니다.",
        "summary": "FEC 첨가제의 SEI 안정화 효과를 확인한 연구입니다.",
    }
    client = _install_fake_client(monkeypatch, [_ok_response(payload)])

    result = asyncio.run(
        ai_service.extract_deep_analysis("Paper Title", "Full body text...", ["Figure 1. Cycling."])
    )

    assert result == payload
    assert client.post.await_count == 1


def test_extract_deep_analysis_truncates_long_body_text(monkeypatch):
    captured = {}

    async def _fake_generate_json(system_prompt, payload, gemini_api_key=None, *, stage=""):
        captured["body_text"] = payload["body_text"]
        return {"base_electrolyte": "정보 없음"}

    monkeypatch.setattr(ai_service, "_generate_json", _fake_generate_json)

    long_text = "x" * (ai_service._DEEP_ANALYSIS_BODY_TEXT_LIMIT + 5000)
    asyncio.run(ai_service.extract_deep_analysis("Paper Title", long_text, []))

    assert len(captured["body_text"]) == ai_service._DEEP_ANALYSIS_BODY_TEXT_LIMIT + len("...")


def test_extract_deep_analysis_wraps_http_error_as_runtime_error(monkeypatch, no_sleep):
    _install_fake_client(monkeypatch, [_error_response(400, "bad request")])

    with pytest.raises(RuntimeError):
        asyncio.run(ai_service.extract_deep_analysis("Paper Title", "Full body text...", []))


# --- expand_compound_category -------------------------------------------------


def test_expand_compound_category_returns_compound_list(monkeypatch):
    payload = {"compounds": ["LiFSI", "FEC", "LiPF6"]}
    client = _install_fake_client(monkeypatch, [_ok_response(payload)])

    result = asyncio.run(ai_service.expand_compound_category("불소계"))

    assert result == ["LiFSI", "FEC", "LiPF6"]
    assert client.post.await_count == 1


def test_expand_compound_category_returns_empty_list_when_gemini_is_unsure(monkeypatch):
    _install_fake_client(monkeypatch, [_ok_response({"compounds": []})])

    result = asyncio.run(ai_service.expand_compound_category("이상한계열"))

    assert result == []


def test_expand_compound_category_wraps_http_error_as_runtime_error(monkeypatch, no_sleep):
    _install_fake_client(monkeypatch, [_error_response(400, "bad request")])

    with pytest.raises(RuntimeError):
        asyncio.run(ai_service.expand_compound_category("불소계"))
