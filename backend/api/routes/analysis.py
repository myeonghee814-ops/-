import logging

from fastapi import APIRouter, HTTPException

from schemas.analysis import AnalyzeRequest, PaperAnalysis
from services.ai_analysis_service import analyze_paper
from services.external.exceptions import OpenAIAnalysisError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analyze", tags=["analysis"])


@router.post("", response_model=PaperAnalysis)
async def analyze(request: AnalyzeRequest) -> PaperAnalysis:
    try:
        return await analyze_paper(request)
    except OpenAIAnalysisError as exc:
        logger.error("AI analysis failed: %s", exc)
        raise HTTPException(status_code=502, detail="AI analysis is currently unavailable") from exc
