import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from main import app
from schemas.analysis import AnalyzeRequest, PaperAnalysis
from services import ai_analysis_service
from services.external import openai_client
from services.external.exceptions import OpenAIAnalysisError


def _sample_analysis() -> PaperAnalysis:
    return PaperAnalysis(
        title="Example Paper",
        authors=["A. Author"],
        journal="Journal of Power Sources",
        electrolyte="1M LiPF6 in EC/DMC",
        salt="LiPF6",
        solvent="EC/DMC",
        additive="FEC",
        cathode="NMC811",
        anode="Graphite",
        separator="Celgard 2325",
        cell_type="Coin cell (2032)",
        voltage_window="3.0-4.3 V",
        temperature="25 C",
        formation_protocol="C/20 for 2 cycles",
        cycle_condition="1C/1C, 25 C",
        rate_capability="80% capacity retention at 5C",
        main_findings=["Improved cycling stability with FEC additive"],
        innovation="Novel FEC/VC co-additive combination",
        advantages=["Higher capacity retention", "Reduced gas generation"],
        limitations=["Limited high-temperature data"],
        future_work=["Test at elevated temperatures"],
    )


def _fake_settings(api_key: str | None = "test-key") -> SimpleNamespace:
    return SimpleNamespace(OPENAI_API_KEY=api_key, OPENAI_MODEL="gpt-4o-mini", EXTERNAL_API_TIMEOUT_SECONDS=10.0)


# --- ai_analysis_service: orchestration, mocking the OpenAI client entirely ---


@pytest.mark.asyncio
async def test_analyze_paper_returns_client_result(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(openai_client, "analyze", AsyncMock(return_value=_sample_analysis()))

    request = AnalyzeRequest(title="Example Paper", abstract="An abstract about electrolytes.")
    result = await ai_analysis_service.analyze_paper(request)

    assert result.title == "Example Paper"
    assert result.salt == "LiPF6"


@pytest.mark.asyncio
async def test_analyze_paper_propagates_client_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(openai_client, "analyze", AsyncMock(side_effect=OpenAIAnalysisError("boom")))

    request = AnalyzeRequest(title="Example Paper", abstract="An abstract.")
    with pytest.raises(OpenAIAnalysisError):
        await ai_analysis_service.analyze_paper(request)


def test_build_user_content_includes_title_and_abstract() -> None:
    request = AnalyzeRequest(title="Example Paper", abstract="An abstract.")
    content = ai_analysis_service._build_user_content(request)

    assert "Example Paper" in content
    assert "An abstract." in content


# --- openai_client: request/response handling, mocking the SDK client itself ---


@pytest.mark.asyncio
async def test_openai_client_parses_valid_response(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = json.dumps(_sample_analysis().model_dump())
    fake_response = SimpleNamespace(output_text=payload)
    fake_client = SimpleNamespace(responses=SimpleNamespace(create=AsyncMock(return_value=fake_response)))

    monkeypatch.setattr(openai_client, "get_settings", lambda: _fake_settings())
    monkeypatch.setattr(openai_client, "AsyncOpenAI", lambda **kwargs: fake_client)

    result = await openai_client.analyze("system prompt", "user content")

    assert result.title == "Example Paper"
    assert result.main_findings == ["Improved cycling stability with FEC additive"]


@pytest.mark.asyncio
async def test_openai_client_raises_when_api_key_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(openai_client, "get_settings", lambda: _fake_settings(api_key=None))

    with pytest.raises(OpenAIAnalysisError):
        await openai_client.analyze("system", "user")


@pytest.mark.asyncio
async def test_openai_client_raises_on_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_response = SimpleNamespace(output_text="not valid json")
    fake_client = SimpleNamespace(responses=SimpleNamespace(create=AsyncMock(return_value=fake_response)))

    monkeypatch.setattr(openai_client, "get_settings", lambda: _fake_settings())
    monkeypatch.setattr(openai_client, "AsyncOpenAI", lambda **kwargs: fake_client)

    with pytest.raises(OpenAIAnalysisError):
        await openai_client.analyze("system", "user")


# --- endpoint: POST /api/v1/analyze ---


@pytest.mark.asyncio
async def test_analyze_endpoint_returns_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(openai_client, "analyze", AsyncMock(return_value=_sample_analysis()))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/analyze", json={"title": "Example Paper", "abstract": "An abstract."}
        )

    assert response.status_code == 200
    body = response.json()
    assert body["salt"] == "LiPF6"
    assert body["advantages"] == ["Higher capacity retention", "Reduced gas generation"]


@pytest.mark.asyncio
async def test_analyze_endpoint_accepts_pdf_text_instead_of_abstract(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(openai_client, "analyze", AsyncMock(return_value=_sample_analysis()))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/analyze", json={"title": "Example Paper", "pdf_text": "Full extracted PDF text..."}
        )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_analyze_endpoint_requires_abstract_or_pdf_text() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/analyze", json={"title": "Example Paper"})

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_analyze_endpoint_returns_502_when_provider_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(openai_client, "analyze", AsyncMock(side_effect=OpenAIAnalysisError("boom")))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/analyze", json={"title": "Example Paper", "abstract": "An abstract."}
        )

    assert response.status_code == 502
