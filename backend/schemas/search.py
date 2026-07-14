from pydantic import BaseModel, Field, model_validator


class SearchQuery(BaseModel):
    """Validated input for a literature search."""

    keyword: str = Field(..., min_length=1, description="Search keyword, e.g. a topic or title fragment")
    year_from: int | None = Field(default=None, ge=1900, description="Earliest publication year (inclusive)")
    year_to: int | None = Field(default=None, ge=1900, description="Latest publication year (inclusive)")
    limit: int = Field(default=20, ge=1, le=100, description="Maximum number of papers to return")

    @model_validator(mode="after")
    def _validate_year_range(self) -> "SearchQuery":
        if self.year_from is not None and self.year_to is not None and self.year_from > self.year_to:
            raise ValueError("year_from must not be greater than year_to")
        return self


class PaperResult(BaseModel):
    """A single search result, normalized across providers."""

    title: str
    authors: list[str] = Field(default_factory=list)
    journal: str | None = None
    year: int | None = None
    citation_count: int | None = None
    doi: str | None = None
    abstract: str | None = None
    pdf_url: str | None = None
    published_date: str | None = None
    source: str = Field(description="Which provider returned this result")


class SearchResponse(BaseModel):
    """Response body for GET /api/search."""

    query: SearchQuery
    source: str = Field(description="Which provider answered the query")
    count: int
    results: list[PaperResult]
