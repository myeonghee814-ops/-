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
import logging
import re

import httpx

from app.core.config import settings
from app.services.semantic_scholar_service import Candidate

logger = logging.getLogger(__name__)


def _log_gemini_failure(stage: str, exc: Exception) -> None:
    """Every Gemini-calling stage degrades silently to the caller (that's
    the whole point of ai_degraded), but the actual cause - 429 quota
    exceeded vs. 503 overloaded vs. a timeout vs. something else entirely -
    would otherwise be lost. Logging it here is the only way to tell those
    apart after the fact from the server console/log file."""

    if isinstance(exc, httpx.HTTPStatusError):
        logger.warning(
            "Gemini %s failed: HTTP %s - %s",
            stage,
            exc.response.status_code,
            exc.response.text[:500],
        )
    elif isinstance(exc, httpx.TimeoutException):
        logger.warning("Gemini %s failed: request timed out (%s)", stage, exc)
    elif isinstance(exc, httpx.HTTPError):
        logger.warning("Gemini %s failed: network error - %s", stage, exc)
    else:
        logger.warning("Gemini %s failed: %s - %s", stage, type(exc).__name__, exc)

QUERY_EXPANSION_SYSTEM_PROMPT = """\
You are a bilingual (Korean/English) search assistant for battery researchers. \
The user will type a search keyword in Korean, English, or bare scientific \
shorthand (chemical formulas, abbreviations like LHCE, LiFSI, TEMPO, NCA). \
The user should never need to know the correct English scientific term.

Expand/translate the keyword into an effective academic search-engine query \
using standard English battery/electrochemistry terminology and relevant \
synonyms (e.g. an additive abbreviation should be paired with its full \
chemical name; a Korean material name should be translated to its standard \
English term).

IMPORTANT - the target search engine's query field is a PLAIN KEYWORD/PHRASE \
list, not a boolean query language: it does NOT understand quotes, \
parentheses, or the words AND/OR as operators - it matches them as literal \
text, which makes the whole query match nothing. Never wrap terms in quotes, \
never use parentheses, and never join concepts with the words AND/OR. \
Instead, just place every relevant keyword/synonym/phrase next to the \
others separated by plain spaces, exactly like typing into a simple search \
box (e.g. "high-nickel cathode NCM NMC cycling stability", not \
'("high-nickel cathode" OR NCM OR NMC) AND "cycling stability"').

Respond ONLY with JSON of this exact shape:
{"english_query": "<plain space-separated search query string, no quotes/parentheses/AND/OR>", "expanded_terms": ["<term1>", "<term2>", ...]}
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
  "result_summary": "<Korean, 2-4문장: 핵심 정량 결과(용량 유지율, 쿨롱 효율, 율속 특성 등), \
이 연구의 새로운 점, 강점, 한계를 하나로 종합한 요약>"
}
"""

EXTRACTION_BATCH_SYSTEM_PROMPT = """\
You are a senior battery researcher extracting structured information from a \
list of papers (title + abstract) for a Korean colleague who has not read \
the full papers yet. Be precise and concise. If a field is not discernible \
from a paper's abstract, use "정보 없음" for that paper - never invent data.

Material/chemistry fields (cathode, anode, electrolyte, voltage_window, \
cell_type) should use standard scientific notation/formulas (e.g. NCA, \
NMC811, LiPF6, Li metal) exactly as commonly written even in Korean papers - \
do not force-translate chemical names. All other fields must be written in \
natural Korean.

Respond ONLY with JSON of this exact shape, one entry per paper given, \
covering every index:
{"analyses": [
  {
    "index": <int>,
    "cathode": "<material, e.g. NCA, NMC811, LFP, or '정보 없음'>",
    "anode": "<material, e.g. graphite, Li metal, silicon, or '정보 없음'>",
    "electrolyte": "<electrolyte/additive system, or '정보 없음'>",
    "voltage_window": "<e.g. '3.0-4.3 V', or '정보 없음'>",
    "cell_type": "<e.g. coin cell (half-cell), pouch full-cell, or '정보 없음'>",
    "experimental_conditions": "<Korean, 1-3문장: 사이클링 조건, C-rate, 온도, 테스트 셋업>",
    "result_summary": "<Korean, 2-4문장: 핵심 정량 결과(용량 유지율, 쿨롱 효율, 율속 특성 등), \
이 연구의 새로운 점, 강점, 한계를 하나로 종합한 요약>"
  }, ...
]}
"""


EXTRACTION_DEEP_SYSTEM_PROMPT = """\
You are a senior battery researcher extracting detailed experimental \
information from the full body text of a paper (not just its abstract) for \
a Korean colleague. The abstract alone rarely states exact electrolyte \
compositions or voltage windows - that detail lives in the Methods/\
Experimental section of the full text, which you have here. Be precise and \
concise. If a field is not discernible from the text, use "정보 없음" - \
never invent data.

Distinguish the BASE (control/baseline) electrolyte from the TEST \
(experimental/comparison) electrolyte where the paper studies an additive or \
a modified formulation against a baseline - if the paper only uses one \
electrolyte system throughout, put it in base_electrolyte and use "정보 없음" \
for test_electrolyte.

Material/chemistry fields (electrolyte compositions, cell type) should use \
standard scientific notation/formulas (e.g. 1M LiPF6 in EC/DMC, NCM811, Li \
metal) exactly as commonly written even in Korean papers - do not force-\
translate chemical names. All other fields must be written in natural \
Korean.

A list of candidate figure/table caption lines detected in the text is \
provided as a hint for key_findings - use it if relevant, but the body text \
itself is the source of truth.

Respond ONLY with JSON of this exact shape:
{
  "base_electrolyte": "<베이스(기준) 전해액 조성, 또는 '정보 없음'>",
  "test_electrolyte": "<실험(비교) 전해액 조성, 또는 '정보 없음'>",
  "voltage_range": "<사이클링에 사용된 전압 범위, 예: '3.0-4.3 V', 또는 '정보 없음'>",
  "cell_type_detail": "<전지 형태 상세, 예: 'coin cell (half-cell), 2032 type', 또는 '정보 없음'>",
  "key_findings": "<Figure/Table에 근거한 핵심 정량 결과 (한국어, 2-4문장)>",
  "summary": "<이 논문의 새로운 점, 강점, 한계를 종합한 요약 (한국어, 2-4문장)>"
}
"""

COMPOUND_CATEGORY_EXPANSION_SYSTEM_PROMPT = """\
You are a battery electrolyte chemistry expert. The user typed a chemical \
CATEGORY/FAMILY reference (not a specific compound) into a battery \
electrolyte additive/solvent search field - e.g. "불소계" (fluorine-based), \
"황계 첨가제" (sulfur-based additive), "nitrile-based".

List 3-5 well-known, real, specific electrolyte additive/solvent compound \
names (standard abbreviations/formulas, e.g. LiFSI, FEC, VC, PRS, TPP) that \
belong to this category and are commonly discussed in battery research. \
Only include compounds you are confident are real and correctly \
categorized - never invent a name, and return an empty list rather than \
guess if you are not confident anything belongs to this category.

Respond ONLY with JSON of this exact shape:
{"compounds": ["<compound1>", "<compound2>", ...]}
"""


GEMINI_URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# 429 (quota exceeded) is retried once at most - if the daily free-tier quota
# is exhausted, a second retry within the same window won't help either.
# 503 (transient overload) gets more retries since it can clear at any moment.
_MAX_RETRIES_BY_STATUS = {429: 1, 503: 3}
_MIN_RETRY_DELAY_SECONDS = 30.0

# A hung connection (no response at all) is at least as recoverable as a
# 503 - retry it the same way, but there's no Retry-After to honor, so a
# short fixed delay before trying again is enough.
_MAX_TIMEOUT_RETRIES = 3
_TIMEOUT_RETRY_DELAY_SECONDS = 3.0
_REQUEST_TIMEOUT_SECONDS = 15.0


def _retry_delay_seconds(resp: httpx.Response) -> float:
    """Determine how long to wait before retrying a 429/503 Gemini response.
    Prefers the server-provided delay (Retry-After header, or the
    RetryInfo/message text in Gemini's error body) over a fixed backoff -
    Gemini's daily quota errors ask for ~55s, far longer than a naive
    fixed delay would allow. Falls back to _MIN_RETRY_DELAY_SECONDS.
    """

    retry_after = resp.headers.get("retry-after")
    if retry_after:
        try:
            return max(float(retry_after), _MIN_RETRY_DELAY_SECONDS)
        except ValueError:
            pass

    try:
        error = resp.json().get("error", {})
    except ValueError:
        error = {}

    for detail in error.get("details", []):
        if detail.get("@type", "").endswith("RetryInfo"):
            match = re.match(r"([\d.]+)s?", detail.get("retryDelay", ""))
            if match:
                return max(float(match.group(1)), _MIN_RETRY_DELAY_SECONDS)

    match = re.search(r"retry in ([\d.]+)s", error.get("message", ""), re.IGNORECASE)
    if match:
        return max(float(match.group(1)), _MIN_RETRY_DELAY_SECONDS)

    return _MIN_RETRY_DELAY_SECONDS


def _parse_json_object(text: str) -> dict:
    """Parse the first valid JSON object out of `text`, tolerating any
    trailing content Gemini's JSON mode occasionally appends after it."""

    obj, _ = json.JSONDecoder().raw_decode(text.lstrip())
    return obj


async def _generate_json(
    system_prompt: str,
    user_payload: dict,
    gemini_api_key: str | None = None,
    *,
    stage: str = "Gemini call",
) -> dict:
    """Call Gemini's native generateContent endpoint in JSON mode and parse
    the response. Uses the ?key= query-param auth Gemini's REST API expects
    (not an OpenAI-style Authorization header).

    `gemini_api_key`, when given, is the caller's own key (e.g. from the
    X-Gemini-Api-Key header) and takes priority over the server's .env key -
    this lets each user spend their own free-tier quota instead of sharing
    the server's.

    Every attempt's outcome (429/503 status, or a timeout) is logged as it
    happens, not just once the whole call finally gives up - the pipeline's
    own search-time-budget can cancel this coroutine mid-retry (a plain
    TimeoutError from the caller's asyncio.wait_for, not from httpx), which
    would otherwise erase the actual HTTP cause with no trace of it ever
    having been observed.
    """

    api_key = gemini_api_key or settings.gemini_api_key
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY가 설정되지 않았습니다. backend/.env 파일에 추가하거나 "
            "요청에 본인의 API 키를 포함해 다시 시도해주세요. "
            "(무료 발급: https://aistudio.google.com/apikey)"
        )

    logger.info(
        "Gemini %s: using %s API key",
        stage,
        "caller-provided (X-Gemini-Api-Key)" if gemini_api_key else "server .env",
    )

    url = GEMINI_URL_TEMPLATE.format(model=settings.gemini_model)
    body = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"parts": [{"text": json.dumps(user_payload)}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }

    attempt = 0
    timeout_attempt = 0
    async with httpx.AsyncClient() as client:
        while True:
            try:
                resp = await client.post(
                    url, params={"key": api_key}, json=body, timeout=_REQUEST_TIMEOUT_SECONDS
                )
            except httpx.TimeoutException:
                logger.warning(
                    "Gemini %s: request timed out (attempt %d/%d)",
                    stage,
                    timeout_attempt + 1,
                    _MAX_TIMEOUT_RETRIES + 1,
                )
                if timeout_attempt >= _MAX_TIMEOUT_RETRIES:
                    raise
                await asyncio.sleep(_TIMEOUT_RETRY_DELAY_SECONDS)
                timeout_attempt += 1
                continue

            max_retries = _MAX_RETRIES_BY_STATUS.get(resp.status_code, 0)
            if resp.status_code in (429, 503):
                logger.warning(
                    "Gemini %s: HTTP %s received (attempt %d/%d) - %s",
                    stage,
                    resp.status_code,
                    attempt + 1,
                    max_retries + 1,
                    resp.text[:300],
                )
                if attempt < max_retries:
                    await asyncio.sleep(_retry_delay_seconds(resp))
                    attempt += 1
                    continue
            resp.raise_for_status()
            data = resp.json()
            break

    text = data["candidates"][0]["content"]["parts"][0]["text"]
    return _parse_json_object(text)


def _truncate(text: str, limit: int = 1000) -> str:
    return text if len(text) <= limit else text[:limit] + "..."


# The Methods/Experimental and Results sections that matter for deep
# analysis are almost always well within a paper's first ~20k characters
# (~5k tokens) - truncating there keeps the call fast and cheap without
# losing the detail this stage exists to recover, and avoids a huge full-text
# paper blowing past the per-call time budget.
_DEEP_ANALYSIS_BODY_TEXT_LIMIT = 20_000


async def expand_search_query(
    keyword: str, gemini_api_key: str | None = None
) -> tuple[str, list[str]]:
    """Translate/expand a Korean, English, or shorthand keyword into an
    effective English Semantic Scholar search query. Returns (english_query, expanded_terms).
    """

    try:
        data = await _generate_json(
            QUERY_EXPANSION_SYSTEM_PROMPT, {"keyword": keyword}, gemini_api_key, stage="query expansion"
        )
    except (httpx.HTTPError, json.JSONDecodeError, KeyError, IndexError) as exc:
        _log_gemini_failure("query expansion", exc)
        raise RuntimeError(f"AI 검색어 확장에 실패했습니다: {exc}") from exc

    english_query = str(data.get("english_query", "")).strip() or keyword
    expanded_terms = [str(t) for t in data.get("expanded_terms", [])]
    return english_query, expanded_terms


async def rerank_candidates(
    keyword: str, candidates: list[Candidate], gemini_api_key: str | None = None
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
        data = await _generate_json(RANKING_SYSTEM_PROMPT, payload, gemini_api_key, stage="re-ranking")
    except (httpx.HTTPError, json.JSONDecodeError, KeyError, IndexError) as exc:
        _log_gemini_failure("re-ranking", exc)
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


async def extract_battery_analysis(
    title: str, abstract: str, gemini_api_key: str | None = None
) -> dict:
    """Extract battery snapshot + Korean research analysis fields for one paper."""

    try:
        return await _generate_json(
            EXTRACTION_SYSTEM_PROMPT,
            {"title": title, "abstract": abstract},
            gemini_api_key,
            stage="battery extraction (individual)",
        )
    except (httpx.HTTPError, json.JSONDecodeError, KeyError, IndexError) as exc:
        _log_gemini_failure("battery extraction (individual)", exc)
        raise RuntimeError(f"AI 배터리 정보 추출에 실패했습니다: {exc}") from exc


async def extract_battery_analysis_batch(
    papers: list[tuple[str, str]], gemini_api_key: str | None = None
) -> dict[int, dict]:
    """Extract battery snapshot + Korean research analysis fields for
    several papers (title, abstract) in a single Gemini call, instead of
    one call per paper - the common case for a fresh top-N search result.

    Returns {index: analysis} keyed by position in `papers`. An index
    missing from Gemini's response (a rare JSON-shape slip, not a call
    failure) is simply absent from the result - the caller falls back to
    a "정보 없음" default for just that paper instead of retrying.
    """

    if not papers:
        return {}

    payload = {
        "papers": [
            {"index": i, "title": title, "abstract": _truncate(abstract)}
            for i, (title, abstract) in enumerate(papers)
        ]
    }

    try:
        data = await _generate_json(
            EXTRACTION_BATCH_SYSTEM_PROMPT, payload, gemini_api_key, stage="battery extraction (batch)"
        )
    except (httpx.HTTPError, json.JSONDecodeError, KeyError, IndexError) as exc:
        _log_gemini_failure("battery extraction (batch)", exc)
        raise RuntimeError(f"AI 배터리 정보 일괄 추출에 실패했습니다: {exc}") from exc

    results: dict[int, dict] = {}
    for entry in data.get("analyses", []):
        idx = entry.get("index")
        if idx is None or not (0 <= idx < len(papers)):
            continue
        results[idx] = entry
    return results


async def extract_deep_analysis(
    title: str,
    body_text: str,
    candidate_figure_captions: list[str],
    gemini_api_key: str | None = None,
) -> dict:
    """On-demand, full-text-PDF version of extract_battery_analysis: recovers
    experiment-level detail (exact electrolyte compositions, voltage window,
    cell type) that an abstract alone usually can't. Only called when the
    user explicitly requests it for one paper that has an open-access PDF -
    never as part of the regular search results list."""

    payload = {
        "title": title,
        "body_text": _truncate(body_text, _DEEP_ANALYSIS_BODY_TEXT_LIMIT),
        "candidate_figure_captions": candidate_figure_captions,
    }

    try:
        return await _generate_json(
            EXTRACTION_DEEP_SYSTEM_PROMPT, payload, gemini_api_key, stage="deep analysis"
        )
    except (httpx.HTTPError, json.JSONDecodeError, KeyError, IndexError) as exc:
        _log_gemini_failure("deep analysis", exc)
        raise RuntimeError(f"AI 심층 분석에 실패했습니다: {exc}") from exc


async def expand_compound_category(
    category_text: str, gemini_api_key: str | None = None
) -> list[str]:
    """Expands a chemical CATEGORY/FAMILY reference (e.g. "불소계", "황계
    첨가제") into 3-5 specific, real compound names, for when the additive/
    solvent search field names a category rather than a specific compound.
    See battery_term_mapping.looks_like_compound_category, which decides
    whether this is even worth calling."""

    try:
        data = await _generate_json(
            COMPOUND_CATEGORY_EXPANSION_SYSTEM_PROMPT,
            {"category": category_text},
            gemini_api_key,
            stage="compound category expansion",
        )
    except (httpx.HTTPError, json.JSONDecodeError, KeyError, IndexError) as exc:
        _log_gemini_failure("compound category expansion", exc)
        raise RuntimeError(f"AI 화합물 계열 확장에 실패했습니다: {exc}") from exc

    return [str(c) for c in data.get("compounds", [])]
