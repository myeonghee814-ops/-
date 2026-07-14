"""Thin client for the OpenAI Responses API.

Owns everything specific to this provider: request construction, the
strict JSON-schema response format, and response parsing. The service
layer (services/ai_analysis_service.py) only assembles prompt content and
never touches the OpenAI SDK directly.
"""

import json

from openai import APIError, AsyncOpenAI
from pydantic import ValidationError

from core.config import get_settings
from schemas.analysis import PaperAnalysis
from services.external.exceptions import OpenAIAnalysisError

# Every field must be listed as required by OpenAI's strict structured-output
# mode; genuinely optional fields are made nullable via a ["string", "null"]
# type instead of being omitted from "required".
_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": ["string", "null"]},
        "authors": {"type": "array", "items": {"type": "string"}},
        "journal": {"type": ["string", "null"]},
        "electrolyte": {"type": ["string", "null"]},
        "salt": {"type": ["string", "null"]},
        "solvent": {"type": ["string", "null"]},
        "additive": {"type": ["string", "null"]},
        "cathode": {"type": ["string", "null"]},
        "anode": {"type": ["string", "null"]},
        "separator": {"type": ["string", "null"]},
        "cell_type": {"type": ["string", "null"]},
        "voltage_window": {"type": ["string", "null"]},
        "temperature": {"type": ["string", "null"]},
        "formation_protocol": {"type": ["string", "null"]},
        "cycle_condition": {"type": ["string", "null"]},
        "rate_capability": {"type": ["string", "null"]},
        "main_findings": {"type": "array", "items": {"type": "string"}},
        "innovation": {"type": ["string", "null"]},
        "advantages": {"type": "array", "items": {"type": "string"}},
        "limitations": {"type": "array", "items": {"type": "string"}},
        "future_work": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "title",
        "authors",
        "journal",
        "electrolyte",
        "salt",
        "solvent",
        "additive",
        "cathode",
        "anode",
        "separator",
        "cell_type",
        "voltage_window",
        "temperature",
        "formation_protocol",
        "cycle_condition",
        "rate_capability",
        "main_findings",
        "innovation",
        "advantages",
        "limitations",
        "future_work",
    ],
    "additionalProperties": False,
}


async def analyze(system_prompt: str, user_content: str) -> PaperAnalysis:
    """Send a paper analysis request to OpenAI and return the parsed result.

    Raises OpenAIAnalysisError if the API key isn't configured, the request
    fails, or the response doesn't parse into a valid PaperAnalysis.
    """
    settings = get_settings()
    if not settings.OPENAI_API_KEY:
        raise OpenAIAnalysisError("OPENAI_API_KEY is not configured")

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY, timeout=settings.EXTERNAL_API_TIMEOUT_SECONDS)

    try:
        response = await client.responses.create(
            model=settings.OPENAI_MODEL,
            instructions=system_prompt,
            input=user_content,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "paper_analysis",
                    "schema": _RESPONSE_SCHEMA,
                    "strict": True,
                }
            },
        )
    except APIError as exc:
        raise OpenAIAnalysisError(f"OpenAI request failed: {exc}") from exc

    try:
        payload = json.loads(response.output_text)
        return PaperAnalysis.model_validate(payload)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise OpenAIAnalysisError(f"Unexpected OpenAI response shape: {exc}") from exc
