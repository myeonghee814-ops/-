"""Unit tests for search_pipeline.py:

- graceful degradation when a Gemini call (query expansion, re-ranking,
  or battery extraction) fails or the time budget runs out - the pipeline
  should still return a usable result instead of failing the whole
  search, and report `ai_degraded=True` so the caller can surface a
  notice.
- batched battery extraction (one call for all not-yet-cached papers,
  falling back to one-call-per-paper only if the batch call itself
  fails) and the final (year desc, relevance score desc) sort.
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


def _candidate(paper_id="p1", title="A Paper", year=2024) -> semantic_scholar_service.Candidate:
    return semantic_scholar_service.Candidate(
        paper_id=paper_id,
        title=title,
        authors="Author A",
        journal="Journal X",
        year=year,
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


async def _fake_extract_individual_ok(title, abstract, gemini_api_key=None):
    return {"cathode": "NCA", "anode": "Graphite", "performance_summary": "좋음"}


async def _fake_extract_individual_fails(title, abstract, gemini_api_key=None):
    raise RuntimeError("AI 배터리 정보 추출에 실패했습니다: 503")


async def _fake_extract_individual_must_not_be_called(title, abstract, gemini_api_key=None):
    raise AssertionError("individual extraction should not be called")


async def _fake_extract_batch_ok(papers, gemini_api_key=None):
    return {
        i: {"cathode": "NCA", "anode": "Graphite", "performance_summary": "좋음"}
        for i in range(len(papers))
    }


async def _fake_extract_batch_fails(papers, gemini_api_key=None):
    raise RuntimeError("AI 배터리 정보 일괄 추출에 실패했습니다: 503")


async def _fake_extract_batch_must_not_be_called(papers, gemini_api_key=None):
    raise AssertionError("batch extraction should not be called")


def _patch_search_candidates(monkeypatch, candidates):
    async def _fake(query, max_results=None):
        return candidates

    monkeypatch.setattr(search_pipeline.semantic_scholar_service, "search_candidates", _fake)


def _patch_ai_defaults(monkeypatch, *, expand=_fake_expand_ok, rerank=_fake_rerank_ok, batch=None, individual=None):
    monkeypatch.setattr(search_pipeline.ai_service, "expand_search_query", expand)
    monkeypatch.setattr(search_pipeline.ai_service, "rerank_candidates", rerank)
    if batch is not None:
        monkeypatch.setattr(search_pipeline.ai_service, "extract_battery_analysis_batch", batch)
    if individual is not None:
        monkeypatch.setattr(search_pipeline.ai_service, "extract_battery_analysis", individual)


def test_run_search_happy_path_not_degraded(monkeypatch, db):
    _patch_ai_defaults(
        monkeypatch,
        batch=_fake_extract_batch_ok,
        individual=_fake_extract_individual_must_not_be_called,
    )
    _patch_search_candidates(monkeypatch, [_candidate()])

    search_query, ai_degraded = asyncio.run(search_pipeline.run_search(db, "실리콘 음극"))

    assert ai_degraded is False
    assert search_query.ai_degraded is False
    assert search_query.expanded_query == "expanded 실리콘 음극"
    assert len(search_query.results) == 1
    assert search_query.results[0].relevance_score == 90.0
    assert search_query.results[0].paper.cathode == "NCA"


def test_run_search_falls_back_to_raw_keyword_when_expansion_fails(monkeypatch, db):
    _patch_ai_defaults(monkeypatch, expand=_fake_expand_fails, batch=_fake_extract_batch_ok)
    _patch_search_candidates(monkeypatch, [_candidate()])

    search_query, ai_degraded = asyncio.run(search_pipeline.run_search(db, "실리콘 음극"))

    assert ai_degraded is True
    assert search_query.ai_degraded is True
    assert search_query.expanded_query == "실리콘 음극"
    assert len(search_query.results) == 1


def test_run_search_falls_back_to_original_order_when_reranking_fails(monkeypatch, db):
    _patch_ai_defaults(monkeypatch, rerank=_fake_rerank_fails, batch=_fake_extract_batch_ok)
    candidates = [_candidate("p1", "First"), _candidate("p2", "Second")]
    _patch_search_candidates(monkeypatch, candidates)

    search_query, ai_degraded = asyncio.run(search_pipeline.run_search(db, "실리콘 음극"))

    assert ai_degraded is True
    assert [r.paper.title for r in search_query.results] == ["First", "Second"]
    assert all(r.relevance_score == 0.0 for r in search_query.results)
    assert all(r.why_selected == "" for r in search_query.results)


def test_run_search_falls_back_to_individual_calls_when_batch_fails(monkeypatch, db):
    _patch_ai_defaults(
        monkeypatch,
        batch=_fake_extract_batch_fails,
        individual=_fake_extract_individual_ok,
    )
    candidates = [_candidate("p1", "First"), _candidate("p2", "Second")]
    _patch_search_candidates(monkeypatch, candidates)

    search_query, ai_degraded = asyncio.run(search_pipeline.run_search(db, "실리콘 음극"))

    # The batch call failed, but every individual fallback call succeeded -
    # so the result set is fully enriched and NOT degraded.
    assert ai_degraded is False
    assert search_query.ai_degraded is False
    assert all(r.paper.cathode == "NCA" for r in search_query.results)


def test_run_search_falls_back_to_no_info_when_individual_extraction_fails(monkeypatch, db):
    _patch_ai_defaults(
        monkeypatch,
        batch=_fake_extract_batch_fails,
        individual=_fake_extract_individual_fails,
    )
    _patch_search_candidates(monkeypatch, [_candidate()])

    search_query, ai_degraded = asyncio.run(search_pipeline.run_search(db, "실리콘 음극"))

    assert ai_degraded is True
    paper = search_query.results[0].paper
    assert paper.cathode == ""
    assert paper.extracted_at is None
    assert paper.is_extracted is False


def test_run_search_batch_partial_response_defaults_missing_paper_without_retry(monkeypatch, db):
    async def _fake_batch_partial(papers, gemini_api_key=None):
        # Only the first paper is analyzed - the second is missing from
        # Gemini's response entirely (a JSON-shape slip, not a call failure).
        return {0: {"cathode": "NCA", "anode": "Graphite", "performance_summary": "좋음"}}

    _patch_ai_defaults(
        monkeypatch,
        batch=_fake_batch_partial,
        individual=_fake_extract_individual_must_not_be_called,
    )
    candidates = [_candidate("p1", "First"), _candidate("p2", "Second")]
    _patch_search_candidates(monkeypatch, candidates)

    search_query, ai_degraded = asyncio.run(search_pipeline.run_search(db, "실리콘 음극"))

    assert ai_degraded is True
    by_title = {r.paper.title: r.paper for r in search_query.results}
    assert by_title["First"].cathode == "NCA"
    assert by_title["First"].is_extracted is True
    assert by_title["Second"].cathode == ""
    assert by_title["Second"].is_extracted is False


def test_run_search_skips_already_extracted_papers_in_batch(monkeypatch, db):
    calls = []

    async def _fake_batch_records_calls(papers, gemini_api_key=None):
        calls.append(papers)
        return {i: {"cathode": "NCA"} for i in range(len(papers))}

    _patch_ai_defaults(
        monkeypatch,
        batch=_fake_batch_records_calls,
        individual=_fake_extract_individual_must_not_be_called,
    )
    cached_candidate = _candidate("p1", "Cached Paper")
    new_candidate = _candidate("p2", "New Paper")
    _patch_search_candidates(monkeypatch, [cached_candidate, new_candidate])

    # Pre-seed the cached paper as already extracted.
    cached_paper = search_pipeline._get_or_create_paper(db, cached_candidate)
    search_pipeline._apply_extraction(cached_paper, {"cathode": "LFP"})
    db.commit()

    search_query, ai_degraded = asyncio.run(search_pipeline.run_search(db, "실리콘 음극"))

    assert ai_degraded is False
    # Only the uncached paper's (title, abstract) went to the batch call.
    assert calls == [[("New Paper", "An abstract.")]]
    by_title = {r.paper.title: r.paper for r in search_query.results}
    assert by_title["Cached Paper"].cathode == "LFP"
    assert by_title["New Paper"].cathode == "NCA"


def test_run_search_skips_extraction_when_time_budget_exhausted(monkeypatch, db):
    monkeypatch.setattr(search_pipeline, "_SEARCH_TIME_BUDGET_SECONDS", -100.0)
    _patch_ai_defaults(
        monkeypatch,
        batch=_fake_extract_batch_must_not_be_called,
        individual=_fake_extract_individual_must_not_be_called,
    )
    _patch_search_candidates(monkeypatch, [_candidate()])

    search_query, ai_degraded = asyncio.run(search_pipeline.run_search(db, "실리콘 음극"))

    assert ai_degraded is True
    assert search_query.ai_degraded is True
    # The top-N result set is still returned even though nothing could be
    # AI-enriched in time.
    assert len(search_query.results) == 1
    assert search_query.results[0].paper.is_extracted is False


def test_run_search_sorts_by_year_then_relevance_score(monkeypatch, db):
    async def _fake_rerank_mixed(keyword, candidates, gemini_api_key=None):
        scores = {"old-high-score": 50.0, "new-low-score": 10.0, "new-high-score": 90.0}
        return [(c, scores[c.paper_id], "") for c in candidates]

    _patch_ai_defaults(monkeypatch, rerank=_fake_rerank_mixed, batch=_fake_extract_batch_ok)
    candidates = [
        _candidate("old-high-score", "Old High Score", year=2020),
        _candidate("new-low-score", "New Low Score", year=2023),
        _candidate("new-high-score", "New High Score", year=2023),
    ]
    _patch_search_candidates(monkeypatch, candidates)

    search_query, _ = asyncio.run(search_pipeline.run_search(db, "실리콘 음극"))

    # Newest year first; within the same year (2023), higher score first.
    assert [r.paper.title for r in search_query.results] == [
        "New High Score",
        "New Low Score",
        "Old High Score",
    ]
