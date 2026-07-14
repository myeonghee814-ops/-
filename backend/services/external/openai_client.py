"""Thin client for the OpenAI Responses API.

Owns everything specific to this provider: request construction, the
strict JSON-schema response format, and response parsing. Service layers
(services/ai_analysis_service.py, services/comparison_service.py) only
assemble prompt content and never touch the OpenAI SDK directly.
"""

import json

from openai import APIError
from pydantic import ValidationError

from core.config import get_settings
from core.http_clients import get_openai_client
from schemas.analysis import PaperAnalysis
from schemas.comparison import ComparisonResult
from services.external.exceptions import OpenAIAnalysisError

# Every field must be listed as required by OpenAI's strict structured-output
# mode; genuinely optional fields are made nullable via a ["string", "null"]
# type instead of being omitted from "required".
_ANALYSIS_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": ["string", "null"]},
        "authors": {"type": "array", "items": {"type": "string"}},
        "journal": {"type": ["string", "null"]},
        "battery_system": {"type": ["string", "null"]},
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
        "battery_system",
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

_COMPARISON_TABLE_ROW_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": ["string", "null"]},
        "electrolyte": {"type": ["string", "null"]},
        "salt": {"type": ["string", "null"]},
        "additive": {"type": ["string", "null"]},
        "cathode": {"type": ["string", "null"]},
        "anode": {"type": ["string", "null"]},
        "separator": {"type": ["string", "null"]},
        "cell_type": {"type": ["string", "null"]},
        "voltage_window": {"type": ["string", "null"]},
        "temperature": {"type": ["string", "null"]},
        "cycle_condition": {"type": ["string", "null"]},
        "main_finding": {"type": ["string", "null"]},
        "advantages": {"type": ["string", "null"]},
        "limitations": {"type": ["string", "null"]},
    },
    "required": [
        "title",
        "electrolyte",
        "salt",
        "additive",
        "cathode",
        "anode",
        "separator",
        "cell_type",
        "voltage_window",
        "temperature",
        "cycle_condition",
        "main_finding",
        "advantages",
        "limitations",
    ],
    "additionalProperties": False,
}

_COMPARISON_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "paper_count": {"type": "integer"},
        "common_experimental_conditions": {"type": "array", "items": {"type": "string"}},
        "differences": {"type": "array", "items": {"type": "string"}},
        "frequently_used_electrolytes": {"type": "array", "items": {"type": "string"}},
        "frequently_used_additives": {"type": "array", "items": {"type": "string"}},
        "most_common_cathode": {"type": ["string", "null"]},
        "most_common_anode": {"type": ["string", "null"]},
        "research_trend": {"type": ["string", "null"]},
        "research_gap": {"type": ["string", "null"]},
        "potential_future_direction": {"type": ["string", "null"]},
        "comparison_table": {"type": "array", "items": _COMPARISON_TABLE_ROW_SCHEMA},
    },
    "required": [
        "paper_count",
        "common_experimental_conditions",
        "differences",
        "frequently_used_electrolytes",
        "frequently_used_additives",
        "most_common_cathode",
        "most_common_anode",
        "research_trend",
        "research_gap",
        "potential_future_direction",
        "comparison_table",
    ],
    "additionalProperties": False,
}


async def _request_structured_json(system_prompt: str, user_content: str, schema_name: str, json_schema: dict) -> dict:
    """Send a Responses API request constrained to the given JSON schema.

    Raises OpenAIAnalysisError if the API key isn't configured, the request
    fails, or the response body isn't valid JSON.
    """
    settings = get_settings()
    if not settings.OPENAI_API_KEY:
        raise OpenAIAnalysisError("OPENAI_API_KEY is not configured")

    client = get_openai_client()

    try:
        response = await client.responses.create(
            model=settings.OPENAI_MODEL,
            instructions=system_prompt,
            input=user_content,
            text={
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "schema": json_schema,
                    "strict": True,
                }
            },
        )
    except APIError as exc:
        raise OpenAIAnalysisError(f"OpenAI request failed: {exc}") from exc

    try:
        return json.loads(response.output_text)
    except json.JSONDecodeError as exc:
        raise OpenAIAnalysisError(f"Unexpected OpenAI response shape: {exc}") from exc


async def analyze(system_prompt: str, user_content: str) -> PaperAnalysis:
    """Send a paper analysis request to OpenAI and return the parsed result."""
    payload = await _request_structured_json(system_prompt, user_content, "paper_analysis", _ANALYSIS_RESPONSE_SCHEMA)
    try:
        return PaperAnalysis.model_validate(payload)
    except ValidationError as exc:
        raise OpenAIAnalysisError(f"Unexpected OpenAI response shape: {exc}") from exc


async def compare_papers(system_prompt: str, user_content: str) -> ComparisonResult:
    """Send a cross-paper comparison request to OpenAI and return the parsed result."""
    payload = await _request_structured_json(
        system_prompt, user_content, "paper_comparison", _COMPARISON_RESPONSE_SCHEMA
    )
    try:
        return ComparisonResult.model_validate(payload)
    except ValidationError as exc:
        raise OpenAIAnalysisError(f"Unexpected OpenAI response shape: {exc}") from exc
