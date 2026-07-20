from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.paper import PaperCard

SortBy = Literal["relevance", "recency"]
MaterialNoticeLevel = Literal["info", "warning"]


class SearchRequest(BaseModel):
    """Structured search input: a required material/chemistry term plus
    two optional refinements, combined server-side into the single
    keyword string the search pipeline expects."""

    material: str = Field(min_length=1, max_length=200)
    performance: str = Field(default="", max_length=200)
    additive_or_solvent: str = Field(default="", max_length=200)
    sort_by: SortBy = "relevance"

    @model_validator(mode="after")
    def _strip_and_require_material(self) -> "SearchRequest":
        self.material = self.material.strip()
        self.performance = self.performance.strip()
        self.additive_or_solvent = self.additive_or_solvent.strip()
        if not self.material:
            raise ValueError("소재를 입력해주세요.")
        return self


class SearchResponse(BaseModel):
    search_id: int
    keyword: str
    material: str
    material_notice: str = ""
    material_notice_level: MaterialNoticeLevel | None = None
    performance: str
    additive_or_solvent: str
    sort_by: SortBy
    expanded_query: str
    results: list[PaperCard]
    ai_degraded: bool = False
