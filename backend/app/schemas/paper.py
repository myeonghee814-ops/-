from pydantic import BaseModel


class BatterySnapshot(BaseModel):
    cathode: str
    anode: str
    electrolyte: str
    voltage_window: str
    cell_type: str


class PaperCard(BaseModel):
    """Shape for the top-10 results list."""

    result_id: int
    rank: int
    relevance_score: float
    why_selected: str

    title: str
    authors: str
    journal: str
    year: int | None
    doi: str

    battery_snapshot: BatterySnapshot


class DeepAnalysis(BaseModel):
    """On-demand, full-text-PDF analysis - see ai_service.extract_deep_analysis.
    Present only once the user has clicked "자세히 분석" and it succeeded."""

    base_electrolyte: str
    test_electrolyte: str
    voltage_range: str
    cell_type_detail: str
    key_findings: str
    summary: str


class PaperDetail(PaperCard):
    """Shape for the paper detail page: everything from PaperCard plus
    the full research analysis and abstract."""

    experimental_conditions: str
    result_summary: str
    abstract: str
    keyword: str
    open_access_pdf_url: str
    deep_analysis: DeepAnalysis | None
