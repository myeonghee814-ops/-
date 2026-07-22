"""Unit tests for search_pipeline.py:

- graceful degradation when a Gemini call (query expansion, or the
  combined re-ranking + battery extraction call) fails or the time budget
  runs out - the pipeline should still return a usable result instead of
  failing the whole search, and report `ai_degraded=True` so the caller
  can surface a notice.
- re-ranking and battery extraction sharing one Gemini call/response, with
  already-extracted papers never having that response's battery_info
  applied to them (but still sent through re-ranking, since relevance is
  query-specific and can't be cached) - and the final (year desc,
  relevance score desc) sort.
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


async def _fake_expand_ok(keyword, gemini_api_key=None, focus_hint=None):
    return f"expanded {keyword}", ["term"]


async def _fake_expand_fails(keyword, gemini_api_key=None, focus_hint=None):
    raise RuntimeError("AI 검색어 확장에 실패했습니다: 503")


async def _fake_rerank_ok(keyword, candidates, gemini_api_key=None):
    return [
        (c, 90.0, "관련성이 높습니다.", {"cathode": "NCA", "anode": "Graphite", "result_summary": "좋음"})
        for c in candidates
    ]


async def _fake_rerank_fails(keyword, candidates, gemini_api_key=None):
    raise RuntimeError("AI 재순위화/정보추출에 실패했습니다: 503")


def _patch_search_candidates(monkeypatch, candidates):
    async def _fake(query, max_results=None):
        return candidates

    monkeypatch.setattr(search_pipeline.semantic_scholar_service, "search_candidates", _fake)


def _patch_ai_defaults(monkeypatch, *, expand=_fake_expand_ok, rerank=_fake_rerank_ok):
    monkeypatch.setattr(search_pipeline.ai_service, "expand_search_query", expand)
    monkeypatch.setattr(search_pipeline.ai_service, "rerank_and_extract_candidates", rerank)


# --- _api_search_query --------------------------------------------------------


def test_api_search_query_appends_battery_context_suffix():
    """Every outgoing Semantic Scholar query gets the battery-context
    suffix appended, regardless of source - disambiguates acronyms that
    mean something else in other fields (e.g. "FEC" = fluoroethylene
    carbonate here, forward error correction in networking)."""

    assert search_pipeline._api_search_query("FEC") == "FEC lithium-ion battery electrolyte"


def test_api_search_query_appends_suffix_after_hangul_and_boolean_stripping():
    result = search_pipeline._api_search_query('("Mid-Ni" OR "고전압")')
    assert result == "Mid-Ni lithium-ion battery electrolyte"


def test_run_search_happy_path_not_degraded(monkeypatch, db):
    _patch_ai_defaults(monkeypatch)
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

    _patch_ai_defaults(monkeypatch, expand=_fake_expand_fails)
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
    _patch_ai_defaults(monkeypatch, expand=_fake_expand_fails)

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

    async def _fake_expand_boolean_syntax(keyword, gemini_api_key=None, focus_hint=None):
        return (
            '("NCM613" OR "NCM 613" OR "NMC613") AND ("high voltage" OR "고전압")',
            ["NCM613", "high voltage"],
        )

    captured_queries = []

    async def _fake_search(query, max_results=None):
        captured_queries.append(query)
        return [_candidate()]

    monkeypatch.setattr(search_pipeline.semantic_scholar_service, "search_candidates", _fake_search)
    _patch_ai_defaults(monkeypatch, expand=_fake_expand_boolean_syntax)

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


# --- additive/solvent chemical-category expansion -----------------------------


def test_run_search_expands_additive_category_via_gemini(monkeypatch, db):
    """A category/family reference in the additive/solvent field (e.g.
    "불소계") must be expanded into specific compound names before it
    reaches Semantic Scholar - the bare category word matches no real
    paper's text, same failure mode as any other untranslated Hangul."""

    async def _fake_expand_category(category_text, gemini_api_key=None):
        assert category_text == "불소계"
        return ["LiFSI", "FEC", "LiPF6"]

    captured_queries = []

    async def _fake_search(query, max_results=None):
        captured_queries.append(query)
        return [_candidate()]

    monkeypatch.setattr(search_pipeline.ai_service, "expand_compound_category", _fake_expand_category)
    monkeypatch.setattr(search_pipeline.semantic_scholar_service, "search_candidates", _fake_search)
    _patch_ai_defaults(monkeypatch)

    search_query, ai_degraded = asyncio.run(
        search_pipeline.run_search(db, "NCA", additive_or_solvent="불소계")
    )

    assert ai_degraded is False
    assert search_query.additive_notice == "'불소계' → LiFSI, FEC, LiPF6 등으로 확장하여 검색했습니다."
    assert search_query.additive_notice_level == "info"
    assert "불소계" not in search_query.keyword
    assert "LiFSI" in search_query.keyword
    api_query = captured_queries[0]
    assert "LiFSI" in api_query and "FEC" in api_query and "LiPF6" in api_query


def test_run_search_falls_back_to_category_dictionary_when_gemini_unavailable(monkeypatch, db):
    async def _fake_expand_category_fails(category_text, gemini_api_key=None):
        raise RuntimeError("AI 화합물 계열 확장에 실패했습니다: 503")

    monkeypatch.setattr(
        search_pipeline.ai_service, "expand_compound_category", _fake_expand_category_fails
    )
    _patch_ai_defaults(monkeypatch)
    _patch_search_candidates(monkeypatch, [_candidate()])

    search_query, ai_degraded = asyncio.run(
        search_pipeline.run_search(db, "NCA", additive_or_solvent="불소계")
    )

    assert ai_degraded is True
    assert search_query.additive_notice_level == "info"
    assert "LiFSI" in search_query.additive_notice
    assert "LiFSI" in search_query.keyword


def test_run_search_warns_when_category_has_no_fallback_and_gemini_fails(monkeypatch, db):
    async def _fake_expand_category_fails(category_text, gemini_api_key=None):
        raise RuntimeError("AI 화합물 계열 확장에 실패했습니다: 503")

    monkeypatch.setattr(
        search_pipeline.ai_service, "expand_compound_category", _fake_expand_category_fails
    )
    _patch_ai_defaults(monkeypatch)
    _patch_search_candidates(monkeypatch, [_candidate()])

    search_query, ai_degraded = asyncio.run(
        search_pipeline.run_search(db, "NCA", additive_or_solvent="이상한계열")
    )

    assert ai_degraded is True
    assert search_query.additive_notice_level == "warning"
    assert "이상한계열" in search_query.keyword


def test_run_search_skips_category_expansion_for_a_specific_compound(monkeypatch, db):
    """A specific compound name (not a category) must never trigger the
    extra Gemini call at all - only category-like phrasing should."""

    async def _must_not_be_called(category_text, gemini_api_key=None):
        raise AssertionError("expand_compound_category should not be called for a specific compound")

    monkeypatch.setattr(search_pipeline.ai_service, "expand_compound_category", _must_not_be_called)
    _patch_ai_defaults(monkeypatch)
    _patch_search_candidates(monkeypatch, [_candidate()])

    search_query, ai_degraded = asyncio.run(
        search_pipeline.run_search(db, "NCA", additive_or_solvent="LiFSI")
    )

    assert ai_degraded is False
    assert search_query.additive_notice == ""
    assert search_query.additive_notice_level == ""
    assert "LiFSI" in search_query.keyword


def test_run_search_retries_with_material_only_when_full_query_returns_zero(monkeypatch, db):
    """Regression test: Semantic Scholar's relevance search can return 0
    candidates for a query with several specific terms even though smaller
    subsets return plenty - observed live, a material name plus 4 compound
    names from additive-category expansion returned 0, but every 4-term
    subset of that same 5-term query returned several. Retrying on just the
    material term (the one field guaranteed to be a real chemistry term) is
    a cheap second chance before giving up entirely."""

    captured_queries = []

    async def _fake_search(query, max_results=None):
        captured_queries.append(query)
        return [_candidate()] if query.startswith("NCA ") else []

    async def _fake_expand_category(category_text, gemini_api_key=None):
        return ["FEC", "LiFSI", "LiTFSI", "DFEC"]

    monkeypatch.setattr(search_pipeline.semantic_scholar_service, "search_candidates", _fake_search)
    monkeypatch.setattr(search_pipeline.ai_service, "expand_compound_category", _fake_expand_category)
    _patch_ai_defaults(monkeypatch)

    search_query, ai_degraded = asyncio.run(
        search_pipeline.run_search(db, "NCA", additive_or_solvent="불소계")
    )

    assert len(captured_queries) == 2
    assert not captured_queries[0].startswith("NCA ")
    assert captured_queries[1].startswith("NCA ")
    assert len(search_query.results) == 1


# --- additive-only mode (material empty, additive_or_solvent given) -----------


async def _fake_rerank_electrolyte_mixed(keyword, candidates, gemini_api_key=None):
    """Both candidates get the SAME relevance_score from Gemini - only
    their extracted electrolyte field differs, isolating the score
    adjustment itself from Gemini's own (independent) relevance judgment."""

    infos = {
        "p1": {"electrolyte": "1M LiPF6 in EC/DMC with 5wt% FEC additive"},
        "p2": {"electrolyte": "1M LiPF6 in EC/DEC"},
    }
    return [(c, 70.0, "", infos[c.paper_id]) for c in candidates]


def test_run_search_additive_only_mode_passes_focus_hint(monkeypatch, db):
    captured = {}

    async def _fake_expand_capture(keyword, gemini_api_key=None, focus_hint=None):
        captured["focus_hint"] = focus_hint
        return f"expanded {keyword}", ["term"]

    _patch_ai_defaults(monkeypatch, expand=_fake_expand_capture)
    _patch_search_candidates(monkeypatch, [_candidate()])

    asyncio.run(search_pipeline.run_search(db, "", additive_or_solvent="FEC"))

    assert captured["focus_hint"] == search_pipeline._ADDITIVE_ONLY_QUERY_FOCUS_HINT


def test_run_search_with_material_omits_focus_hint(monkeypatch, db):
    """Regression: giving a material must NOT trigger additive-only mode,
    even when additive_or_solvent is also given."""

    captured = {}

    async def _fake_expand_capture(keyword, gemini_api_key=None, focus_hint=None):
        captured["focus_hint"] = focus_hint
        return f"expanded {keyword}", ["term"]

    _patch_ai_defaults(monkeypatch, expand=_fake_expand_capture)
    _patch_search_candidates(monkeypatch, [_candidate()])

    asyncio.run(search_pipeline.run_search(db, "NCA", additive_or_solvent="FEC"))

    assert captured["focus_hint"] is None


def test_run_search_additive_only_mode_boosts_electrolyte_mentioning_candidate(monkeypatch, db):
    """When searching by additive alone (no material), a candidate whose
    extracted electrolyte field actually mentions the additive should
    outrank one whose extracted electrolyte field doesn't - even though
    Gemini's own relevance_score was identical for both (e.g. because the
    second paper uses the compound for something unrelated, like a coating
    agent, which its electrolyte field naturally wouldn't mention)."""

    _patch_ai_defaults(monkeypatch, rerank=_fake_rerank_electrolyte_mixed)
    candidates = [_candidate("p1", "Uses FEC in electrolyte"), _candidate("p2", "Uses FEC as coating agent")]
    _patch_search_candidates(monkeypatch, candidates)

    search_query, ai_degraded = asyncio.run(search_pipeline.run_search(db, "", additive_or_solvent="FEC"))

    assert ai_degraded is False
    titles = [r.paper.title for r in search_query.results]
    assert titles == ["Uses FEC in electrolyte", "Uses FEC as coating agent"]
    scores = {r.paper.title: r.relevance_score for r in search_query.results}
    assert scores["Uses FEC in electrolyte"] == 70.0 + search_pipeline._ADDITIVE_CONTEXT_SCORE_BOOST
    assert scores["Uses FEC as coating agent"] == 70.0 - search_pipeline._ADDITIVE_CONTEXT_SCORE_PENALTY


def test_run_search_with_material_skips_additive_context_adjustment(monkeypatch, db):
    """Regression: when a material IS given, the additive-context score
    adjustment must not run at all - both candidates keep Gemini's own
    (identical) relevance_score untouched, regardless of what their
    extracted electrolyte field says."""

    _patch_ai_defaults(monkeypatch, rerank=_fake_rerank_electrolyte_mixed)
    candidates = [_candidate("p1", "First"), _candidate("p2", "Second")]
    _patch_search_candidates(monkeypatch, candidates)

    search_query, ai_degraded = asyncio.run(search_pipeline.run_search(db, "NCA", additive_or_solvent="FEC"))

    assert ai_degraded is False
    assert all(r.relevance_score == 70.0 for r in search_query.results)


def test_run_search_falls_back_to_original_order_when_reranking_fails(monkeypatch, db):
    """Full degradation (re-ranking itself failed, every score is 0) must
    keep Semantic Scholar's own order verbatim - NOT re-sort by year, even
    though the older paper happens to come first here."""

    _patch_ai_defaults(monkeypatch, rerank=_fake_rerank_fails)
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

    async def _fake_expand_silicon(keyword, gemini_api_key=None, focus_hint=None):
        return "silicon anode SEI", ["silicon anode", "SEI"]

    _patch_ai_defaults(
        monkeypatch, expand=_fake_expand_silicon, rerank=_fake_rerank_fails
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


def test_run_search_demotes_off_domain_candidate_below_lexically_unrelated_one(monkeypatch, db):
    """Regression test for the FEC acronym-collision scenario: a networking
    paper that happens to lexically overlap with the query term ("FEC")
    must still sink below a candidate with NO overlap at all, once an
    OFF_DOMAIN_KEYWORDS match is detected - lexical overlap alone isn't
    enough to trust a candidate is actually on-topic."""

    async def _fake_expand_fec(keyword, gemini_api_key=None, focus_hint=None):
        return "FEC battery electrolyte", ["FEC"]

    _patch_ai_defaults(
        monkeypatch, expand=_fake_expand_fec, rerank=_fake_rerank_fails
    )
    networking = semantic_scholar_service.Candidate(
        paper_id="p1",
        title="FEC schemes for wireless network reliability",
        authors="Author A",
        journal="Journal X",
        year=2024,
        doi="10.1/x",
        abstract="Forward error correction (FEC) improves packet loss resilience.",
    )
    unrelated = semantic_scholar_service.Candidate(
        paper_id="p2",
        title="A cooking recipe archive",
        authors="Author B",
        journal="Journal Y",
        year=2023,
        doi="10.1/y",
        abstract="A collection of recipes for home cooking, unrelated to any technical field.",
    )
    battery = semantic_scholar_service.Candidate(
        paper_id="p3",
        title="FEC additive for lithium-ion battery electrolyte stabilization",
        authors="Author C",
        journal="Journal Z",
        year=2022,
        doi="10.1/z",
        abstract="Fluoroethylene carbonate (FEC) improves SEI formation on the anode.",
    )
    _patch_search_candidates(monkeypatch, [networking, unrelated, battery])

    search_query, ai_degraded = asyncio.run(search_pipeline.run_search(db, "FEC"))

    assert ai_degraded is True
    assert [r.paper.title for r in search_query.results] == [battery.title, unrelated.title, networking.title]


def test_run_search_falls_back_to_no_info_when_reranking_fails(monkeypatch, db):
    """Re-ranking and extraction now share one Gemini call - when it fails
    there is no separate extraction attempt to fall back to, so a
    not-yet-cached paper is simply left with empty placeholder fields."""

    _patch_ai_defaults(monkeypatch, rerank=_fake_rerank_fails)
    _patch_search_candidates(monkeypatch, [_candidate()])

    search_query, ai_degraded = asyncio.run(search_pipeline.run_search(db, "실리콘 음극"))

    assert ai_degraded is True
    paper = search_query.results[0].paper
    assert paper.cathode == ""
    assert paper.extracted_at is None
    assert paper.is_extracted is False


def test_run_search_applies_partial_battery_fields_with_defaults(monkeypatch, db):
    """A ranking entry that omits some battery-info keys (a JSON-shape
    slip, not a call failure) still gets its present fields applied and is
    marked extracted - _apply_extraction's own .get() defaults fill in the
    rest, same as before the merge."""

    async def _fake_rerank_partial(keyword, candidates, gemini_api_key=None):
        return [(c, 90.0, "", {"cathode": "NCA"}) for c in candidates]

    _patch_ai_defaults(monkeypatch, rerank=_fake_rerank_partial)
    _patch_search_candidates(monkeypatch, [_candidate()])

    search_query, ai_degraded = asyncio.run(search_pipeline.run_search(db, "실리콘 음극"))

    assert ai_degraded is False
    paper = search_query.results[0].paper
    assert paper.cathode == "NCA"
    assert paper.electrolyte == "정보 없음"
    assert paper.is_extracted is True


def test_run_search_does_not_overwrite_already_extracted_papers(monkeypatch, db):
    calls = []

    async def _fake_rerank_records_calls(keyword, candidates, gemini_api_key=None):
        calls.append(candidates)
        return [(c, 90.0, "", {"cathode": "NCA"}) for c in candidates]

    _patch_ai_defaults(monkeypatch, rerank=_fake_rerank_records_calls)
    cached_candidate = _candidate("p1", "Cached Paper")
    new_candidate = _candidate("p2", "New Paper")
    _patch_search_candidates(monkeypatch, [cached_candidate, new_candidate])

    # Pre-seed the cached paper as already extracted.
    cached_paper = search_pipeline._get_or_create_paper(db, cached_candidate)
    search_pipeline._apply_extraction(cached_paper, {"cathode": "LFP"})
    db.commit()

    search_query, ai_degraded = asyncio.run(search_pipeline.run_search(db, "실리콘 음극"))

    assert ai_degraded is False
    # Both candidates still go through re-ranking (relevance is
    # query-specific and can't be cached) - only applying the battery_info
    # is skipped for the already-extracted one.
    assert len(calls) == 1
    assert {c.title for c in calls[0]} == {"Cached Paper", "New Paper"}
    by_title = {r.paper.title: r.paper for r in search_query.results}
    assert by_title["Cached Paper"].cathode == "LFP"
    assert by_title["New Paper"].cathode == "NCA"


def test_run_search_skips_extraction_when_time_budget_exhausted(monkeypatch, db):
    monkeypatch.setattr(search_pipeline, "_SEARCH_TIME_BUDGET_SECONDS", -100.0)
    _patch_ai_defaults(monkeypatch)
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
        return [(c, scores[c.paper_id], "", {}) for c in candidates]

    _patch_ai_defaults(monkeypatch, rerank=_fake_rerank_mixed)
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
        return [(c, scores[c.paper_id], "", {}) for c in candidates]

    _patch_ai_defaults(monkeypatch, rerank=_fake_rerank_mixed)
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

    _patch_ai_defaults(monkeypatch, rerank=_fake_rerank_fails)
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
