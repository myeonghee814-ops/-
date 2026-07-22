"""Local (non-AI) relevance re-ranking, used as the fallback when Gemini's
own `ai_service.rerank_and_extract_candidates` is unavailable (429/503/timeout). Before
this existed, a degraded search fell back to Semantic Scholar's own order
verbatim - this module gives that fallback an actual relevance signal
instead, via BM25 (Okapi BM25, k1=1.5/b=0.75 - standard defaults), computed
locally with no external API call and no third-party dependency.

Candidates that share no vocabulary with the query score exactly 0 and
naturally sink to the bottom when sorted - the same outcome
`search_pipeline._apply_relevance_safety_filter` produces by demotion, kept
in place alongside this as a second, independent safety net in case this
scoring has a bug of its own.

BM25 is lexical-overlap-only, so it can't tell that a candidate matched an
acronym in the wrong field (e.g. "FEC" = fluoroethylene carbonate here, but
forward error correction in networking) - `domain_score_adjustment` adds a
small independent bonus/penalty on top, based on whether the candidate's
title/abstract actually looks like battery research at all. See
BATTERY_DOMAIN_KEYWORDS/OFF_DOMAIN_KEYWORDS below.
"""

import math
import re
from collections import Counter
from dataclasses import dataclass

from app.services.semantic_scholar_service import Candidate

_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9\-]{1,}")
_MIN_TOKEN_LENGTH = 2

# Words too short/generic to mean anything as a query signal (boolean
# operators from the expanded query, common English filler) - excluded
# from the query term set, not from document tokenization.
_QUERY_STOPWORDS = {
    "and", "or", "the", "for", "with", "in", "of", "on", "a", "an", "to", "vs",
}

_BM25_K1 = 1.5
_BM25_B = 0.75

LOCAL_RERANK_WHY_SELECTED = "검색어 키워드 일치도 기준으로 정렬됨 (AI 재순위화 실패로 로컬 폴백 적용)"

# Domain-relevance signal, independent of query-term overlap: some acronyms
# used in the search query are genuinely ambiguous across fields (e.g. "FEC"
# is fluoroethylene carbonate here, but forward error correction in
# networking) - Semantic Scholar's plain-text search has no way to know
# which field the user meant, so it can return off-topic candidates that
# happen to share the literal acronym. This nudges battery-relevant
# candidates up and pushes clearly-off-domain ones to the bottom, on top of
# (not instead of) the BM25 lexical-overlap score above. Deliberately a
# short, hand-picked list (same "extend as gaps surface" spirit as
# battery_term_mapping's TERM_MAP), not an exhaustive taxonomy. Journal name
# is intentionally NOT checked here - a journal whitelist/blocklist is a
# separate, higher-maintenance mechanism to consider later.
#
# "cell" is deliberately NOT included bare - it collides with "cellular
# network"/"stem cell" etc., which would defeat the point of this list for
# exactly the kind of off-domain (telecom) content it exists to demote.
BATTERY_DOMAIN_KEYWORDS = {
    "battery",
    "batteries",
    "electrolyte",
    "cathode",
    "anode",
    "lithium-ion",
    "lithium ion",
    "li-ion",
    "li-s",
    "lithium-sulfur",
    "solid electrolyte interphase",
    "sei",
    "cei",
    "coulombic efficiency",
    "capacity retention",
    "cycling stability",
    "coin cell",
    "pouch cell",
    "full cell",
    "half cell",
}

OFF_DOMAIN_KEYWORDS = {
    "forward error correction",
    "wireless",
    "wireless network",
    "network coding",
    "channel coding",
    "transport protocol",
    "ldpc",
    "turbo code",
    "convolutional code",
    "bit error rate",
    "packet loss",
    "modulation",
    "5g",
    "4g",
    "real-time communication",
}

# Bonus is modest - a tie-breaking nudge on top of the real BM25 lexical
# signal, not a replacement for it. Penalty is deliberately huge relative to
# any realistic BM25 score, so an off-domain match always sinks to (or near)
# the bottom after normalization, regardless of how strong its raw lexical
# overlap happens to be.
_BATTERY_DOMAIN_BONUS = 3.0
_OFF_DOMAIN_PENALTY = 1000.0


def has_battery_domain_keyword(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in BATTERY_DOMAIN_KEYWORDS)


def has_off_domain_keyword(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in OFF_DOMAIN_KEYWORDS)


def domain_score_adjustment(text: str) -> float:
    """Score delta from domain-relevance keywords in `text` (title+abstract) -
    add to a candidate's raw relevance score before normalizing."""

    adjustment = 0.0
    if has_battery_domain_keyword(text):
        adjustment += _BATTERY_DOMAIN_BONUS
    if has_off_domain_keyword(text):
        adjustment -= _OFF_DOMAIN_PENALTY
    return adjustment


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text) if len(t) >= _MIN_TOKEN_LENGTH]


def _query_terms(english_query: str, expanded_terms: list[str]) -> list[str]:
    """Collect query terms for BM25 scoring: whole expanded phrases (kept
    intact so e.g. "silicon anode" isn't reduced to just "anode") plus
    individual significant words from the English query. Mirrors
    search_pipeline._significant_terms's term-collection intent, but
    returns a token list (with repeats folded via a later Counter) rather
    than a plain set, since BM25 treats each query term independently."""

    terms: list[str] = []
    seen: set[str] = set()

    def _add_unique(term: str) -> None:
        if term not in seen:
            seen.add(term)
            terms.append(term)

    for phrase in expanded_terms:
        for token in _tokenize(phrase):
            _add_unique(token)
    for token in _tokenize(english_query):
        if token not in _QUERY_STOPWORDS:
            _add_unique(token)

    return terms


@dataclass
class _Doc:
    candidate: Candidate
    token_counts: Counter
    length: int


def _score_bm25(query_terms: list[str], docs: list[_Doc]) -> list[float]:
    n_docs = len(docs)
    avg_doc_length = sum(d.length for d in docs) / n_docs if n_docs else 0.0

    doc_freq: dict[str, int] = {}
    for term in query_terms:
        doc_freq[term] = sum(1 for d in docs if d.token_counts.get(term))

    # +1 inside the log (the Lucene/modern BM25 variant) keeps idf
    # non-negative even for a term that appears in every candidate,
    # unlike the classic Robertson-Sparck-Jones formula.
    idf = {
        term: math.log(1 + (n_docs - df + 0.5) / (df + 0.5))
        for term, df in doc_freq.items()
    }

    scores: list[float] = []
    for doc in docs:
        score = 0.0
        for term in query_terms:
            freq = doc.token_counts.get(term, 0)
            if not freq:
                continue
            denom = freq + _BM25_K1 * (1 - _BM25_B + _BM25_B * doc.length / avg_doc_length)
            score += idf[term] * (freq * (_BM25_K1 + 1)) / denom
        scores.append(score)
    return scores


def _normalize_to_100(scores: list[float]) -> list[float]:
    """Min-max normalize raw BM25 scores to a 0-100 scale, matching
    Gemini's relevance_score range - the frontend's RelevanceBadge assumes
    a 0-100 scale for its color tiers, so a normalized score stays visually
    meaningful if it's ever displayed for a locally-reranked result."""

    if not scores:
        return []
    lo, hi = min(scores), max(scores)
    if hi <= 0 or hi == lo:
        return [0.0] * len(scores)
    return [100.0 * (s - lo) / (hi - lo) for s in scores]


def rerank_locally(
    english_query: str, expanded_terms: list[str], candidates: list[Candidate]
) -> list[tuple[Candidate, float, str]]:
    """BM25-based relevance scoring over each candidate's title+abstract
    against the (expanded) query terms - a drop-in substitute for
    `ai_service.rerank_and_extract_candidates` when Gemini is unavailable. Returns
    (candidate, relevance_score, why_selected) tuples sorted best-first,
    same shape as the Gemini path.

    A candidate with no query-term overlap at all scores exactly 0.0 and
    sorts to the bottom; if EVERY candidate scores 0.0 (no query term
    appears anywhere in this candidate set), the list is returned in its
    original input order unchanged - there is no signal to rank by, so
    nothing should be inferred/reordered from that non-signal.
    """

    if not candidates:
        return []

    query_terms = _query_terms(english_query, expanded_terms)
    if not query_terms:
        return [(c, 0.0, "") for c in candidates]

    docs = []
    for candidate in candidates:
        tokens = _tokenize(f"{candidate.title} {candidate.abstract}")
        docs.append(_Doc(candidate=candidate, token_counts=Counter(tokens), length=len(tokens) or 1))

    raw_scores = _score_bm25(query_terms, docs)
    adjusted_scores = [
        score + domain_score_adjustment(f"{doc.candidate.title} {doc.candidate.abstract}")
        for score, doc in zip(raw_scores, docs)
    ]
    if all(score == 0.0 for score in adjusted_scores):
        return [(c, 0.0, "") for c in candidates]

    normalized = _normalize_to_100(adjusted_scores)
    scored = [
        (doc.candidate, score, LOCAL_RERANK_WHY_SELECTED if score > 0 else "")
        for doc, score in zip(docs, normalized)
    ]
    scored.sort(key=lambda t: t[1], reverse=True)
    return scored
