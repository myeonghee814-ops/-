"""Static Korean/abbreviation -> standard English battery-domain term
mapping, used as the query-expansion fallback when Gemini is unavailable
(rate-limited, quota exhausted, or the search's time budget has already
run out). Falling back to the raw Korean keyword sends text Semantic
Scholar's English-only index can't match against anything, and returns
nothing useful - this dictionary guarantees at least a handful of accurate
English search terms instead, drawn from common battery-research
vocabulary (materials, cell types, performance metrics).

Also provides correct_material_typos, a separate fuzzy-matching pass over
just the search form's material field (e.g. "Mlid-Ni" -> "Mid-Ni") that
runs unconditionally, before Gemini is even called - a cleaned-up material
name benefits a successful Gemini call too, not just the dictionary
fallback.

This is deliberately a hand-curated draft, not an exhaustive taxonomy -
extend TERM_MAP/KNOWN_MATERIAL_TERMS as real searches surface gaps.
"""

import difflib
import logging
import re

logger = logging.getLogger(__name__)

# Korean phrase/abbreviation -> standard English term. Longest-phrase-first
# matching (see _sorted_patterns) means a multi-word entry like "실리콘 음극"
# is tried before its component words, so it maps to "silicon anode" as one
# unit instead of being split into "silicon" + "anode material" separately.
TERM_MAP: dict[str, str] = {
    # Cathodes
    "하이니켈 양극재": "high-nickel cathode material",
    "하이니켈 양극": "high-nickel cathode",
    "하이니켈": "high-nickel",
    "삼원계 양극재": "NCM cathode material",
    "삼원계 양극": "NCM cathode",
    "삼원계": "NCM",
    "니켈코발트망간": "NCM",
    "니켈코발트알루미늄": "NCA",
    "리튬인산철": "LFP",
    "코발트산리튬": "LCO",
    "망간산리튬": "LMO",
    "니켈망간산화물": "LNMO",
    "양극활물질": "cathode active material",
    "양극재": "cathode material",
    "양극": "cathode",
    # Anodes
    "실리콘 음극재": "silicon anode material",
    "실리콘 음극": "silicon anode",
    "실리콘음극": "silicon anode",
    "실리콘": "silicon",
    "흑연 음극": "graphite anode",
    "흑연": "graphite",
    "리튬 금속 음극": "lithium metal anode",
    "리튬 금속": "lithium metal",
    "리튬메탈": "lithium metal",
    "리튬티타네이트": "LTO",
    "음극활물질": "anode active material",
    "음극재": "anode material",
    "음극": "anode",
    # Electrolytes / additives / solvents
    "전해액 첨가제": "electrolyte additive",
    "전해질 첨가제": "electrolyte additive",
    "고체전해질": "solid electrolyte",
    "고체 전해질": "solid electrolyte",
    "액체전해질": "liquid electrolyte",
    "액체 전해질": "liquid electrolyte",
    "황화물계 고체전해질": "sulfide solid electrolyte",
    "산화물계 고체전해질": "oxide solid electrolyte",
    "고농도 전해질": "high-concentration electrolyte",
    "국소 고농도 전해질": "localized high-concentration electrolyte",
    "전해액": "electrolyte",
    "전해질": "electrolyte",
    "첨가제": "additive",
    "용매": "solvent",
    "카보네이트 용매": "carbonate solvent",
    "불소화 용매": "fluorinated solvent",
    "희석제": "diluent",
    # Interfaces / safety
    "고체전해질 계면": "solid electrolyte interphase",
    "음극 계면 피막": "SEI",
    "양극 계면 피막": "CEI",
    "열폭주": "thermal runaway",
    "안전성": "safety",
    "과충전": "overcharge",
    "분리막": "separator",
    "세라믹 코팅": "ceramic coating",
    "덴드라이트": "dendrite",
    # Cell types
    "코인셀": "coin cell",
    "파우치셀": "pouch cell",
    "파우치 셀": "pouch cell",
    "풀셀": "full cell",
    "하프셀": "half cell",
    "각형셀": "prismatic cell",
    "원통형셀": "cylindrical cell",
    "전고체전지": "all-solid-state battery",
    "전고체 전지": "all-solid-state battery",
    "리튬이온전지": "lithium-ion battery",
    "리튬이온배터리": "lithium-ion battery",
    # Performance / testing
    "사이클 수명": "cycle life",
    "사이클 안정성": "cycling stability",
    "용량 유지율": "capacity retention",
    "율속특성": "rate capability",
    "율속 특성": "rate capability",
    "쿨롱 효율": "coulombic efficiency",
    "쿨롱효율": "coulombic efficiency",
    "저온 성능": "low-temperature performance",
    "고온 성능": "high-temperature performance",
    "임피던스": "impedance",
    "부피 팽창": "volume expansion",
    "리튬 도금": "lithium plating",
    # Applications
    "전기차": "electric vehicle",
    "에너지저장장치": "energy storage system",
    "그리드 저장": "grid storage",
}

# Used only when neither the dictionary above nor a plain ASCII/formula
# token (see _ASCII_TOKEN_RE) matches anything in the keyword - a
# best-effort generic query so the search still returns something instead
# of erroring out on an empty query string.
_DEFAULT_FALLBACK_QUERY = "lithium-ion battery"

# Chemical formulas and abbreviations (NCA, LiFSI, TEMPO, NCM811, ...) are
# already valid English search terms as typed - keep them verbatim rather
# than trying to enumerate every one in TERM_MAP.
_ASCII_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9\-]{1,}")

# Any Hangul syllable block left in `remaining` after TERM_MAP's phrase
# matching never matched anything - see expand_with_dictionary.
_HANGUL_RE = re.compile(r"[가-힣]+")


def _sorted_patterns() -> list[str]:
    return sorted(TERM_MAP, key=len, reverse=True)


# Standard material shorthand/formulas a user might mistype in the search
# form's material field (e.g. "Mlid-Ni" for "Mid-Ni"). Matched via fuzzy
# string similarity in correct_material_typos - deliberately a shortlist
# of common battery-domain terms, not an exhaustive materials database.
KNOWN_MATERIAL_TERMS: list[str] = [
    "NCA", "NCM", "NMC", "NCM622", "NCM811", "NCA811", "NCM955",
    "LFP", "LCO", "LMO", "LNMO", "LTO",
    "LiFSI", "LiTFSI", "LiPF6", "LiClO4", "LHCE",
    "FEC", "VC", "PRS", "TEMPO",
    "SEI", "CEI",
    "High-Ni", "Mid-Ni", "Low-Ni",
    "graphite", "silicon",
]
_KNOWN_MATERIAL_TERMS_LOWER = {term.lower(): term for term in KNOWN_MATERIAL_TERMS}

# Below this length, fuzzy-matching a token against the whitelist is
# unreliable - two/three-letter tokens (e.g. "Si", the element symbol for
# silicon) can score a deceptively high similarity against an unrelated
# whitelist entry purely by chance (short strings have few characters to
# disagree on). Leave short tokens untouched rather than risk "correcting"
# them into something else entirely.
_MIN_FUZZY_TOKEN_LENGTH = 4
_FUZZY_AUTO_CORRECT_THRESHOLD = 0.8
_FUZZY_UNRECOGNIZED_THRESHOLD = 0.6


def correct_material_typos(material: str) -> tuple[str, str | None, str | None]:
    """Best-effort typo correction for the search form's material field,
    applied once up front (before the keyword is combined and handed to
    the pipeline) so both a successful Gemini call and the dictionary
    fallback above see the corrected spelling either way.

    Only ASCII tokens (formulas/abbreviations like "NCM811", "Mid-Ni") are
    checked against KNOWN_MATERIAL_TERMS - Korean material phrases are
    already handled by TERM_MAP's exact matching in expand_with_dictionary.

    Returns (possibly-corrected material string, a Korean notice to show
    the user or None, and a notice_level of "info"/"warning"/None so the
    caller can style the two cases differently):
    - similarity >= 80% against a known term: auto-corrected, "info"
      notice explains what was substituted.
    - similarity < 60% (no close match at all): left as typed, "warning"
      notice says it wasn't recognized.
    - in between: left as typed, no notice - not confident enough to
      rewrite it, but not clearly wrong either.
    """

    corrections: list[tuple[str, str]] = []
    unrecognized: list[str] = []

    def _correct_token(match: re.Match) -> str:
        token = match.group(0)
        if len(token) < _MIN_FUZZY_TOKEN_LENGTH or token.lower() in _KNOWN_MATERIAL_TERMS_LOWER:
            return token

        candidates = difflib.get_close_matches(
            token.lower(), _KNOWN_MATERIAL_TERMS_LOWER.keys(), n=1, cutoff=_FUZZY_UNRECOGNIZED_THRESHOLD
        )
        if not candidates:
            unrecognized.append(token)
            return token

        best = candidates[0]
        ratio = difflib.SequenceMatcher(None, token.lower(), best).ratio()
        if ratio >= _FUZZY_AUTO_CORRECT_THRESHOLD:
            canonical = _KNOWN_MATERIAL_TERMS_LOWER[best]
            corrections.append((token, canonical))
            return canonical
        return token

    corrected = _ASCII_TOKEN_RE.sub(_correct_token, material)

    if corrections:
        notice = " ".join(f"'{orig}'를 '{fixed}'로 인식하여 검색했습니다." for orig, fixed in corrections)
        level = "info"
    elif unrecognized:
        notice = (
            f"'{unrecognized[0]}'는 인식되지 않는 소재명입니다. "
            "NCM811, LFP 같은 표준 명칭을 확인해주세요."
        )
        level = "warning"
    else:
        notice = None
        level = None

    return corrected, notice, level


def expand_with_dictionary(keyword: str) -> tuple[str, list[str]]:
    """Best-effort English query expansion using the static term map above,
    for when Gemini's own `ai_service.expand_search_query` is unavailable.

    Matches the longest known Korean phrases/abbreviations in `keyword`
    first, then keeps any already-ASCII tokens (formulas, abbreviations
    Gemini would otherwise have left untouched) verbatim. Any Hangul left
    over after that - a word/phrase TERM_MAP has no entry for (e.g. "고전압"
    if it isn't in the map) - is kept as a literal token too instead of
    being silently discarded, and logged as a warning so real TERM_MAP
    gaps are discoverable from server logs instead of just vanishing
    unnoticed. It won't match Semantic Scholar's English-only index by
    itself, but keeping it is strictly better than erasing it outright.

    Returns (english_query, terms) with the same shape as
    expand_search_query, so callers can treat both interchangeably. Never
    silently drops part of the keyword.
    """

    remaining = keyword
    terms: list[str] = []
    seen: set[str] = set()

    def _add(term: str) -> None:
        key = term.lower()
        if key not in seen:
            seen.add(key)
            terms.append(term)

    for pattern in _sorted_patterns():
        if pattern in remaining:
            _add(TERM_MAP[pattern])
            remaining = remaining.replace(pattern, " ")

    for token in _ASCII_TOKEN_RE.findall(keyword):
        _add(token)

    for leftover in _HANGUL_RE.findall(remaining):
        logger.warning(
            "battery_term_mapping: no TERM_MAP entry for %r, keeping as literal token", leftover
        )
        _add(leftover)

    if not terms:
        return _DEFAULT_FALLBACK_QUERY, [_DEFAULT_FALLBACK_QUERY]

    return " ".join(terms), terms


# --- Chemical category/family detection (additive/solvent field only) -------
#
# A user typing "불소계", "F계", "황계 첨가제" etc. into the additive/solvent
# search field means a CATEGORY of compounds, not a specific one - searching
# for that literal Korean phrase against Semantic Scholar's English-only
# index matches nothing, the same failure mode as any other untranslated
# Hangul (see expand_with_dictionary above). See
# search_pipeline._expand_additive_category, which uses looks_like_compound_
# category to decide whether to even call ai_service.expand_compound_category,
# and expand_category_from_dictionary as that call's own fallback.

# Matches a "<word>계"/"<word>계열" token (불소계, 황계, F계, S계, F계열, ...) -
# Korean "계"/"계열" as a family/system suffix. Also matches "포함"/"함유"
# (containing) and English "-based". Not perfectly precise (계 is also a
# suffix in unrelated words like 계면/관계/단계) but false positives in this
# specific field are
# unlikely in practice, and cost only one wasted (gracefully-handled) Gemini
# call rather than a wrong answer.
_CATEGORY_SUFFIX_RE = re.compile(r"(?:^|\s)[A-Za-z가-힣]+(?:\s*계열|계)(?:\s|$)")
_CATEGORY_KEYWORD_RE = re.compile(r"함유|포함|-?based\b", re.IGNORECASE)


def looks_like_compound_category(text: str) -> bool:
    """Best-effort detection of a chemical CATEGORY/FAMILY reference (e.g.
    "불소계", "F계", "황 함유", "nitrile-based") as opposed to a specific
    compound name (e.g. "LiFSI", "FEC") in the additive/solvent search
    field. A false negative just means the raw text is searched as-is (the
    same experience as before this feature existed) - never a crash."""

    return bool(_CATEGORY_SUFFIX_RE.search(text) or _CATEGORY_KEYWORD_RE.search(text))


# Small hand-curated fallback for common electrolyte additive/solvent
# CATEGORIES, used only when ai_service.expand_compound_category (Gemini) is
# unavailable - same "hand-curated draft, extend as gaps surface" spirit as
# TERM_MAP above. Every compound listed here is a real, well-documented
# battery electrolyte component (verified against published battery
# electrolyte literature, not guessed) - this is deliberately a short list
# covering only the most common categories, not an exhaustive taxonomy.
# Matched as a lowercased substring of the user's input.
CATEGORY_COMPOUND_MAP: dict[str, list[str]] = {
    "불소계": ["FEC", "LiFSI", "LiPF6"],
    "f계": ["FEC", "LiFSI", "LiPF6"],
    "황계": ["PRS", "sulfolane", "DTD"],
    "s계": ["PRS", "sulfolane", "DTD"],
    "인계": ["TPP", "TEP", "TMP"],
    "p계": ["TPP", "TEP", "TMP"],
    "질소계": ["succinonitrile", "acetonitrile"],
    "n계": ["succinonitrile", "acetonitrile"],
}


def expand_category_from_dictionary(category_text: str) -> list[str]:
    """Fallback for a looks_like_compound_category hit when Gemini is
    unavailable: look up CATEGORY_COMPOUND_MAP by substring match. Returns
    [] (never guesses) for any category not in this short list - the caller
    then falls back further to searching the raw category text as-is."""

    lowered = category_text.lower()
    for pattern, compounds in CATEGORY_COMPOUND_MAP.items():
        if pattern in lowered:
            return compounds
    return []
