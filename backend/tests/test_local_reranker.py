"""Unit tests for local_reranker.py - the BM25-based fallback used when
Gemini re-ranking itself fails (429/503/timeout)."""

from app.services import local_reranker, semantic_scholar_service


def _candidate(paper_id, title, abstract, year=2024) -> semantic_scholar_service.Candidate:
    return semantic_scholar_service.Candidate(
        paper_id=paper_id,
        title=title,
        authors="Author A",
        journal="Journal X",
        year=year,
        doi="10.1/x",
        abstract=abstract,
    )


def test_rerank_locally_ranks_matching_candidate_above_unrelated_one():
    related = _candidate(
        "p1",
        "Silicon anode SEI stabilization via novel binder",
        "This paper studies SEI formation on silicon anodes.",
    )
    unrelated = _candidate(
        "p2",
        "Recyclable packaging for consumer electronics",
        "A study on packaging materials with no relation to batteries.",
    )

    ranked = local_reranker.rerank_locally(
        "silicon anode SEI", ["silicon anode", "SEI"], [unrelated, related]
    )

    assert [c.paper_id for c, _, _ in ranked] == ["p1", "p2"]
    scored_by_id = {c.paper_id: score for c, score, _ in ranked}
    assert scored_by_id["p1"] > 0
    assert scored_by_id["p2"] == 0.0


def test_rerank_locally_sets_why_selected_note_only_for_scored_candidates():
    related = _candidate("p1", "Silicon anode SEI study", "SEI formation on silicon anodes.")
    unrelated = _candidate("p2", "Unrelated packaging paper", "No relation to batteries at all.")

    ranked = local_reranker.rerank_locally("silicon anode SEI", ["silicon anode"], [related, unrelated])

    why_by_id = {c.paper_id: why for c, _, why in ranked}
    assert why_by_id["p1"] == local_reranker.LOCAL_RERANK_WHY_SELECTED
    assert why_by_id["p2"] == ""


def test_rerank_locally_preserves_original_order_when_nothing_matches_anything():
    """If not a single candidate shares any vocabulary with the query,
    there is no signal to rank by - the original (Semantic Scholar) order
    must come back unchanged rather than being reshuffled arbitrarily."""

    first = _candidate("p1", "Completely unrelated topic one", "Nothing to do with the query.")
    second = _candidate("p2", "Completely unrelated topic two", "Also nothing to do with the query.")

    ranked = local_reranker.rerank_locally("silicon anode SEI", ["silicon anode"], [first, second])

    assert [c.paper_id for c, _, _ in ranked] == ["p1", "p2"]
    assert all(score == 0.0 for _, score, _ in ranked)
    assert all(why == "" for _, _, why in ranked)


def test_rerank_locally_empty_candidates_returns_empty_list():
    assert local_reranker.rerank_locally("silicon anode", ["silicon anode"], []) == []


def test_rerank_locally_no_query_terms_scores_everything_zero():
    candidate = _candidate("p1", "Some paper", "Some abstract.")

    ranked = local_reranker.rerank_locally("", [], [candidate])

    assert ranked == [(candidate, 0.0, "")]


def test_rerank_locally_scores_higher_for_more_term_repetition():
    """A candidate whose abstract repeats the query term many times should
    score at least as high as one that mentions it only once (classic BM25
    term-frequency behavior, saturating rather than growing unbounded)."""

    frequent = _candidate(
        "p1",
        "Silicon anode research",
        "Silicon anode silicon anode silicon anode cycling performance.",
    )
    once = _candidate("p2", "Silicon anode research", "Silicon anode cycling performance.")

    ranked = local_reranker.rerank_locally("silicon anode", ["silicon anode"], [once, frequent])

    scored_by_id = {c.paper_id: score for c, score, _ in ranked}
    assert scored_by_id["p1"] >= scored_by_id["p2"]


# --- domain-relevance bonus/penalty (ambiguous-acronym disambiguation) -------


def test_has_battery_domain_keyword_detects_battery_terms():
    assert local_reranker.has_battery_domain_keyword("A study on lithium-ion battery electrolytes.")
    assert local_reranker.has_battery_domain_keyword("Coin cell cycling performance evaluation.")


def test_has_battery_domain_keyword_ignores_bare_cell():
    """Bare "cell" is deliberately excluded - it would false-positive on
    "cellular network"/"stem cell" etc., exactly the kind of off-domain
    content this list exists to help exclude."""

    assert not local_reranker.has_battery_domain_keyword("A cellular network protocol for 5G.")


def test_has_off_domain_keyword_detects_networking_terms():
    assert local_reranker.has_off_domain_keyword("A forward error correction scheme for wireless networks.")
    assert local_reranker.has_off_domain_keyword("LDPC codes for channel coding.")


def test_has_off_domain_keyword_ignores_battery_text():
    assert not local_reranker.has_off_domain_keyword("Silicon anode SEI stabilization via novel binder.")


def test_domain_score_adjustment_penalty_dominates_bonus():
    """A text matching both an off-domain and a battery keyword (e.g. "FEC"
    mentioned in a networking paper that also happens to say "battery" in
    passing) must still net out strongly negative - the penalty exists
    specifically to overrule a coincidental battery-keyword match."""

    adjustment = local_reranker.domain_score_adjustment(
        "Forward error correction for battery-powered wireless sensor networks."
    )
    assert adjustment < 0


def test_rerank_locally_demotes_off_domain_candidate_below_unrelated_one():
    """The core acronym-collision scenario: "FEC" as a query term lexically
    overlaps with a networking paper's title just as much as with a real
    battery paper's - domain_score_adjustment must still push the
    networking paper to the very bottom, below even an unrelated
    (non-off-domain) candidate with zero overlap."""

    battery_paper = _candidate(
        "p1",
        "FEC additive for lithium-ion battery electrolyte stabilization",
        "Fluoroethylene carbonate (FEC) improves SEI formation on the anode.",
    )
    networking_paper = _candidate(
        "p2",
        "FEC schemes for wireless network reliability",
        "Forward error correction (FEC) improves packet loss resilience.",
    )
    unrelated_paper = _candidate(
        "p3",
        "A cooking recipe archive",
        "Nothing about batteries or networking here.",
    )

    ranked = local_reranker.rerank_locally("FEC battery electrolyte", ["FEC"], [
        networking_paper,
        unrelated_paper,
        battery_paper,
    ])

    assert [c.paper_id for c, _, _ in ranked][0] == "p1"
    assert [c.paper_id for c, _, _ in ranked][-1] == "p2"
