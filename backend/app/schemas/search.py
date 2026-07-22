from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.paper import PaperCard

SortBy = Literal["relevance", "recency"]
NoticeLevel = Literal["info", "warning"]


class SearchRequest(BaseModel):
    """Structured search input: a material/chemistry term and two optional
    refinements, combined server-side into the single keyword string the
    search pipeline expects. At least one of `material` or
    `additive_or_solvent` is required - searching by additive/solvent alone
    (e.g. "FEC") is supported, in which case search_pipeline.py's
    additive-only mode narrows toward the electrolyte-additive usage
    context specifically (a bare compound name is otherwise ambiguous -
    the same molecule also turns up in papers using it as a coating agent,
    a binder, etc.)."""

    material: str = Field(default="", max_length=200)
    performance: str = Field(default="", max_length=200)
    additive_or_solvent: str = Field(default="", max_length=200)
    sort_by: SortBy = "relevance"

    @model_validator(mode="after")
    def _strip_and_require_material_or_additive(self) -> "SearchRequest":
        self.material = self.material.strip()
        self.performance = self.performance.strip()
        self.additive_or_solvent = self.additive_or_solvent.strip()
        if not self.material and not self.additive_or_solvent:
            raise ValueError("소재 또는 첨가제/용매 중 하나는 입력해주세요.")
        return self


class SearchResponse(BaseModel):
    search_id: int
    keyword: str
    material: str
    material_notice: str = ""
    material_notice_level: NoticeLevel | None = None
    performance: str
    additive_or_solvent: str
    additive_notice: str = ""
    additive_notice_level: NoticeLevel | None = None
    sort_by: SortBy
    expanded_query: str
    results: list[PaperCard]
    ai_degraded: bool = False
