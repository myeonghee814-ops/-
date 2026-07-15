"""Unit tests for the graceful-degradation fallbacks added to
search_pipeline.py: when a Gemini call (query expansion, re-ranking, or
per-paper battery extraction) raises RuntimeError after ai_service's own
retries are exhausted, the pipeline should still return a usable result
instead of failing the whole search, and report `ai_degraded=True` so the
caller can surface a notice.
"""

import asyncio

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.services import search_pipeline, semantic_scholar_service


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def _candidate(paper_id="p1", title="A Paper") -> semantic_scholar_service.Candidate:
    return semantic_scholar_service.Candidate(
        paper_id=paper_id,
        title=title,
        authors="Author A",
        journal="Journal X",
        year=2024,
        doi="10.1/x",
        abstract="An abstract.",
    )


async def _fake_expand_ok(keyword, gemini_api_key=None):
    return f"expanded {keyword}", ["term"]


async def _fake_expand_fails(keyword, gemini_api_key=None):
    raise RuntimeError("AI 검색어 확장에 실패했습니다: 503")


async def _fake_rerank_ok(keyword, candidates, gemini_api_key=None):
    return [(c, 90.0, "관련성이 높습니다.") for c in candidates]


async def _fake_rerank_fails(keyword, candidates, gemini_api_key=None):
    raise RuntimeError("AI 재순위화에 실패했습니다: 503")


async def _fake_extract_ok(title, abstract, gemini_api_key=None):
    return {"cathode": "NCA", "anode": "Graphite", "performance_summary": "좋음"}


async def _fake_extract_fails(title, abstract, gemini_api_key=None):
    raise RuntimeError("AI 배터리 정보 추출에 실패했습니다: 503")


def _patch_search_candidates(monkeypatch, candidates):
    async def _fake(query, max_results=None):
        return candidates

    monkeypatch.setattr(search_pipeline.semantic_scholar_service, "search_candidates", _fake)


def test_run_search_happy_path_not_degraded(monkeypatch, db):
    monkeypatch.setattr(search_pipeline.ai_service, "expand_search_query", _fake_expand_ok)
    monkeypatch.setattr(search_pipeline.ai_service, "rerank_candidates", _fake_rerank_ok)
    monkeypatch.setattr(search_pipeline.ai_service, "extract_battery_analysis", _fake_extract_ok)
    _patch_search_candidates(monkeypatch, [_candidate()])

    search_query, ai_degraded = asyncio.run(search_pipeline.run_search(db, "실리콘 음극"))

    assert ai_degraded is False
    assert search_query.ai_degraded is False
    assert search_query.expanded_query == "expanded 실리콘 음극"
    assert len(search_query.results) == 1
    assert search_query.results[0].relevance_score == 90.0
    assert search_query.results[0].paper.cathode == "NCA"


def test_run_search_falls_back_to_raw_keyword_when_expansion_fails(monkeypatch, db):
    monkeypatch.setattr(search_pipeline.ai_service, "expand_search_query", _fake_expand_fails)
    monkeypatch.setattr(search_pipeline.ai_service, "rerank_candidates", _fake_rerank_ok)
    monkeypatch.setattr(search_pipeline.ai_service, "extract_battery_analysis", _fake_extract_ok)
    _patch_search_candidates(monkeypatch, [_candidate()])

    search_query, ai_degraded = asyncio.run(search_pipeline.run_search(db, "실리콘 음극"))

    assert ai_degraded is True
    assert search_query.ai_degraded is True
    assert search_query.expanded_query == "실리콘 음극"
    assert len(search_query.results) == 1


def test_run_search_falls_back_to_original_order_when_reranking_fails(monkeypatch, db):
    monkeypatch.setattr(search_pipeline.ai_service, "expand_search_query", _fake_expand_ok)
    monkeypatch.setattr(search_pipeline.ai_service, "rerank_candidates", _fake_rerank_fails)
    monkeypatch.setattr(search_pipeline.ai_service, "extract_battery_analysis", _fake_extract_ok)
    candidates = [_candidate("p1", "First"), _candidate("p2", "Second")]
    _patch_search_candidates(monkeypatch, candidates)

    search_query, ai_degraded = asyncio.run(search_pipeline.run_search(db, "실리콘 음극"))

    assert ai_degraded is True
    assert [r.paper.title for r in search_query.results] == ["First", "Second"]
    assert all(r.relevance_score == 0.0 for r in search_query.results)
    assert all(r.why_selected == "" for r in search_query.results)


def test_run_search_falls_back_to_no_info_when_extraction_fails(monkeypatch, db):
    monkeypatch.setattr(search_pipeline.ai_service, "expand_search_query", _fake_expand_ok)
    monkeypatch.setattr(search_pipeline.ai_service, "rerank_candidates", _fake_rerank_ok)
    monkeypatch.setattr(search_pipeline.ai_service, "extract_battery_analysis", _fake_extract_fails)
    _patch_search_candidates(monkeypatch, [_candidate()])

    search_query, ai_degraded = asyncio.run(search_pipeline.run_search(db, "실리콘 음극"))

    assert ai_degraded is True
    paper = search_query.results[0].paper
    assert paper.cathode == ""
    assert paper.extracted_at is None
    assert paper.is_extracted is False
