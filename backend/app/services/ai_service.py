"""AI stages of the pipeline: relevance re-ranking and battery-metadata
extraction, both via the OpenAI Chat Completions API in JSON mode.

The AI is prompted to behave like a senior battery researcher, not a
generic summarizer: ranking weighs chemistry/electrolyte/cell-type/
experimental similarity alongside keyword match and journal/year, and
extraction always answers "why should a battery researcher read this".
"""

import json

from openai import AsyncOpenAI
from openai import OpenAIError

from app.core.config import settings
from app.services.pubmed_service import Candidate

RANKING_SYSTEM_PROMPT = """\
You are a senior battery researcher (electrochemistry, lithium-ion cells, \
electrolytes, additives, cathodes/anodes, separators) helping a colleague \
triage a literature search. You will be given a search keyword and a list \
of candidate papers (index, title, journal, year, abstract).

Score EVERY candidate's relevance to the keyword on a 0-100 scale, weighing:
- battery chemistry similarity (cathode/anode materials matching the keyword's chemistry)
- electrolyte / additive similarity
- cell type similarity (coin cell, pouch cell, full cell, half cell)
- experimental similarity (cycling, rate performance, safety, characterization methods)
- application relevance (EV, grid storage, consumer electronics, etc.)
- keyword / topical similarity
- publication recency (newer generally more relevant unless the keyword implies foundational work)
- journal quality/reputation as a secondary signal

Do NOT rely on keyword text-matching alone - reason like a domain expert about \
whether the paper's actual chemistry and experiments matter to someone \
researching the keyword.

For each candidate also write "why_selected": one or two sentences answering, \
specifically, "why should a battery researcher read this paper?" in the context \
of the given keyword. Be concrete (mention the actual chemistry/mechanism/result), \
not generic.

Respond ONLY with JSON of the shape:
{"rankings": [{"index": <int>, "relevance_score": <0-100 number>, "why_selected": "<text>"}, ...]}
One entry per candidate, covering every index given.
"""

EXTRACTION_SYSTEM_PROMPT = """\
You are a senior battery researcher extracting structured information from a \
paper's title and abstract for a fellow researcher who has not read the full \
paper yet. Be precise and concise. If a field is not discernible from the \
abstract, use "Not specified" - never invent data.

Respond ONLY with JSON of this exact shape:
{
  "cathode": "<material, e.g. NCA, NMC811, LFP, or 'Not specified'>",
  "anode": "<material, e.g. graphite, Li metal, silicon, or 'Not specified'>",
  "electrolyte": "<electrolyte/additive system, or 'Not specified'>",
  "voltage_window": "<e.g. '3.0-4.3 V', or 'Not specified'>",
  "cell_type": "<e.g. coin cell (half-cell), pouch full-cell, or 'Not specified'>",
  "experimental_conditions": "<1-3 sentences: cycling protocol, C-rate, temperature, testing setup>",
  "performance_summary": "<1-3 sentences: key quantitative results - capacity retention, coulombic efficiency, rate capability>",
  "innovation": "<1-2 sentences: what is novel about this work>",
  "advantages": "<1-2 sentences: strengths of the proposed approach>",
  "limitations": "<1-2 sentences: stated or implied limitations/tradeoffs>"
}
"""


def _client() -> AsyncOpenAI:
    if not settings.openai_api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Add it to backend/.env to enable AI "
            "re-ranking and battery metadata extraction."
        )
    return AsyncOpenAI(api_key=settings.openai_api_key)


def _truncate(text: str, limit: int = 1000) -> str:
    return text if len(text) <= limit else text[:limit] + "..."


async def rerank_candidates(
    keyword: str, candidates: list[Candidate]
) -> list[tuple[Candidate, float, str]]:
    """Score every candidate against the keyword and return them sorted
    best-first as (candidate, relevance_score, why_selected) tuples."""

    if not candidates:
        return []

    payload = [
        {
            "index": i,
            "title": c.title,
            "journal": c.journal,
            "year": c.year,
            "abstract": _truncate(c.abstract),
        }
        for i, c in enumerate(candidates)
    ]

    client = _client()
    try:
        response = await client.chat.completions.create(
            model=settings.openai_model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": RANKING_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps({"keyword": keyword, "candidates": payload}),
                },
            ],
        )
        data = json.loads(response.choices[0].message.content)
    except (OpenAIError, json.JSONDecodeError, KeyError, IndexError) as exc:
        raise RuntimeError(f"AI re-ranking failed: {exc}") from exc

    rankings = data.get("rankings", [])
    scored: list[tuple[Candidate, float, str]] = []
    for entry in rankings:
        idx = entry.get("index")
        if idx is None or not (0 <= idx < len(candidates)):
            continue
        score = float(entry.get("relevance_score", 0))
        why = str(entry.get("why_selected", "")).strip()
        scored.append((candidates[idx], score, why))

    scored.sort(key=lambda t: t[1], reverse=True)
    return scored


async def extract_battery_analysis(title: str, abstract: str) -> dict:
    """Extract battery snapshot + research analysis fields from one paper."""

    client = _client()
    try:
        response = await client.chat.completions.create(
            model=settings.openai_model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps({"title": title, "abstract": abstract}),
                },
            ],
        )
        return json.loads(response.choices[0].message.content)
    except (OpenAIError, json.JSONDecodeError, KeyError, IndexError) as exc:
        raise RuntimeError(f"AI metadata extraction failed: {exc}") from exc
