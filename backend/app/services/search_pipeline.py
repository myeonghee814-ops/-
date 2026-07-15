"""Orchestrates the full pipeline:

Keyword (Korean/English/shorthand) -> AI query expansion -> Semantic
Scholar search -> AI re-ranking (Korean reasoning) -> battery metadata
extraction (Korean) -> persisted SearchQuery/SearchResult/Paper rows.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Paper, SearchQuery, SearchResult
from app.services import ai_service, semantic_scholar_service


async def _get_or_create_paper(
    db: Session, candidate: semantic_scholar_service.Candidate, gemini_api_key: str | None = None
) -> Paper:
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

    if not paper.is_extracted:
        analysis = await ai_service.extract_battery_analysis(
            paper.title, paper.abstract, gemini_api_key
        )
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
        db.flush()

    return paper


async def run_search(db: Session, keyword: str, gemini_api_key: str | None = None) -> SearchQuery:
    """Run the full pipeline for a keyword and persist the results.

    `gemini_api_key`, when given (e.g. from the caller's X-Gemini-Api-Key
    header), is used for every AI call instead of the server's .env key.

    Returns the SearchQuery row with its `results` relationship populated
    (ordered by rank, best first).
    """

    english_query, _expanded_terms = await ai_service.expand_search_query(keyword, gemini_api_key)

    candidates = await semantic_scholar_service.search_candidates(english_query)
    if not candidates:
        raise ValueError(f"'{keyword}'에 대한 논문을 찾을 수 없습니다.")

    ranked = await ai_service.rerank_candidates(keyword, candidates, gemini_api_key)
    top = ranked[: settings.top_n_results]

    search_query = SearchQuery(keyword=keyword, expanded_query=english_query)
    db.add(search_query)
    db.flush()

    for rank, (candidate, score, why_selected) in enumerate(top, start=1):
        paper = await _get_or_create_paper(db, candidate, gemini_api_key)
        db.add(
            SearchResult(
                search_query_id=search_query.id,
                paper_id=paper.id,
                rank=rank,
                relevance_score=score,
                why_selected=why_selected,
            )
        )

    db.commit()
    db.refresh(search_query)
    return search_query
