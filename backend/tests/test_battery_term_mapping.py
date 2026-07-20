"""Unit tests for battery_term_mapping.py - the static dictionary fallback
used when Gemini query expansion fails or the search's time budget is
already exhausted."""

from app.services import battery_term_mapping


def test_expand_with_dictionary_maps_multiword_phrase_as_one_unit():
    query, terms = battery_term_mapping.expand_with_dictionary("실리콘 음극")

    assert query == "silicon anode"
    assert terms == ["silicon anode"]


def test_expand_with_dictionary_prefers_longest_match_over_component_words():
    """"하이니켈 양극" should map to the single combined phrase, not to
    "high-nickel" and "cathode material" as two separate hits."""

    query, terms = battery_term_mapping.expand_with_dictionary("하이니켈 양극 사이클 수명")

    assert terms == ["high-nickel cathode", "cycle life"]
    assert query == "high-nickel cathode cycle life"


def test_expand_with_dictionary_preserves_ascii_formula_tokens():
    query, terms = battery_term_mapping.expand_with_dictionary("NCA811 사이클 수명")

    assert "NCA811" in terms
    assert "cycle life" in terms
    assert "NCA811" in query


def test_expand_with_dictionary_translates_every_mapped_phrase():
    """A TERM_MAP hit is always translated - it never survives as raw
    Korean text in the output. Unmapped Korean words are a different
    story now (see test_expand_with_dictionary_keeps_unmapped_korean_
    terms_instead_of_dropping_them below) - "안정성" here has no TERM_MAP
    entry (only "사이클 안정성"/"안전성" do) and is expected to pass through
    literally, which is exactly the point of that behavior."""

    query, _terms = battery_term_mapping.expand_with_dictionary("실리콘 음극 SEI 안정성")

    assert "실리콘" not in query
    assert "음극" not in query
    assert "silicon anode" in query


def test_expand_with_dictionary_keeps_unmapped_korean_terms_instead_of_dropping_them():
    """Previously any Korean word/phrase with no TERM_MAP entry (e.g.
    "고전압") was silently discarded, which could erase a real part of the
    user's query without a trace. It's now kept as a literal token
    instead - not a translation, but strictly better than vanishing."""

    query, terms = battery_term_mapping.expand_with_dictionary("아무개 논문 찾아줘")

    assert terms == ["아무개", "논문", "찾아줘"]
    assert query == "아무개 논문 찾아줘"


def test_expand_with_dictionary_falls_back_to_generic_query_only_when_truly_empty():
    query, terms = battery_term_mapping.expand_with_dictionary("   ")

    assert query == "lithium-ion battery"
    assert terms == ["lithium-ion battery"]


def test_expand_with_dictionary_deduplicates_terms():
    query, terms = battery_term_mapping.expand_with_dictionary("양극 양극 재료")

    assert terms.count("cathode") == 1


# --- correct_material_typos --------------------------------------------------


def test_correct_material_typos_auto_corrects_high_confidence_typo():
    """"Mlid-Ni" (~92% similar to "Mid-Ni") should be silently corrected,
    with an "info" notice explaining what was substituted."""

    corrected, notice, level = battery_term_mapping.correct_material_typos("Mlid-Ni")

    assert corrected == "Mid-Ni"
    assert notice == "'Mlid-Ni'를 'Mid-Ni'로 인식하여 검색했습니다."
    assert level == "info"


def test_correct_material_typos_warns_on_unrecognized_term():
    """A token with no close match at all (well under 60% similarity to
    anything known) is left untouched but flagged as unrecognized."""

    corrected, notice, level = battery_term_mapping.correct_material_typos("Xyzabc")

    assert corrected == "Xyzabc"
    assert notice == "'Xyzabc'는 인식되지 않는 소재명입니다. NCM811, LFP 같은 표준 명칭을 확인해주세요."
    assert level == "warning"


def test_correct_material_typos_leaves_ambiguous_similarity_untouched():
    """Similarity in the 60-79% band is not confident enough to auto-
    correct, but also not clearly wrong - no notice either way."""

    corrected, notice, level = battery_term_mapping.correct_material_typos("Mdini")

    assert corrected == "Mdini"
    assert notice is None
    assert level is None


def test_correct_material_typos_skips_short_tokens():
    """Short tokens (e.g. the 2-letter element symbol "Si") are exempt from
    fuzzy matching - "Si" is ~80% similar to "SEI" purely by chance, and
    "correcting" a real material into an unrelated one would be worse than
    doing nothing."""

    corrected, notice, level = battery_term_mapping.correct_material_typos("Si")

    assert corrected == "Si"
    assert notice is None
    assert level is None


def test_correct_material_typos_no_notice_for_already_correct_term():
    corrected, notice, level = battery_term_mapping.correct_material_typos("NCM811")

    assert corrected == "NCM811"
    assert notice is None
    assert level is None


def test_correct_material_typos_ignores_korean_text():
    """Korean material phrases are handled by TERM_MAP elsewhere - this
    function only touches ASCII tokens, so pure Korean input passes
    through completely unchanged."""

    corrected, notice, level = battery_term_mapping.correct_material_typos("실리콘 음극")

    assert corrected == "실리콘 음극"
    assert notice is None
    assert level is None
