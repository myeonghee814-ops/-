"""Orchestrates the full pipeline:

Keyword (Korean/English/shorthand) -> AI query expansion -> Semantic
Scholar search -> AI re-ranking (Korean reasoning) -> battery metadata
extraction (Korean, batched) -> persisted SearchQuery/SearchResult/Paper
rows.

The whole pipeline is bounded by _SEARCH_TIME_BUDGET_SECONDS: every
Gemini-calling phase is awaited with whatever time remains in the budget,
so a slow/overloaded Gemini degrades the result instead of hanging the
request. Two stages have a non-Gemini fallback instead of just giving up:
- query expansion falls back to `battery_term_mapping`'s static Korean ->
  English dictionary instead of sending raw Korean text to Semantic
  Scholar's English-only index. Any Korean word the dictionary has no
  entry for is kept as a literal token (never silently dropped) and
  logged, so TERM_MAP gaps are discoverable from real traffic.
- re-ranking falls back to `local_reranker`'s BM25 scoring (title+abstract
  vs the expanded query terms) instead of just handing back Semantic
  Scholar's own order - `_apply_relevance_safety_filter`'s lexical-overlap
  demotion still runs on top as an independent second safety net, in case
  BM25 itself misbehaves.
Both fallback stages log a distinct "falling back to..." line on entry -
grepping for that text over time is a proxy for how often Gemini itself
is failing (quota, overload, or the search time budget).
Battery metadata extraction still falls back to plain "정보 없음"
placeholders - there is no non-AI substitute for reading an abstract. Its
prompt is deliberately light (cathode/anode/electrolyte/voltage_window/
cell_type, experimental_conditions, and one merged result_summary instead
of four separate narrative fields) so each call is faster and less likely
to be the one that runs into a timeout or 503 in the first place.
Semantic Scholar's own call is not budget-wrapped - without it there are no
results to return at all, and it already has its own bounded retry.
"""

import asyncio
import logging
import re
import time
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Paper, SearchQuery, SearchResult
from app.services import ai_service, battery_term_mapping, local_reranker, semantic_scholar_service

logger = logging.getLogger(__name__)

# Gemini's own 503 ("high demand") retry policy waits at least
# _MIN_RETRY_DELAY_SECONDS (30s, see ai_service.py) between each of up to 3
# retries - a stage that hits 503 on every attempt needs ~90s just for
# those sleeps, before its own (fast) request round-trips. 25s used to cut
# that off mid-retry, before Gemini ever got a real chance to succeed or
# fail definitively. 120s covers one stage's full worst-case 503 retry
# cycle with headroom, while still bounding how long a search can ever take.
_SEARCH_TIME_BUDGET_SECONDS = 120.0

# Words too short or too generic to mean anything as an overlap signal
# (boolean operators from the expanded query, common English filler).
_OVERLAP_STOPWORDS = {
    "and", "or", "the", "for", "with", "in", "of", "on", "a", "an", "to", "vs",
}
_OVERLAP_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9\-]{2,}")

# battery_term_mapping.expand_with_dictionary deliberately keeps any Hangul
# it has no TERM_MAP entry for (e.g. "고전압") as a literal token instead of
# silently dropping it - that's the right call for the *display* query, but
# Semantic Scholar's index is English-only, and literal Hangul in the actual
# API query starves the result set (it's treated as an unmatchable required
# term) instead of just failing to match on those specific words alone.
_HANGUL_RE = re.compile(r"[가-힣]+")


def _api_search_query(english_query: str) -> str:
    """Derive the string actually sent to Semantic Scholar from the
    (possibly Hangul-containing) display query, by stripping any leftover
    Hangul. Never returns an empty string - falls back to the untouched
    query if stripping would remove everything (e.g. an all-Korean keyword
    with no TERM_MAP hits at all), since a degraded search beats none."""

    stripped = " ".join(_HANGUL_RE.sub(" ", english_query).split())
    return stripped or english_query


def _significant_terms(english_query: str, expanded_terms: list[str]) -> set[str]:
    """Collect lowercased, deduplicated search terms worth checking for
    title/abstract overlap: whole expanded phrases (kept intact so e.g.
    "silicon anode" isn't reduced to the near-meaningless word "anode"
    alone) plus individual significant words from the English query."""

    terms: set[str] = set()
    for phrase in expanded_terms:
        cleaned = phrase.strip().lower()
        if len(cleaned) >= 3:
            terms.add(cleaned)
    for word in _OVERLAP_WORD_RE.findall(english_query):
        lowered = word.lower()
        if lowered not in _OVERLAP_STOPWORDS:
            terms.add(lowered)
    return terms


def _apply_relevance_safety_filter(
    ranked: list[tuple["semantic_scholar_service.Candidate", float, str]],
    english_query: str,
    expanded_terms: list[str],
) -> list[tuple["semantic_scholar_service.Candidate", float, str]]:
    """Safety net for when AI re-ranking itself failed: without Gemini's
    semantic judgment, fall back to plain lexical overlap between the
    (expanded) search terms and each candidate's title/abstract. Candidates
    with no overlap at all are pushed to the bottom (not dropped outright,
    so a too-strict match never leaves fewer than top_n_results papers);
    candidates within each bucket keep Semantic Scholar's original relative
    order - this filter only demotes, it never re-sorts by year/recency.
    """

    terms = _significant_terms(english_query, expanded_terms)
    if not terms:
        return ranked

    overlapping = []
    non_overlapping = []
    for item in ranked:
        candidate = item[0]
        haystack = f"{candidate.title} {candidate.abstract}".lower()
        if any(term in haystack for term in terms):
            overlapping.append(item)
        else:
            non_overlapping.append(item)
    return overlapping + non_overlapping


def _sort_key(
    item: tuple["semantic_scholar_service.Candidate", float, str], sort_by: str
) -> tuple[float, float]:
    """Sort key for the final (non-degraded) result ordering. Both the
    relevance score and publication year are always in the tuple - only
    which one comes first (and thus wins ties) changes with `sort_by`.
    Missing year sorts as 0 (last, since sorting is descending)."""

    candidate, score, _ = item
    year = candidate.year or 0
    if sort_by == "recency":
        return (year, score)
    return (score, year)


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
    paper.result_summary = analysis.get("result_summary", "")
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
        except (RuntimeError, TimeoutError) as exc:
            if isinstance(exc, TimeoutError):
                logger.warning(
                    "Individual extraction for paper %r aborted: %.1fs search time budget exhausted",
                    paper.title,
                    remaining,
                )
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
    except (RuntimeError, TimeoutError) as exc:
        if isinstance(exc, TimeoutError):
            logger.warning("Batch extraction aborted: %.1fs search time budget exhausted", remaining)
        return await _extract_papers_individually(needs, gemini_api_key, deadline)

    degraded = False
    for i, paper in enumerate(needs):
        if i in analyses:
            _apply_extraction(paper, analyses[i])
        else:
            degraded = True
    return degraded


async def run_search(
    db: Session,
    keyword: str,
    gemini_api_key: str | None = None,
    *,
    material: str = "",
    material_notice: str = "",
    material_notice_level: str = "",
    performance: str = "",
    additive_or_solvent: str = "",
    sort_by: str = "relevance",
) -> tuple[SearchQuery, bool]:
    """Run the full pipeline for a keyword and persist the results.

    `keyword` is the single combined search string the pipeline (query
    expansion, Semantic Scholar, re-ranking) actually operates on;
    `material`/`performance`/`additive_or_solvent` are the structured
    fields it was built from (from the UI's 3-field search form) and are
    persisted alongside it purely so a later "search again" can repopulate
    the same 3 boxes - they play no other role in the pipeline itself.
    `material_notice` is the (already-computed, by the caller) Korean
    notice from `battery_term_mapping.correct_material_typos`, persisted
    the same way so it survives a page reload.

    `sort_by` picks which signal is the PRIMARY sort key whenever a real
    relevance score exists - "relevance" (default): relevance score desc,
    year desc as tiebreaker; "recency": year desc, relevance score desc as
    tiebreaker. Both signals are always considered either way; only the
    priority flips. This applies whether the score came from Gemini or
    from the local BM25 fallback (see below) - it has no effect only in
    the rare case neither has any real signal at all (no candidate shares
    any query vocabulary), where Semantic Scholar's own order is kept
    regardless of `sort_by`.

    `gemini_api_key`, when given (e.g. from the caller's X-Gemini-Api-Key
    header), is used for every AI call instead of the server's .env key.

    If Gemini is unavailable or the time budget runs out (RuntimeError or
    TimeoutError from a wait_for-wrapped ai_service call), the pipeline
    degrades gracefully instead of failing the whole search: query
    expansion falls back to `battery_term_mapping`'s static dictionary
    (never silently drops part of the keyword), re-ranking falls back to
    `local_reranker`'s BM25 scoring (filtered through a lexical-overlap
    safety net as a second check), and battery analysis falls back to
    "정보 없음" placeholders. The selected top-N results are always
    returned regardless of degradation. The caller is told via the
    returned `ai_degraded` flag so it can surface a notice to the user.

    Returns (SearchQuery with its `results` relationship populated,
    ordered by rank - relevance score first, publication year as
    tiebreaker for same-score papers, EXCEPT in the rare case where
    neither Gemini nor local BM25 produced any relevance signal at all:
    then every score is 0 and the result stays in Semantic Scholar's own
    order instead of being re-sorted by year; ai_degraded).
    """

    ai_degraded = False
    deadline = time.monotonic() + _SEARCH_TIME_BUDGET_SECONDS

    remaining = deadline - time.monotonic()
    if remaining <= 0:
        logger.warning("Query expansion falling back to static dictionary (search time budget already exhausted)")
        english_query, expanded_terms = battery_term_mapping.expand_with_dictionary(keyword)
        ai_degraded = True
    else:
        try:
            english_query, expanded_terms = await asyncio.wait_for(
                ai_service.expand_search_query(keyword, gemini_api_key), timeout=remaining
            )
        except (RuntimeError, TimeoutError) as exc:
            if isinstance(exc, TimeoutError):
                # A plain (non-httpx) TimeoutError here means our own
                # per-search time budget ran out while waiting - ai_service
                # never got to log a cause because the call was still in
                # flight, so it's logged here instead.
                logger.warning("Query expansion aborted: %.1fs search time budget exhausted", remaining)
            # Greppable marker for how often Gemini query expansion fails -
            # a rising count here is a proxy for the daily free-tier quota
            # (or 503 high-demand) rate, independent of any specific search.
            logger.warning("Query expansion falling back to static dictionary (Gemini unavailable)")
            english_query, expanded_terms = battery_term_mapping.expand_with_dictionary(keyword)
            ai_degraded = True

    api_query = _api_search_query(english_query)
    candidates = await semantic_scholar_service.search_candidates(api_query)
    if not candidates:
        raise ValueError(f"'{keyword}'에 대한 논문을 찾을 수 없습니다.")

    remaining = deadline - time.monotonic()
    rerank_degraded = False
    if remaining <= 0:
        logger.warning("Re-ranking falling back to local BM25 (search time budget already exhausted)")
        ranked = local_reranker.rerank_locally(english_query, expanded_terms, candidates)
        ai_degraded = True
        rerank_degraded = True
    else:
        try:
            ranked = await asyncio.wait_for(
                ai_service.rerank_candidates(keyword, candidates, gemini_api_key), timeout=remaining
            )
        except (RuntimeError, TimeoutError) as exc:
            if isinstance(exc, TimeoutError):
                logger.warning("Re-ranking aborted: %.1fs search time budget exhausted", remaining)
            # Greppable marker for how often Gemini re-ranking fails, same
            # intent as the query-expansion one above.
            logger.warning("Re-ranking falling back to local BM25 (Gemini unavailable)")
            ranked = local_reranker.rerank_locally(english_query, expanded_terms, candidates)
            ai_degraded = True
            rerank_degraded = True

    if rerank_degraded:
        # Local BM25 already computed a real relevance score per candidate,
        # but the lexical-overlap safety net still runs as an independent
        # second check - if BM25 itself has a bug, this can only ever
        # demote a candidate further, never wrongly promote one, so it's
        # cheap insurance rather than redundant work.
        ranked = _apply_relevance_safety_filter(ranked, english_query, expanded_terms)
        top = ranked[: settings.top_n_results]
        if not all(score == 0.0 for _, score, _ in ranked):
            # BM25 found real signal - same sort_by-aware ordering as a
            # successful Gemini call gets, so "정확도 우선"/"최신순 우선" behave
            # identically regardless of which scorer produced the score.
            top = sorted(top, key=lambda t: _sort_key(t, sort_by), reverse=True)
        # else: not a single candidate shares any query vocabulary at all -
        # no signal to rank by, so Semantic Scholar's own order (already
        # preserved by both BM25 and the safety filter above) is kept
        # as-is instead of falling back to a de facto year-sort.
    else:
        top = ranked[: settings.top_n_results]
        top = sorted(top, key=lambda t: _sort_key(t, sort_by), reverse=True)

    search_query = SearchQuery(
        keyword=keyword,
        material=material,
        material_notice=material_notice,
        material_notice_level=material_notice_level,
        performance=performance,
        additive_or_solvent=additive_or_solvent,
        sort_by=sort_by,
        expanded_query=english_query,
    )
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
