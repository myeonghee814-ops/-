from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.converters import to_paper_detail
from app.db.database import get_db
from app.db.models import SearchResult
from app.schemas.paper import PaperDetail

router = APIRouter(prefix="/api/results", tags=["papers"])


@router.get("/{result_id}", response_model=PaperDetail)
def get_result_detail(result_id: int, db: Session = Depends(get_db)) -> PaperDetail:
    result = db.get(SearchResult, result_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Result not found")
    return to_paper_detail(result)
