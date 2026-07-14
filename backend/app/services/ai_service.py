"""AI stages of the pipeline: bilingual query expansion, relevance
re-ranking, and battery-metadata extraction, all via Google's Gemini API
native REST endpoint (generateContent) in JSON mode. Gemini's free tier
requires no billing/credit card, unlike the OpenAI API.

The AI is prompted to behave like a senior battery researcher, not a
generic summarizer: ranking weighs chemistry/electrolyte/cell-type/
experimental similarity alongside keyword match and journal/year, and
every recommendation answers, in natural Korean, "왜 이 논문을 읽어야 하는가?"
(why should a battery researcher read this). Users search in Korean,
English, or bare scientific shorthand (e.g. "LiFSI", "TEMPO") - query
expansion converts that into an effective English Semantic Scholar search
before anything else runs.
"""

import asyncio
import json

import httpx

from app.core.config import settings
from app.services.semantic_scholar_service import Candidate

QUERY_EXPANSION_SYSTEM_PROMPT = """\
You are a bilingual (Korean/English) search assistant for battery researchers. \
The user will type a search keyword in Korean, English, or bare scientific \
shorthand (chemical formulas, abbreviations like LHCE, LiFSI, TEMPO, NCA). \
The user should never need to know the correct English scientific term.

Expand/translate the keyword into an effective academic search-engine query \
using standard English battery/electrochemistry terminology and relevant \
synonyms (e.g. an additive abbreviation should be paired with its full \
chemical name; a Korean material name should be translated to its standard \
English term). Combine multiple concepts with AND/OR as appropriate.

Respond ONLY with JSON of this exact shape:
{"english_query": "<search query string>", "expanded_terms": ["<term1>", "<term2>", ...]}
"""

RANKING_SYSTEM_PROMPT = """\
You are a senior battery researcher (electrochemistry, lithium-ion cells, \
electrolytes, additives, cathodes/anodes, separators) helping a Korean \
colleague triage a literature search. You will be given the user's original \
search keyword and a list of candidate papers (index, title, journal, year, \
abstract).

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

For each candidate also write "why_selected" IN NATURAL KOREAN: one or two \
sentences answering, specifically, "왜 이 논문을 읽어야 하는가?" (why should a \
battery researcher read this paper) in the context of the given keyword. Be \
concrete (mention the actual chemistry/mechanism/result), not generic. \
Chemical names/formulas/abbreviations (NCA, LiFSI, CEI, etc.) may stay in \
their standard scientific notation even inside the Korean sentence - only the \
surrounding explanation must be Korean.

Example why_selected: "고전압 NCA Full Cell을 사용하였으며, 황계 첨가제를 이용한 \
CEI 안정화 효과를 평가한 최신 연구입니다."

Respond ONLY with JSON of the shape:
{"rankings": [{"index": <int>, "relevance_score": <0-100 number>, "why_selected": "<Korean text>"}, ...]}
One entry per candidate, covering every index given.
"""

EXTRACTION_SYSTEM_PROMPT = """\
You are a senior battery researcher extracting structured information from a \
paper's title and abstract for a Korean colleague who has not read the full \
paper yet. Be precise and concise. If a field is not discernible from the \
abstract, use "정보 없음" - never invent data.

Material/chemistry fields (cathode, anode, electrolyte, voltage_window, \
cell_type) should use standard scientific notation/formulas (e.g. NCA, \
NMC811, LiPF6, Li metal) exactly as commonly written even in Korean papers - \
do not force-translate chemical names. All other fields must be written in \
natural Korean.

Respond ONLY with JSON of this exact shape:
{
  "cathode": "<material, e.g. NCA, NMC811, LFP, or '정보 없음'>",
  "anode": "<material, e.g. graphite, Li metal, silicon, or '정보 없음'>",
  "electrolyte": "<electrolyte/additive system, or '정보 없음'>",
  "voltage_window": "<e.g. '3.0-4.3 V', or '정보 없음'>",
  "cell_type": "<e.g. coin cell (half-cell), pouch full-cell, or '정보 없음'>",
  "experimental_conditions": "<Korean, 1-3문장: 사이클링 조건, C-rate, 온도, 테스트 셋업>",
  "performance_summary": "<Korean, 1-3문장: 용량 유지율, 쿨롱 효율, 율속 특성 등 핵심 정량 결과>",
  "innovation": "<Korean, 1-2문장: 이 연구의 새로운 점>",
  "advantages": "<Korean, 1-2문장: 제안된 접근법의 강점>",
  "limitations": "<Korean, 1-2문장: 명시적 또는 암묵적 한계/트레이드오프>"
}
"""


GEMINI_URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


async def _generate_json(system_prompt: str, user_payload: dict, retries: int = 2) -> dict:
    """Call Gemini's native generateContent endpoint in JSON mode and parse
    the response. Uses the ?key= query-param auth Gemini's REST API expects
    (not an OpenAI-style Authorization header). Retries a couple of times
    on 429/503 - transient rate-limit/overload responses - before giving up.
    """

    if not settings.gemini_api_key:
        raise RuntimeError(
            "GEMINI_API_KEY가 설정되지 않았습니다. backend/.env 파일에 추가한 뒤 "
            "다시 시도해주세요. (무료 발급: https://aistudio.google.com/apikey)"
        )

    url = GEMINI_URL_TEMPLATE.format(model=settings.gemini_model)
    body = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"parts": [{"text": json.dumps(user_payload)}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }

    async with httpx.AsyncClient() as client:
        for attempt in range(retries + 1):
            resp = await client.post(
                url, params={"key": settings.gemini_api_key}, json=body, timeout=60
            )
            if resp.status_code in (429, 503) and attempt < retries:
                await asyncio.sleep(2 * (attempt + 1))
                continue
            resp.raise_for_status()
            data = resp.json()
            break

    text = data["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(text)


def _truncate(text: str, limit: int = 1000) -> str:
    return text if len(text) <= limit else text[:limit] + "..."


async def expand_search_query(keyword: str) -> tuple[str, list[str]]:
    """Translate/expand a Korean, English, or shorthand keyword into an
    effective English Semantic Scholar search query. Returns (english_query, expanded_terms).
    """

    try:
        data = await _generate_json(QUERY_EXPANSION_SYSTEM_PROMPT, {"keyword": keyword})
    except (httpx.HTTPError, json.JSONDecodeError, KeyError, IndexError) as exc:
        raise RuntimeError(f"AI 검색어 확장에 실패했습니다: {exc}") from exc

    english_query = str(data.get("english_query", "")).strip() or keyword
    expanded_terms = [str(t) for t in data.get("expanded_terms", [])]
    return english_query, expanded_terms


async def rerank_candidates(
    keyword: str, candidates: list[Candidate]
) -> list[tuple[Candidate, float, str]]:
    """Score every candidate against the keyword and return them sorted
    best-first as (candidate, relevance_score, why_selected) tuples."""

    if not candidates:
        return []

    payload = {
        "keyword": keyword,
        "candidates": [
            {
                "index": i,
                "title": c.title,
                "journal": c.journal,
                "year": c.year,
                "abstract": _truncate(c.abstract),
            }
            for i, c in enumerate(candidates)
        ],
    }

    try:
        data = await _generate_json(RANKING_SYSTEM_PROMPT, payload)
    except (httpx.HTTPError, json.JSONDecodeError, KeyError, IndexError) as exc:
        raise RuntimeError(f"AI 재순위화에 실패했습니다: {exc}") from exc

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
    """Extract battery snapshot + Korean research analysis fields for one paper."""

    try:
        return await _generate_json(EXTRACTION_SYSTEM_PROMPT, {"title": title, "abstract": abstract})
    except (httpx.HTTPError, json.JSONDecodeError, KeyError, IndexError) as exc:
        raise RuntimeError(f"AI 배터리 정보 추출에 실패했습니다: {exc}") from exc
