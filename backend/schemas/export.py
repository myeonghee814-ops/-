from pydantic import BaseModel, Field

from schemas.search import PaperResult


class ExportRequest(BaseModel):
    """Input for Excel export: the papers the user selected in the results grid."""

    papers: list[PaperResult] = Field(..., min_length=1)
