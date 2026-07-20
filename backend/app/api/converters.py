from app.db.models import SearchResult
from app.schemas.paper import BatterySnapshot, PaperCard, PaperDetail


def to_paper_card(result: SearchResult) -> PaperCard:
    paper = result.paper
    return PaperCard(
        result_id=result.id,
        rank=result.rank,
        relevance_score=result.relevance_score,
        why_selected=result.why_selected,
        title=paper.title,
        authors=paper.authors,
        journal=paper.journal,
        year=paper.year,
        doi=paper.doi,
        battery_snapshot=BatterySnapshot(
            cathode=paper.cathode,
            anode=paper.anode,
            electrolyte=paper.electrolyte,
            voltage_window=paper.voltage_window,
            cell_type=paper.cell_type,
        ),
    )


def to_paper_detail(result: SearchResult) -> PaperDetail:
    card = to_paper_card(result)
    paper = result.paper
    return PaperDetail(
        **card.model_dump(),
        experimental_conditions=paper.experimental_conditions,
        result_summary=paper.result_summary,
        abstract=paper.abstract,
        keyword=result.search_query.keyword,
    )
