"""Orchestrates Excel export: analyzes each selected paper, compares the
batch if enough succeeded, then hands everything to
services/excel_export_service.py to render as a workbook.

An export should almost never fail outright just because AI analysis or
comparison isn't available (e.g. no OPENAI_API_KEY configured, or fewer
than settings.COMPARISON_MIN_PAPERS papers selected) — the Summary Table
sheet only needs the papers' existing search metadata, so it always
succeeds. Sheets that depend on AI results degrade gracefully instead,
showing a clear "not analyzed"/"unavailable" note, consistent with how the
paper detail page's Quick Summary cards behave.
"""

import asyncio
import logging

from core.config import get_settings
from schemas.analysis import AnalyzeRequest, PaperAnalysis
from schemas.comparison import ComparisonResult
from schemas.search import PaperResult
from services.ai_analysis_service import analyze_paper
from services.comparison_service import InsufficientAnalysesError, compare_papers
from services.excel_export_service import build_workbook
from services.external.exceptions import OpenAIAnalysisError

logger = logging.getLogger(__name__)


async def generate_export(papers: list[PaperResult]) -> bytes:
    analyses = await _analyze_all(papers)
    successful_analyses = [analysis for analysis in analyses if analysis is not None]

    comparison, comparison_note = await _compare_if_possible(successful_analyses, len(papers))

    return build_workbook(papers, analyses, comparison, comparison_note)


async def _analyze_all(papers: list[PaperResult]) -> list[PaperAnalysis | None]:
    return list(await asyncio.gather(*(_analyze_one(paper) for paper in papers)))


async def _analyze_one(paper: PaperResult) -> PaperAnalysis | None:
    if not paper.abstract:
        logger.info("Skipping AI analysis for %r: no abstract available", paper.title)
        return None
    try:
        return await analyze_paper(AnalyzeRequest(title=paper.title, abstract=paper.abstract))
    except OpenAIAnalysisError as exc:
        logger.warning("AI analysis failed for %r: %s", paper.title, exc)
        return None


async def _compare_if_possible(
    successful_analyses: list[PaperAnalysis], total_papers: int
) -> tuple[ComparisonResult | None, str | None]:
    minimum = get_settings().COMPARISON_MIN_PAPERS

    if len(successful_analyses) < minimum:
        return None, (
            f"AI comparison requires at least {minimum} successfully analyzed papers; "
            f"{len(successful_analyses)} of {total_papers} succeeded."
        )

    try:
        return await compare_papers(successful_analyses), None
    except InsufficientAnalysesError as exc:
        # Shouldn't happen given the check above, but keep the export
        # resilient rather than raising out of an otherwise-successful export.
        return None, str(exc)
    except OpenAIAnalysisError as exc:
        logger.warning("AI comparison failed: %s", exc)
        return None, "AI comparison is currently unavailable."
