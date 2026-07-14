import logging

from fastapi import APIRouter, HTTPException

from schemas.comparison import ComparisonRequest, ComparisonResult
from services.comparison_service import InsufficientAnalysesError, compare_papers
from services.external.exceptions import OpenAIAnalysisError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/compare", tags=["comparison"])


@router.post("", response_model=ComparisonResult)
async def compare(request: ComparisonRequest) -> ComparisonResult:
    try:
        return await compare_papers(request.analyses)
    except InsufficientAnalysesError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OpenAIAnalysisError as exc:
        logger.error("Comparison failed: %s", exc)
        raise HTTPException(status_code=502, detail="AI comparison is currently unavailable") from exc
