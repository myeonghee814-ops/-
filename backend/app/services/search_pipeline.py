"""Orchestrates the full pipeline:

3-field form (material/performance/additive-or-solvent) -> additive/solvent
CATEGORY expansion (e.g. "불소계" -> LiFSI/FEC/LiPF6) -> combined keyword ->
AI query expansion -> Semantic Scholar search -> AI re-ranking (Korean
reasoning) -> battery metadata extraction (Korean, batched) -> persisted
SearchQuery/SearchResult/Paper rows.

The whole pipeline is bounded by _SEARCH_TIME_BUDGET_SECONDS: every
Gemini-calling phase is awaited with whatever time remains in the budget,
so a slow/overloaded Gemini degrades the result instead of hanging the
request. Three stages have a non-Gemini fallback instead of just giving up:
- additive/solvent category expansion (`_expand_additive_category`) falls
  back to `battery_term_mapping`'s small curated CATEGORY_COMPOUND_MAP, then
  to searching the raw category text as-is if even that has no entry -
  searching a bare category word (rather than the specific compounds it
  refers to) matches nothing useful in a paper's title/abstract.
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
All three fallback stages log a distinct "falling back to..." line on entry
- grepping for that text over time is a proxy for how often Gemini itself
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
from app.services import (
    ai_service,
    battery_term_mapping,
    local_reranker,
    pdf_extract,
    semantic_scholar_service,
)

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

# semantic_scholar_service.search_candidates calls the plain relevance-search
# endpoint (/graph/v1/paper/search), which - per Semantic Scholar's own docs -
# has no boolean query syntax: only the separate /paper/search/bulk endpoint
# supports quotes/parentheses/operators, and even there OR is the `|`
# character, never the literal word "OR". QUERY_EXPANSION_SYSTEM_PROMPT now
# tells Gemini not to produce '("term1" OR "term2") AND "term3"'-style output,
# but this strips it anyway as a second, independent safety net - sent
# verbatim to the relevance endpoint, those quote/paren/AND/OR characters are
# literal text that essentially never appears in a real paper's title or
# abstract, so the whole query matches nothing (0 candidates) even though
# every individual term inside it would have matched plenty on its own. This
# was the root cause behind at least one previously-unexplained "no results"
# search (a keyword combination Gemini happened to expand into this form).
_BOOLEAN_SYNTAX_RE = re.compile(r"[\"'“”()]|\b(?:AND|OR)\b", re.IGNORECASE)


# Appended to every outgoing Semantic Scholar query, regardless of source
# (Gemini or dictionary fallback) - many battery-relevant abbreviations are
# genuinely ambiguous across fields (e.g. "FEC" = fluoroethylene carbonate
# here, but forward error correction in networking), and Semantic Scholar's
# plain-text search has no way to know which field was meant. These are
# common, generic words that match the vast majority of real battery papers,
# so they bias the ranking toward battery-domain results without narrowing
# the candidate pool the way another *specific* term would (see the
# material-only retry below for why piling on specific terms can backfire).
_BATTERY_CONTEXT_SUFFIX = "lithium-ion battery electrolyte"


def _api_search_query(english_query: str) -> str:
    """Derive the string actually sent to Semantic Scholar from the
    (possibly Hangul-containing, possibly boolean-syntax-containing) display
    query: strips leftover Hangul (see battery_term_mapping above) and any
    quote/parenthesis/AND/OR boolean syntax the relevance-search endpoint
    doesn't understand, leaving a plain space-separated keyword list, then
    appends _BATTERY_CONTEXT_SUFFIX so an ambiguous abbreviation is biased
    toward its battery-domain meaning. Falls back to the untouched query
    (plus the suffix) if stripping would remove everything, since a
    degraded search beats none."""

    stripped = _HANGUL_RE.sub(" ", english_query)
    stripped = _BOOLEAN_SYNTAX_RE.sub(" ", stripped)
    stripped = " ".join(stripped.split())
    base = stripped or english_query
    return f"{base} {_BATTERY_CONTEXT_SUFFIX}"


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
    (expanded) search terms and each candidate's title/abstract, demoted
    into three buckets (each keeping Semantic Scholar's original relative
    order - this filter only demotes, it never re-sorts by year/recency):
    1. query-term overlap (or no `terms` to check at all)
    2. no query-term overlap
    3. an OFF_DOMAIN_KEYWORDS match (see local_reranker) - always last,
       regardless of terms-overlap, since an ambiguous abbreviation (e.g.
       "FEC" matching a networking paper instead of fluoroethylene
       carbonate) can lexically overlap with the query while still being
       off-topic. Never drops candidates outright, so a too-strict match
       never leaves fewer than top_n_results papers.
    """

    off_domain = []
    remaining = []
    for item in ranked:
        candidate = item[0]
        haystack = f"{candidate.title} {candidate.abstract}".lower()
        if local_reranker.has_off_domain_keyword(haystack):
            off_domain.append(item)
        else:
            remaining.append(item)

    terms = _significant_terms(english_query, expanded_terms)
    if not terms:
        return remaining + off_domain

    overlapping = []
    non_overlapping = []
    for item in remaining:
        candidate = item[0]
        haystack = f"{candidate.title} {candidate.abstract}".lower()
        if any(term in haystack for term in terms):
            overlapping.append(item)
        else:
            non_overlapping.append(item)
    return overlapping + non_overlapping + off_domain


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
            open_access_pdf_url=candidate.open_access_pdf_url,
        )
        db.add(paper)
        db.flush()
    else:
        # Bibliographic (not AI-derived) field - safe and cheap to refresh
        # from Semantic Scholar every time this paper resurfaces, unlike
        # cathode/anode/etc. which require a Gemini call to redo.
        paper.open_access_pdf_url = candidate.open_access_pdf_url
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


async def _expand_additive_category(
    additive_or_solvent: str, gemini_api_key: str | None, deadline: float
) -> tuple[str, str, str, bool]:
    """If `additive_or_solvent` looks like a chemical CATEGORY/FAMILY
    reference (e.g. "불소계", "황계 첨가제") rather than a specific compound
    name, expands it into 3-5 real compound names via Gemini - falling back
    to a small curated dictionary, then to the raw text unchanged - so
    Semantic Scholar gets concrete chemistry to search for instead of a
    vague category word that matches no real paper's text (the same failure
    mode as any other untranslated Hangul).

    Returns (text actually used to build the search keyword, a Korean
    notice describing what happened or "" if nothing needed explaining, a
    notice_level of "info"/"warning", and whether this stage degraded -
    i.e. Gemini's answer wasn't used, regardless of whether the dictionary
    fallback still found something useful).
    """

    if not additive_or_solvent or not battery_term_mapping.looks_like_compound_category(
        additive_or_solvent
    ):
        return additive_or_solvent, "", "", False

    compounds: list[str] = []
    remaining = deadline - time.monotonic()
    if remaining > 0:
        try:
            compounds = await asyncio.wait_for(
                ai_service.expand_compound_category(additive_or_solvent, gemini_api_key),
                timeout=remaining,
            )
        except (RuntimeError, TimeoutError) as exc:
            if isinstance(exc, TimeoutError):
                logger.warning(
                    "Compound category expansion aborted: %.1fs search time budget exhausted",
                    remaining,
                )
            logger.warning(
                "Compound category expansion falling back to static dictionary (Gemini unavailable)"
            )

    if compounds:
        notice = f"'{additive_or_solvent}' → {', '.join(compounds)} 등으로 확장하여 검색했습니다."
        return " ".join(compounds), notice, "info", False

    fallback_compounds = battery_term_mapping.expand_category_from_dictionary(additive_or_solvent)
    if fallback_compounds:
        notice = f"'{additive_or_solvent}' → {', '.join(fallback_compounds)} 등으로 확장하여 검색했습니다."
        return " ".join(fallback_compounds), notice, "info", True

    notice = f"'{additive_or_solvent}'를 구체적 화합물로 확장하지 못해 원문 그대로 검색합니다."
    return additive_or_solvent, notice, "warning", True


async def run_search(
    db: Session,
    material: str,
    gemini_api_key: str | None = None,
    *,
    material_notice: str = "",
    material_notice_level: str = "",
    performance: str = "",
    additive_or_solvent: str = "",
    sort_by: str = "relevance",
) -> tuple[SearchQuery, bool]:
    """Run the full pipeline for the 3-field search form and persist the
    results.

    `material` (already typo-corrected by the caller via
    `battery_term_mapping.correct_material_typos`), `performance`, and
    `additive_or_solvent` are combined internally into the single keyword
    string the pipeline (query expansion, Semantic Scholar, re-ranking)
    actually operates on - `additive_or_solvent` is expanded first if it
    looks like a chemical category rather than a specific compound (see
    `_expand_additive_category`). All three raw fields are also persisted
    as-is on the SearchQuery purely so a later "search again" can repopulate
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

    expanded_additive, additive_notice, additive_notice_level, additive_degraded = (
        await _expand_additive_category(additive_or_solvent, gemini_api_key, deadline)
    )
    ai_degraded = ai_degraded or additive_degraded
    keyword = " ".join(part for part in (material, performance, expanded_additive) if part)

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
    logger.info("Semantic Scholar API query (from display query %r): %r", english_query, api_query)
    candidates = await semantic_scholar_service.search_candidates(api_query)
    if not candidates:
        # Observed live: Semantic Scholar's relevance search can return
        # exactly 0 candidates for a query with several specific terms
        # (e.g. a material name plus 4-5 compound names from additive-
        # category expansion) even though every 4-term subset of the same
        # query returns several - it gets stricter as term count grows
        # rather than more permissive. Retrying on just the material term
        # (the one field guaranteed to be a real, searchable chemistry
        # term) is a cheap second chance before giving up entirely.
        fallback_query = _api_search_query(material)
        if fallback_query and fallback_query != api_query:
            logger.warning(
                "Semantic Scholar returned 0 candidates for %r - retrying with just the material term: %r",
                api_query,
                fallback_query,
            )
            candidates = await semantic_scholar_service.search_candidates(fallback_query)
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
        additive_notice=additive_notice,
        additive_notice_level=additive_notice_level,
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


async def run_deep_analysis(db: Session, paper: Paper, gemini_api_key: str | None = None) -> Paper:
    """On-demand full-text-PDF analysis for one paper, triggered only by an
    explicit user action (never as part of the regular search). Assumes the
    caller has already checked `paper.open_access_pdf_url` is non-empty and
    `paper.is_deep_analyzed` is False - unlike the rest of the pipeline this
    has no graceful-degradation fallback: a failure here is surfaced to the
    caller directly instead of silently downgrading, since it's a single
    explicit request rather than a best-effort background stage.

    Downloads the paper's open-access PDF, extracts its full text (see
    pdf_extract.py), and asks Gemini for experiment-level detail an abstract
    alone usually can't give (exact electrolyte compositions, voltage
    window, cell type). Result is cached on the Paper row (keyed by
    external_paper_id, same as extract_battery_analysis) so revisiting the
    same paper from a later search never re-downloads or re-analyzes it.
    """

    extracted = await pdf_extract.download_and_extract(paper.open_access_pdf_url)
    analysis = await ai_service.extract_deep_analysis(
        paper.title, extracted.body_text, extracted.candidate_figure_captions, gemini_api_key
    )

    paper.deep_base_electrolyte = analysis.get("base_electrolyte", "정보 없음")
    paper.deep_test_electrolyte = analysis.get("test_electrolyte", "정보 없음")
    paper.deep_voltage_range = analysis.get("voltage_range", "정보 없음")
    paper.deep_cell_type_detail = analysis.get("cell_type_detail", "정보 없음")
    paper.deep_key_findings = analysis.get("key_findings", "")
    paper.deep_summary = analysis.get("summary", "")
    paper.deep_analyzed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(paper)
    return paper
