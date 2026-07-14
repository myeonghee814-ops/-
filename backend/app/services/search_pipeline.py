"""Orchestrates the full pipeline:

Keyword -> PubMed search -> AI re-ranking -> battery metadata extraction
-> persisted SearchQuery/SearchResult/Paper rows.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Paper, SearchQuery, SearchResult
from app.services import ai_service, pubmed_service


async def _get_or_create_paper(db: Session, candidate: pubmed_service.Candidate) -> Paper:
    paper = db.query(Paper).filter(Paper.pubmed_id == candidate.pubmed_id).one_or_none()
    if paper is None:
        paper = Paper(
            pubmed_id=candidate.pubmed_id,
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
        analysis = await ai_service.extract_battery_analysis(paper.title, paper.abstract)
        paper.cathode = analysis.get("cathode", "Not specified")
        paper.anode = analysis.get("anode", "Not specified")
        paper.electrolyte = analysis.get("electrolyte", "Not specified")
        paper.voltage_window = analysis.get("voltage_window", "Not specified")
        paper.cell_type = analysis.get("cell_type", "Not specified")
        paper.experimental_conditions = analysis.get("experimental_conditions", "")
        paper.performance_summary = analysis.get("performance_summary", "")
        paper.innovation = analysis.get("innovation", "")
        paper.advantages = analysis.get("advantages", "")
        paper.limitations = analysis.get("limitations", "")
        paper.extracted_at = datetime.now(timezone.utc)
        db.flush()

    return paper


async def run_search(db: Session, keyword: str) -> SearchQuery:
    """Run the full pipeline for a keyword and persist the results.

    Returns the SearchQuery row with its `results` relationship populated
    (ordered by rank, best first).
    """

    candidates = await pubmed_service.search_candidates(keyword)
    if not candidates:
        raise ValueError(f"No papers found on PubMed for keyword: {keyword!r}")

    ranked = await ai_service.rerank_candidates(keyword, candidates)
    top = ranked[: settings.top_n_results]

    search_query = SearchQuery(keyword=keyword)
    db.add(search_query)
    db.flush()

    for rank, (candidate, score, why_selected) in enumerate(top, start=1):
        paper = await _get_or_create_paper(db, candidate)
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
