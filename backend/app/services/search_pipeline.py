"""Orchestrates the full pipeline:

Keyword (Korean/English/shorthand) -> AI query expansion -> Semantic
Scholar search -> AI re-ranking (Korean reasoning) -> battery metadata
extraction (Korean, batched) -> persisted SearchQuery/SearchResult/Paper
rows.

The whole pipeline is bounded by _SEARCH_TIME_BUDGET_SECONDS: every
Gemini-calling phase is awaited with whatever time remains in the budget,
so a slow/overloaded Gemini degrades the result (raw keyword, Semantic
Scholar's own order, "정보 없음" snapshots) instead of hanging the request.
Semantic Scholar's own call is not budget-wrapped - without it there are no
results to return at all, and it already has its own bounded retry.
"""

import asyncio
import time
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Paper, SearchQuery, SearchResult
from app.services import ai_service, semantic_scholar_service

_SEARCH_TIME_BUDGET_SECONDS = 25.0


def _get_or_create_paper(db: Session, candidate: semantic_scholar_service.Candidate) -> Paper:
    paper = db.query(Paper).filter(Paper.external_paper_id == candidate.paper_id).one_or_none()
    if paper is None:
        paper = Paper(
            external_paper_id=candidate.paper_id,
            title=candidate.title,
            authors=candidate.authors,
            journal=candidate.journal,
            year=candidate.year,
            doi=candidate.doi,
            abstract=candidate.abstract,
        )
        db.add(paper)
        db.flush()
    return paper


def _apply_extraction(paper: Paper, analysis: dict) -> None:
    paper.cathode = analysis.get("cathode", "정보 없음")
    paper.anode = analysis.get("anode", "정보 없음")
    paper.electrolyte = analysis.get("electrolyte", "정보 없음")
    paper.voltage_window = analysis.get("voltage_window", "정보 없음")
    paper.cell_type = analysis.get("cell_type", "정보 없음")
    paper.experimental_conditions = analysis.get("experimental_conditions", "")
    paper.performance_summary = analysis.get("performance_summary", "")
    paper.innovation = analysis.get("innovation", "")
    paper.advantages = analysis.get("advantages", "")
    paper.limitations = analysis.get("limitations", "")
    paper.extracted_at = datetime.now(timezone.utc)


async def _extract_papers_individually(
    papers: list[Paper], gemini_api_key: str | None, deadline: float
) -> bool:
    """Fallback used when the batch extraction call itself fails - the
    same one-call-per-paper behavior the pipeline used before batching.
    Returns True if any paper was left without extraction (a Gemini
    failure, or the time budget running out mid-loop)."""

    degraded = False
    for paper in papers:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return True
        try:
            analysis = await asyncio.wait_for(
                ai_service.extract_battery_analysis(paper.title, paper.abstract, gemini_api_key),
                timeout=remaining,
            )
        except (RuntimeError, TimeoutError):
            degraded = True
            continue
        _apply_extraction(paper, analysis)
    return degraded


async def _extract_papers(
    papers: list[Paper], gemini_api_key: str | None, deadline: float
) -> bool:
    """Fills in battery snapshot/analysis for every not-yet-extracted
    paper, batched into a single Gemini call when possible; falls back to
    one call per paper only if that batch call itself fails. Papers whose
    extraction already succeeded on a previous search (`is_extracted`) are
    reused as-is and never sent to Gemini again.

    Returns True if any paper was left without extraction - `extracted_at`
    is deliberately left unset for those so a later request retries them
    instead of caching the gap forever.
    """

    needs = [p for p in papers if not p.is_extracted]
    if not needs:
        return False

    remaining = deadline - time.monotonic()
    if remaining <= 0:
        return True

    try:
        analyses = await asyncio.wait_for(
            ai_service.extract_battery_analysis_batch(
                [(p.title, p.abstract) for p in needs], gemini_api_key
            ),
            timeout=remaining,
        )
    except (RuntimeError, TimeoutError):
        return await _extract_papers_individually(needs, gemini_api_key, deadline)

    degraded = False
    for i, paper in enumerate(needs):
        if i in analyses:
            _apply_extraction(paper, analyses[i])
        else:
            degraded = True
    return degraded


async def run_search(
    db: Session, keyword: str, gemini_api_key: str | None = None
) -> tuple[SearchQuery, bool]:
    """Run the full pipeline for a keyword and persist the results.

    `gemini_api_key`, when given (e.g. from the caller's X-Gemini-Api-Key
    header), is used for every AI call instead of the server's .env key.

    If Gemini is unavailable or the time budget runs out (RuntimeError or
    TimeoutError from a wait_for-wrapped ai_service call), the pipeline
    degrades gracefully instead of failing the whole search: query
    expansion falls back to the raw keyword, re-ranking falls back to
    Semantic Scholar's own relevance order (score 0, no why_selected), and
    battery analysis falls back to "정보 없음" placeholders. The selected
    top-N results are always returned regardless of degradation. The
    caller is told via the returned `ai_degraded` flag so it can surface a
    notice to the user.

    Returns (SearchQuery with its `results` relationship populated, ordered
    by rank - newest publication year first, relevance score as
    tiebreaker; ai_degraded).
    """

    ai_degraded = False
    deadline = time.monotonic() + _SEARCH_TIME_BUDGET_SECONDS

    remaining = deadline - time.monotonic()
    if remaining <= 0:
        english_query = keyword
        ai_degraded = True
    else:
        try:
            english_query, _expanded_terms = await asyncio.wait_for(
                ai_service.expand_search_query(keyword, gemini_api_key), timeout=remaining
            )
        except (RuntimeError, TimeoutError):
            english_query = keyword
            ai_degraded = True

    candidates = await semantic_scholar_service.search_candidates(english_query)
    if not candidates:
        raise ValueError(f"'{keyword}'에 대한 논문을 찾을 수 없습니다.")

    remaining = deadline - time.monotonic()
    if remaining <= 0:
        ranked = [(candidate, 0.0, "") for candidate in candidates]
        ai_degraded = True
    else:
        try:
            ranked = await asyncio.wait_for(
                ai_service.rerank_candidates(keyword, candidates, gemini_api_key), timeout=remaining
            )
        except (RuntimeError, TimeoutError):
            ranked = [(candidate, 0.0, "") for candidate in candidates]
            ai_degraded = True

    # Candidate SELECTION stays relevance-score-driven (top_n_results by
    # AI score, or Semantic Scholar's own order when degraded); only the
    # final display order changes: newest year first, relevance score as
    # tiebreaker for same-year papers. Missing year sorts last.
    top = ranked[: settings.top_n_results]
    top = sorted(top, key=lambda t: (t[0].year or 0, t[1]), reverse=True)

    search_query = SearchQuery(keyword=keyword, expanded_query=english_query)
    db.add(search_query)
    db.flush()

    papers = [_get_or_create_paper(db, candidate) for candidate, _, _ in top]
    extraction_degraded = await _extract_papers(papers, gemini_api_key, deadline)
    ai_degraded = ai_degraded or extraction_degraded

    for rank, ((_, score, why_selected), paper) in enumerate(zip(top, papers), start=1):
        db.add(
            SearchResult(
                search_query_id=search_query.id,
                paper_id=paper.id,
                rank=rank,
                relevance_score=score,
                why_selected=why_selected,
            )
        )

    search_query.ai_degraded = ai_degraded
    db.commit()
    db.refresh(search_query)
    return search_query, ai_degraded
