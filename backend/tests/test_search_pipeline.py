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
import re

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.services import pdf_extract, search_pipeline, semantic_scholar_service

_HANGUL_RE = re.compile(r"[가-힣]+")


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
    return {"cathode": "NCA", "anode": "Graphite", "result_summary": "좋음"}


async def _fake_extract_individual_fails(title, abstract, gemini_api_key=None):
    raise RuntimeError("AI 배터리 정보 추출에 실패했습니다: 503")


async def _fake_extract_individual_must_not_be_called(title, abstract, gemini_api_key=None):
    raise AssertionError("individual extraction should not be called")


async def _fake_extract_batch_ok(papers, gemini_api_key=None):
    return {
        i: {"cathode": "NCA", "anode": "Graphite", "result_summary": "좋음"}
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


def test_run_search_falls_back_to_dictionary_when_expansion_fails(monkeypatch, db):
    """Query expansion failure must NOT fall back to the raw Korean
    keyword - it should use battery_term_mapping's static dictionary
    instead, so Semantic Scholar still gets an accurate English query."""

    _patch_ai_defaults(monkeypatch, expand=_fake_expand_fails, batch=_fake_extract_batch_ok)
    _patch_search_candidates(monkeypatch, [_candidate()])

    search_query, ai_degraded = asyncio.run(search_pipeline.run_search(db, "실리콘 음극"))

    assert ai_degraded is True
    assert search_query.ai_degraded is True
    assert search_query.expanded_query == "silicon anode"
    assert len(search_query.results) == 1


def test_run_search_strips_unmapped_hangul_from_the_semantic_scholar_query(monkeypatch, db):
    """Regression test for [버그 3]: battery_term_mapping.expand_with_dictionary
    deliberately keeps a TERM_MAP-less Korean word (e.g. "고전압") in the
    *display* expanded_query instead of dropping it - but that same literal
    Hangul must never reach Semantic Scholar's English-only index as part
    of the actual search string, or it starves the candidate pool (40
    candidates collapsing to 1 was the originally observed symptom). The
    two are now separate: the API call gets a Hangul-stripped query, while
    expanded_query keeps showing the untranslated word to the user."""

    captured_queries = []

    async def _fake_search(query, max_results=None):
        captured_queries.append(query)
        return [_candidate()]

    monkeypatch.setattr(search_pipeline.semantic_scholar_service, "search_candidates", _fake_search)
    _patch_ai_defaults(monkeypatch, expand=_fake_expand_fails, batch=_fake_extract_batch_ok)

    search_query, ai_degraded = asyncio.run(
        search_pipeline.run_search(db, "Mid-Ni 고전압 Sulfur additive")
    )

    assert ai_degraded is True
    assert len(captured_queries) == 1
    api_query = captured_queries[0]
    assert not _HANGUL_RE.search(api_query), f"Hangul leaked into the Semantic Scholar query: {api_query!r}"
    assert "Mid-Ni" in api_query
    assert "Sulfur additive" in api_query
    # The display query still keeps the unmapped Korean word - only the
    # outgoing API string was cleaned, not the user-facing one.
    assert "고전압" in search_query.expanded_query


def test_run_search_strips_boolean_query_syntax_from_gemini_expansion(monkeypatch, db):
    """Regression test: Semantic Scholar's plain relevance-search endpoint
    (what search_candidates() calls) has no boolean query syntax - Gemini's
    query expansion used to be free to produce '("term1" OR "term2") AND
    "term3"'-style output for synonym grouping, which the endpoint then
    matches as literal quote/paren/AND/OR text instead of an actual boolean
    query, returning zero candidates even though every individual term would
    have matched plenty on its own. This was the real cause of at least one
    previously-unexplained "no results" search."""

    async def _fake_expand_boolean_syntax(keyword, gemini_api_key=None):
        return (
            '("NCM613" OR "NCM 613" OR "NMC613") AND ("high voltage" OR "고전압")',
            ["NCM613", "high voltage"],
        )

    captured_queries = []

    async def _fake_search(query, max_results=None):
        captured_queries.append(query)
        return [_candidate()]

    monkeypatch.setattr(search_pipeline.semantic_scholar_service, "search_candidates", _fake_search)
    _patch_ai_defaults(monkeypatch, expand=_fake_expand_boolean_syntax, batch=_fake_extract_batch_ok)

    search_query, ai_degraded = asyncio.run(search_pipeline.run_search(db, "NCM613 고전압"))

    assert ai_degraded is False
    assert len(captured_queries) == 1
    api_query = captured_queries[0]
    assert '"' not in api_query and "'" not in api_query
    assert "(" not in api_query and ")" not in api_query
    assert not re.search(r"\b(?:AND|OR)\b", api_query, re.IGNORECASE)
    assert not _HANGUL_RE.search(api_query)
    assert "NCM613" in api_query
    assert "NMC613" in api_query
    assert "high voltage" in api_query
    # Display query is untouched - only the outgoing API string was cleaned.
    assert search_query.expanded_query == (
        '("NCM613" OR "NCM 613" OR "NMC613") AND ("high voltage" OR "고전압")'
    )


def test_run_search_falls_back_to_original_order_when_reranking_fails(monkeypatch, db):
    """Full degradation (re-ranking itself failed, every score is 0) must
    keep Semantic Scholar's own order verbatim - NOT re-sort by year, even
    though the older paper happens to come first here."""

    _patch_ai_defaults(monkeypatch, rerank=_fake_rerank_fails, batch=_fake_extract_batch_ok)
    candidates = [
        _candidate("p1", "First", year=2018),
        _candidate("p2", "Second", year=2024),
    ]
    _patch_search_candidates(monkeypatch, candidates)

    search_query, ai_degraded = asyncio.run(search_pipeline.run_search(db, "실리콘 음극"))

    assert ai_degraded is True
    assert [r.paper.title for r in search_query.results] == ["First", "Second"]
    assert all(r.relevance_score == 0.0 for r in search_query.results)
    assert all(r.why_selected == "" for r in search_query.results)


def test_run_search_demotes_lexically_unrelated_candidates_when_reranking_fails(monkeypatch, db):
    """The relevance safety net: when re-ranking fails, a candidate whose
    title/abstract shares no vocabulary with the expanded search terms
    should sink below one that does, even if Semantic Scholar returned it
    first."""

    async def _fake_expand_silicon(keyword, gemini_api_key=None):
        return "silicon anode SEI", ["silicon anode", "SEI"]

    _patch_ai_defaults(
        monkeypatch, expand=_fake_expand_silicon, rerank=_fake_rerank_fails, batch=_fake_extract_batch_ok
    )
    unrelated = semantic_scholar_service.Candidate(
        paper_id="p1",
        title="Recyclable packaging for consumer electronics",
        authors="Author A",
        journal="Journal X",
        year=2024,
        doi="10.1/x",
        abstract="A study on packaging materials with no relation to batteries.",
    )
    related = semantic_scholar_service.Candidate(
        paper_id="p2",
        title="Silicon anode SEI stabilization via novel binder",
        authors="Author B",
        journal="Journal Y",
        year=2020,
        doi="10.1/y",
        abstract="This paper studies SEI formation on silicon anodes.",
    )
    _patch_search_candidates(monkeypatch, [unrelated, related])

    search_query, ai_degraded = asyncio.run(search_pipeline.run_search(db, "실리콘 음극 SEI"))

    assert ai_degraded is True
    assert [r.paper.title for r in search_query.results] == [related.title, unrelated.title]


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
        return {0: {"cathode": "NCA", "anode": "Graphite", "result_summary": "좋음"}}

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


def test_run_search_sorts_by_relevance_score_then_year(monkeypatch, db):
    """When re-ranking succeeds, relevance score is the primary sort key -
    a highly-relevant older paper must outrank a less-relevant newer one.
    Year only breaks ties between equal scores."""

    async def _fake_rerank_mixed(keyword, candidates, gemini_api_key=None):
        scores = {"old-high-score": 90.0, "new-low-score": 10.0, "new-tied-score": 50.0, "old-tied-score": 50.0}
        return [(c, scores[c.paper_id], "") for c in candidates]

    _patch_ai_defaults(monkeypatch, rerank=_fake_rerank_mixed, batch=_fake_extract_batch_ok)
    candidates = [
        _candidate("new-low-score", "New Low Score", year=2024),
        _candidate("old-high-score", "Old High Score", year=2018),
        _candidate("old-tied-score", "Old Tied Score", year=2020),
        _candidate("new-tied-score", "New Tied Score", year=2023),
    ]
    _patch_search_candidates(monkeypatch, candidates)

    search_query, _ = asyncio.run(search_pipeline.run_search(db, "실리콘 음극"))

    # Highest score first regardless of year; among the tied 50.0 scores,
    # the newer paper (2023) outranks the older one (2020).
    assert [r.paper.title for r in search_query.results] == [
        "Old High Score",
        "New Tied Score",
        "Old Tied Score",
        "New Low Score",
    ]
    assert search_query.sort_by == "relevance"


def test_run_search_sort_by_recency_prioritizes_year_then_score(monkeypatch, db):
    """sort_by="recency" flips the priority: year desc first, relevance
    score desc only breaks ties within the same year. Both signals are
    still considered either way - only which one wins ties changes."""

    async def _fake_rerank_mixed(keyword, candidates, gemini_api_key=None):
        scores = {"new-low-score": 10.0, "old-high-score": 90.0, "old-tied-score": 50.0, "new-tied-score": 50.0}
        return [(c, scores[c.paper_id], "") for c in candidates]

    _patch_ai_defaults(monkeypatch, rerank=_fake_rerank_mixed, batch=_fake_extract_batch_ok)
    candidates = [
        _candidate("old-high-score", "Old High Score", year=2018),
        _candidate("new-low-score", "New Low Score", year=2024),
        _candidate("old-tied-score", "Old Tied Score", year=2020),
        _candidate("new-tied-score", "New Tied Score", year=2020),
    ]
    _patch_search_candidates(monkeypatch, candidates)

    search_query, _ = asyncio.run(
        search_pipeline.run_search(db, "실리콘 음극", sort_by="recency")
    )

    # Newest year (2024) first even though its score is lowest; among the
    # two 2020 papers, the higher score (50.0 tie -> insertion order kept
    # since both tie) still applies as the tiebreaker signal, but 2018's
    # 90.0 score does NOT let it jump ahead of any newer-year paper.
    assert [r.paper.title for r in search_query.results] == [
        "New Low Score",
        "Old Tied Score",
        "New Tied Score",
        "Old High Score",
    ]
    assert search_query.sort_by == "recency"


def test_run_search_sort_by_is_ignored_when_reranking_fails(monkeypatch, db):
    """The fully-degraded case (re-ranking itself failed) must keep
    Semantic Scholar's own order regardless of sort_by - not resorted by
    year even when sort_by="recency" was explicitly requested."""

    _patch_ai_defaults(monkeypatch, rerank=_fake_rerank_fails, batch=_fake_extract_batch_ok)
    candidates = [
        _candidate("p1", "First", year=2018),
        _candidate("p2", "Second", year=2024),
    ]
    _patch_search_candidates(monkeypatch, candidates)

    search_query, ai_degraded = asyncio.run(
        search_pipeline.run_search(db, "실리콘 음극", sort_by="recency")
    )

    assert ai_degraded is True
    assert [r.paper.title for r in search_query.results] == ["First", "Second"]


# --- run_deep_analysis --------------------------------------------------------


def test_run_deep_analysis_downloads_pdf_and_stores_result(monkeypatch, db):
    candidate = _candidate("p1", "Paper")
    paper = search_pipeline._get_or_create_paper(db, candidate)
    paper.open_access_pdf_url = "https://example.com/paper.pdf"
    db.commit()

    async def _fake_download_and_extract(url):
        assert url == "https://example.com/paper.pdf"
        return pdf_extract.ExtractedPaper(
            body_text="Full body text with methods and results.",
            candidate_figure_captions=["Figure 1. Cycling performance."],
        )

    async def _fake_extract_deep_analysis(title, body_text, captions, gemini_api_key=None):
        assert title == "Paper"
        assert body_text == "Full body text with methods and results."
        assert captions == ["Figure 1. Cycling performance."]
        return {
            "base_electrolyte": "1M LiPF6 in EC/DMC",
            "test_electrolyte": "1M LiPF6 in EC/DMC + 2wt% FEC",
            "voltage_range": "3.0-4.3 V",
            "cell_type_detail": "coin cell (half-cell)",
            "key_findings": "FEC 첨가 시 용량 유지율이 개선되었습니다.",
            "summary": "FEC의 SEI 안정화 효과를 확인한 연구입니다.",
        }

    monkeypatch.setattr(pdf_extract, "download_and_extract", _fake_download_and_extract)
    monkeypatch.setattr(search_pipeline.ai_service, "extract_deep_analysis", _fake_extract_deep_analysis)

    result = asyncio.run(search_pipeline.run_deep_analysis(db, paper))

    assert result.is_deep_analyzed is True
    assert result.deep_base_electrolyte == "1M LiPF6 in EC/DMC"
    assert result.deep_test_electrolyte == "1M LiPF6 in EC/DMC + 2wt% FEC"
    assert result.deep_voltage_range == "3.0-4.3 V"
    assert result.deep_cell_type_detail == "coin cell (half-cell)"
    assert result.deep_key_findings == "FEC 첨가 시 용량 유지율이 개선되었습니다."
    assert result.deep_summary == "FEC의 SEI 안정화 효과를 확인한 연구입니다."
    assert result.deep_analyzed_at is not None


def test_run_deep_analysis_propagates_pdf_extraction_failure(monkeypatch, db):
    candidate = _candidate("p1", "Paper")
    paper = search_pipeline._get_or_create_paper(db, candidate)
    paper.open_access_pdf_url = "https://example.com/paper.pdf"
    db.commit()

    async def _fake_download_fails(url):
        raise pdf_extract.PdfExtractionError("PDF를 다운로드할 수 없습니다: connection reset")

    monkeypatch.setattr(pdf_extract, "download_and_extract", _fake_download_fails)

    with pytest.raises(pdf_extract.PdfExtractionError):
        asyncio.run(search_pipeline.run_deep_analysis(db, paper))

    assert paper.is_deep_analyzed is False


def test_run_deep_analysis_propagates_gemini_failure(monkeypatch, db):
    candidate = _candidate("p1", "Paper")
    paper = search_pipeline._get_or_create_paper(db, candidate)
    paper.open_access_pdf_url = "https://example.com/paper.pdf"
    db.commit()

    async def _fake_download_and_extract(url):
        return pdf_extract.ExtractedPaper(body_text="Full text", candidate_figure_captions=[])

    async def _fake_extract_deep_analysis_fails(title, body_text, captions, gemini_api_key=None):
        raise RuntimeError("AI 심층 분석에 실패했습니다: 503")

    monkeypatch.setattr(pdf_extract, "download_and_extract", _fake_download_and_extract)
    monkeypatch.setattr(
        search_pipeline.ai_service, "extract_deep_analysis", _fake_extract_deep_analysis_fails
    )

    with pytest.raises(RuntimeError):
        asyncio.run(search_pipeline.run_deep_analysis(db, paper))

    assert paper.is_deep_analyzed is False
