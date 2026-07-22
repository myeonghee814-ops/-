"""Unit tests for api/converters.py's SearchResult -> PaperCard/PaperDetail
mapping - focused on external_paper_id and open_access_pdf_url, which the
search results list (PaperCard) exposes so the frontend can link out to
DOI/Semantic Scholar and show a "PDF 보기" button without a second request.
"""

from app.api.converters import to_paper_card, to_paper_detail
from app.db.models import Paper, SearchQuery, SearchResult


def _make_result(**paper_overrides) -> SearchResult:
    # Paper's SQLAlchemy column defaults (e.g. cathode: default="") only
    # apply at INSERT time, not when constructing the object in memory
    # without a session - so every column converters.py reads must be
    # given explicitly here.
    paper_kwargs = dict(
        external_paper_id="abc123",
        title="Title",
        authors="Author A",
        journal="Journal X",
        year=2024,
        doi="10.1/x",
        abstract="Abstract text.",
        open_access_pdf_url="https://example.com/paper.pdf",
        cathode="NCA",
        anode="Graphite",
        electrolyte="1M LiPF6 in EC/DMC",
        voltage_window="3.0-4.3 V",
        cell_type="coin cell",
        experimental_conditions="",
        result_summary="",
    )
    paper_kwargs.update(paper_overrides)
    paper = Paper(**paper_kwargs)

    result = SearchResult(id=1, rank=1, relevance_score=90.0, why_selected="관련성이 높습니다.")
    result.paper = paper
    result.search_query = SearchQuery(keyword="NCA")
    return result


def test_to_paper_card_includes_external_paper_id_and_pdf_url():
    card = to_paper_card(_make_result())

    assert card.external_paper_id == "abc123"
    assert card.open_access_pdf_url == "https://example.com/paper.pdf"


def test_to_paper_card_open_access_pdf_url_defaults_to_empty():
    card = to_paper_card(_make_result(open_access_pdf_url=""))

    assert card.open_access_pdf_url == ""


def test_to_paper_detail_still_includes_open_access_pdf_url():
    """Regression: open_access_pdf_url used to be declared directly on
    PaperDetail - now it's inherited from PaperCard, and to_paper_detail no
    longer passes it explicitly. Make sure it still ends up populated."""

    detail = to_paper_detail(_make_result())

    assert detail.open_access_pdf_url == "https://example.com/paper.pdf"
    assert detail.external_paper_id == "abc123"
