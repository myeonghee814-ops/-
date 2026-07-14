from pydantic import BaseModel, Field

from app.schemas.paper import PaperCard


class SearchRequest(BaseModel):
    keyword: str = Field(min_length=2, max_length=200)


class SearchResponse(BaseModel):
    search_id: int
    keyword: str
    expanded_query: str
    results: list[PaperCard]
