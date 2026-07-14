"""Comparison engine: given a batch of already-analyzed papers, generates an
AI cross-paper comparison (common conditions, differences, frequency
patterns, research trend/gap/future direction) plus a per-paper comparison
table.

This module only enforces the minimum-batch-size rule and assembles prompt
content from the analyses; services/external/openai_client.py owns the
actual OpenAI call, mirroring the split used by ai_analysis_service.py.

Note: this operates on whatever batch of PaperAnalysis objects the caller
supplies — there's no server-side tracking of "papers analyzed so far" yet
(analyses aren't persisted; see docs/ARCHITECTURE.md). The comparison is
generated automatically as soon as a batch meeting the minimum size is
submitted, with no separate "run comparison" step required.
"""

import json

from core.config import get_settings
from prompts.paper_comparison import SYSTEM_PROMPT
from schemas.analysis import PaperAnalysis
from schemas.comparison import ComparisonResult
from services.external import openai_client


class InsufficientAnalysesError(Exception):
    """Raised when fewer than settings.COMPARISON_MIN_PAPERS analyses are supplied."""


async def compare_papers(analyses: list[PaperAnalysis]) -> ComparisonResult:
    minimum = get_settings().COMPARISON_MIN_PAPERS
    if len(analyses) < minimum:
        raise InsufficientAnalysesError(
            f"At least {minimum} analyzed papers are required to generate a comparison; "
            f"{len(analyses)} provided."
        )

    user_content = _build_user_content(analyses)
    result = await openai_client.compare_papers(SYSTEM_PROMPT, user_content)

    # Trust our own count over whatever the model reported.
    result.paper_count = len(analyses)
    return result


def _build_user_content(analyses: list[PaperAnalysis]) -> str:
    papers = [analysis.model_dump() for analysis in analyses]
    return json.dumps({"papers": papers})
