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


class PaperDetail(PaperCard):
    """Shape for the paper detail page: everything from PaperCard plus
    the full research analysis and abstract."""

    experimental_conditions: str
    performance_summary: str
    innovation: str
    advantages: str
    limitations: str
    abstract: str
    keyword: str
