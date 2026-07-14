from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.converters import to_paper_card
from app.db.database import get_db
from app.db.models import SearchQuery
from app.schemas.search import SearchRequest, SearchResponse
from app.services.search_pipeline import run_search

router = APIRouter(prefix="/api/search", tags=["search"])


@router.post("", response_model=SearchResponse)
async def create_search(request: SearchRequest, db: Session = Depends(get_db)) -> SearchResponse:
    keyword = request.keyword.strip()
    try:
        search_query = await run_search(db, keyword)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return SearchResponse(
        search_id=search_query.id,
        keyword=search_query.keyword,
        expanded_query=search_query.expanded_query,
        results=[to_paper_card(r) for r in search_query.results],
    )


@router.get("/{search_id}", response_model=SearchResponse)
def get_search(search_id: int, db: Session = Depends(get_db)) -> SearchResponse:
    search_query = db.get(SearchQuery, search_id)
    if search_query is None:
        raise HTTPException(status_code=404, detail="검색 결과를 찾을 수 없습니다.")

    return SearchResponse(
        search_id=search_query.id,
        keyword=search_query.keyword,
        expanded_query=search_query.expanded_query,
        results=[to_paper_card(r) for r in search_query.results],
    )
