from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.api.converters import to_paper_detail
from app.db.database import get_db
from app.db.models import SearchResult
from app.schemas.paper import PaperDetail
from app.services import pdf_extract
from app.services.search_pipeline import run_deep_analysis

router = APIRouter(prefix="/api/results", tags=["papers"])


@router.get("/{result_id}", response_model=PaperDetail)
def get_result_detail(result_id: int, db: Session = Depends(get_db)) -> PaperDetail:
    result = db.get(SearchResult, result_id)
    if result is None:
        raise HTTPException(status_code=404, detail="해당 논문 결과를 찾을 수 없습니다.")
    return to_paper_detail(result)


@router.post("/{result_id}/deep-analysis", response_model=PaperDetail)
async def create_deep_analysis(
    result_id: int,
    db: Session = Depends(get_db),
    x_gemini_api_key: str | None = Header(default=None, alias="X-Gemini-Api-Key"),
) -> PaperDetail:
    result = db.get(SearchResult, result_id)
    if result is None:
        raise HTTPException(status_code=404, detail="해당 논문 결과를 찾을 수 없습니다.")

    paper = result.paper
    if not paper.is_deep_analyzed:
        if not paper.open_access_pdf_url:
            raise HTTPException(
                status_code=422, detail="오픈 액세스 원문 PDF가 없어 심층 분석을 진행할 수 없습니다."
            )
        try:
            await run_deep_analysis(db, paper, x_gemini_api_key)
        except pdf_extract.PdfExtractionError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    return to_paper_detail(result)
