"""AI paper analysis: extracts structured battery-research metadata from a
paper's title plus abstract or full PDF text, via OpenAI's Responses API.

This module only assembles the prompt content and delegates to
services/external/openai_client.py for the actual API call — it has no
knowledge of the OpenAI SDK or response format.
"""

from prompts.paper_analysis import SYSTEM_PROMPT
from schemas.analysis import AnalyzeRequest, PaperAnalysis
from services.external import openai_client


async def analyze_paper(request: AnalyzeRequest) -> PaperAnalysis:
    user_content = _build_user_content(request)
    return await openai_client.analyze(SYSTEM_PROMPT, user_content)


def _build_user_content(request: AnalyzeRequest) -> str:
    parts = [f"Title: {request.title}"]
    if request.abstract:
        parts.append(f"Abstract:\n{request.abstract}")
    if request.pdf_text:
        parts.append(f"Full text:\n{request.pdf_text}")
    return "\n\n".join(parts)
