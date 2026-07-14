import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from main import app
from schemas.analysis import PaperAnalysis
from schemas.comparison import ComparisonResult, ComparisonTableRow
from services import comparison_service
from services.comparison_service import InsufficientAnalysesError
from services.external import openai_client
from services.external.exceptions import OpenAIAnalysisError


def _sample_paper_analysis(index: int) -> PaperAnalysis:
    return PaperAnalysis(
        title=f"Paper {index}",
        authors=[f"Author {index}"],
        journal="Journal of Power Sources",
        battery_system="Li-ion",
        electrolyte="1M LiPF6 in EC/DMC",
        salt="LiPF6",
        solvent="EC/DMC",
        additive="FEC",
        cathode="NMC811",
        anode="Graphite",
        separator="Celgard 2325",
        cell_type="Coin cell",
        voltage_window="3.0-4.3 V",
        temperature="25 C",
        formation_protocol="C/20 for 2 cycles",
        cycle_condition="1C/1C, 25 C",
        rate_capability="80% at 5C",
        main_findings=["Improved cycling stability"],
        innovation="Novel additive combination",
        advantages=["Higher capacity retention"],
        limitations=["Limited high-temperature data"],
        future_work=["Test at elevated temperatures"],
    )


def _sample_analyses(count: int) -> list[PaperAnalysis]:
    return [_sample_paper_analysis(i) for i in range(count)]


def _sample_comparison_result(paper_count: int = 0) -> ComparisonResult:
    return ComparisonResult(
        paper_count=paper_count,
        common_experimental_conditions=["Most papers use LiPF6-based electrolytes"],
        differences=["Cathode chemistry varies between NMC and LFP"],
        frequently_used_electrolytes=["1M LiPF6 in EC/DMC"],
        frequently_used_additives=["FEC"],
        most_common_cathode="NMC811",
        most_common_anode="Graphite",
        research_trend="Increasing focus on additive engineering for SEI stability",
        research_gap="Limited high-temperature cycling data",
        potential_future_direction="Systematic study of additive combinations at elevated temperatures",
        comparison_table=[
            ComparisonTableRow(
                title="Paper 0",
                electrolyte="1M LiPF6 in EC/DMC",
                salt="LiPF6",
                additive="FEC",
                cathode="NMC811",
                anode="Graphite",
                cycle_condition="1C/1C, 25 C",
                main_finding="Improved cycling stability",
                advantages="Higher capacity retention",
                limitations="Limited high-temperature data",
            )
        ],
    )


def _fake_settings(min_papers: int = 10) -> SimpleNamespace:
    return SimpleNamespace(COMPARISON_MIN_PAPERS=min_papers)


def _fake_openai_settings(api_key: str | None = "test-key") -> SimpleNamespace:
    return SimpleNamespace(OPENAI_API_KEY=api_key, OPENAI_MODEL="gpt-4o-mini", EXTERNAL_API_TIMEOUT_SECONDS=10.0)


# --- comparison_service: threshold enforcement + orchestration ---


@pytest.mark.asyncio
async def test_compare_papers_raises_when_below_minimum(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(comparison_service, "get_settings", lambda: _fake_settings(min_papers=10))

    with pytest.raises(InsufficientAnalysesError):
        await comparison_service.compare_papers(_sample_analyses(9))


@pytest.mark.asyncio
async def test_compare_papers_succeeds_at_minimum(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(comparison_service, "get_settings", lambda: _fake_settings(min_papers=10))
    monkeypatch.setattr(openai_client, "compare_papers", AsyncMock(return_value=_sample_comparison_result()))

    result = await comparison_service.compare_papers(_sample_analyses(10))

    assert result.most_common_cathode == "NMC811"


@pytest.mark.asyncio
async def test_compare_papers_overrides_paper_count_with_actual_count(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(comparison_service, "get_settings", lambda: _fake_settings(min_papers=10))
    # Model reports a wrong count; the service should trust the real batch size instead.
    monkeypatch.setattr(
        openai_client, "compare_papers", AsyncMock(return_value=_sample_comparison_result(paper_count=999))
    )

    result = await comparison_service.compare_papers(_sample_analyses(12))

    assert result.paper_count == 12


@pytest.mark.asyncio
async def test_compare_papers_propagates_client_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(comparison_service, "get_settings", lambda: _fake_settings(min_papers=10))
    monkeypatch.setattr(openai_client, "compare_papers", AsyncMock(side_effect=OpenAIAnalysisError("boom")))

    with pytest.raises(OpenAIAnalysisError):
        await comparison_service.compare_papers(_sample_analyses(10))


# --- openai_client.compare_papers: request/response handling ---


@pytest.mark.asyncio
async def test_openai_client_compare_papers_parses_valid_response(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = json.dumps(_sample_comparison_result(paper_count=10).model_dump())
    fake_response = SimpleNamespace(output_text=payload)
    fake_client = SimpleNamespace(responses=SimpleNamespace(create=AsyncMock(return_value=fake_response)))

    monkeypatch.setattr(openai_client, "get_settings", lambda: _fake_openai_settings())
    monkeypatch.setattr(openai_client, "get_openai_client", lambda: fake_client)

    result = await openai_client.compare_papers("system prompt", "user content")

    assert result.most_common_anode == "Graphite"
    assert len(result.comparison_table) == 1
    assert result.comparison_table[0].salt == "LiPF6"
    assert result.comparison_table[0].main_finding == "Improved cycling stability"


@pytest.mark.asyncio
async def test_openai_client_compare_papers_raises_on_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_response = SimpleNamespace(output_text="not valid json")
    fake_client = SimpleNamespace(responses=SimpleNamespace(create=AsyncMock(return_value=fake_response)))

    monkeypatch.setattr(openai_client, "get_settings", lambda: _fake_openai_settings())
    monkeypatch.setattr(openai_client, "get_openai_client", lambda: fake_client)

    with pytest.raises(OpenAIAnalysisError):
        await openai_client.compare_papers("system", "user")


# --- endpoint: POST /api/v1/compare ---


@pytest.mark.asyncio
async def test_compare_endpoint_returns_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(comparison_service, "get_settings", lambda: _fake_settings(min_papers=10))
    monkeypatch.setattr(openai_client, "compare_papers", AsyncMock(return_value=_sample_comparison_result()))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/compare",
            json={"analyses": [a.model_dump() for a in _sample_analyses(10)]},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["paper_count"] == 10
    assert body["most_common_cathode"] == "NMC811"
    assert isinstance(body["comparison_table"], list)
    assert body["comparison_table"][0]["salt"] == "LiPF6"
    assert body["comparison_table"][0]["main_finding"] == "Improved cycling stability"


@pytest.mark.asyncio
async def test_compare_endpoint_returns_422_below_minimum(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(comparison_service, "get_settings", lambda: _fake_settings(min_papers=10))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/compare",
            json={"analyses": [a.model_dump() for a in _sample_analyses(5)]},
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_compare_endpoint_returns_502_when_provider_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(comparison_service, "get_settings", lambda: _fake_settings(min_papers=10))
    monkeypatch.setattr(openai_client, "compare_papers", AsyncMock(side_effect=OpenAIAnalysisError("boom")))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/compare",
            json={"analyses": [a.model_dump() for a in _sample_analyses(10)]},
        )

    assert response.status_code == 502
