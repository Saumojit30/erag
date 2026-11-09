from unittest.mock import MagicMock
from src.epistemic.claims import CLAIM_SYSTEM, _parse, extract_claims
from src.epistemic.confidence import self_consistency
from src.llm.client import Tracker


def _mock_llm(raw_response):
    llm = MagicMock()
    llm.chat.return_value = raw_response
    return llm


def _paras():
    return [{"title": "Maker", "sentences": ["Thon Marial Maker is a basketball player."]}]


def test_parse_preserves_source_draft_and_question():
    raw_json = """
    {
      "claims": [
        {"text": "Thon Maker is a basketball player.", "answer": true, "depends_on": [], "source": "draft"},
        {"text": "Thon Marial Maker was born in South Sudan.", "answer": false, "depends_on": [], "source": "question"}
      ]
    }
    """
    claims = _parse(raw_json, max_claims=8)
    assert len(claims) == 2
    assert claims[0]["source"] == "draft"
    assert claims[0]["answer_bearing"] is True
    assert claims[1]["source"] == "question"
    assert claims[1]["answer_bearing"] is False


def test_parse_defaults_missing_source_to_draft():
    raw_json = """
    {
      "claims": [
        {"text": "Marie Curie was born in Warsaw.", "answer": false, "depends_on": []},
        {"text": "Marie Curie won two Nobel Prizes.", "answer": true, "depends_on": []}
      ]
    }
    """
    claims = _parse(raw_json, max_claims=5)
    assert len(claims) == 2
    assert all(c["source"] == "draft" for c in claims)


def test_parse_invalid_source_defaults_to_draft():
    raw_json = """
    {
      "claims": [
        {"text": "Marie Curie was born in Warsaw.", "answer": true, "depends_on": [], "source": "bogus"}
      ]
    }
    """
    claims = _parse(raw_json, max_claims=5)
    assert len(claims) == 1
    assert claims[0]["source"] == "draft"


def test_extract_claims_mixed_sources_via_mocked_llm():
    llm = _mock_llm("""
    {
      "claims": [
        {"text": "Thon Maker is a basketball player.", "answer": true, "depends_on": [], "source": "draft"},
        {"text": "Thon Marial Maker was born in South Sudan.", "answer": false, "depends_on": [], "source": "question"},
        {"text": "Thon Marial Maker plays for the Detroit Pistons.", "answer": false, "depends_on": [1], "source": "question"}
      ]
    }
    """)
    claims = extract_claims(
        llm,
        question="Where was Thon Maker born?",
        answer="Thon Maker",
        paras=_paras(),
        tracker=Tracker(),
        max_claims=8,
    )
    assert len(claims) == 3
    assert [c["source"] for c in claims] == ["draft", "question", "question"]
    assert claims[2]["depends_on"] == [1]
    # Exactly one answer-bearing claim, and it is draft-sourced.
    bearing = [c for c in claims if c["answer_bearing"]]
    assert len(bearing) == 1
    assert bearing[0]["source"] == "draft"


def test_extract_claims_fallback_carries_source_draft():
    llm = _mock_llm("Non-json output")
    claims = extract_claims(
        llm,
        question="Where was Marie Curie born?",
        answer="Warsaw",
        paras=[{"title": "Curie", "sentences": ["Curie was born in Warsaw."]}],
        tracker=Tracker(),
    )
    assert len(claims) == 1
    assert claims[0]["fallback"] is True
    assert claims[0]["source"] == "draft"


def test_exactly_one_answer_bearing_rule_unchanged():
    # No claim marked: the LAST claim becomes answer-bearing, as before.
    raw_json = """
    {
      "claims": [
        {"text": "Thon Maker is a basketball player.", "answer": false, "depends_on": [], "source": "draft"},
        {"text": "Thon Marial Maker was born in South Sudan.", "answer": false, "depends_on": [], "source": "question"}
      ]
    }
    """
    claims = _parse(raw_json, max_claims=8)
    bearing = [c for c in claims if c["answer_bearing"]]
    assert len(bearing) == 1
    assert bearing[0] is claims[-1]


def test_claim_system_has_question_grounded_and_full_names_instructions():
    assert "answer the Question" in CLAIM_SYSTEM
    assert "disagree with the given Answer" in CLAIM_SYSTEM
    assert "full names exactly as written in the Context" in CLAIM_SYSTEM
    assert '"source"' in CLAIM_SYSTEM


def test_parse_valid_json_claims():
    raw_json = """
    Here are the claims:
    ```json
    {
      "claims": [
        {"text": "Marie Curie was born in Warsaw.", "answer": false, "depends_on": []},
        {"text": "Warsaw was part of the Russian Empire.", "answer": false, "depends_on": [0]},
        {"text": "Marie Curie won two Nobel Prizes.", "answer": true, "depends_on": [0]}
      ]
    }
    ```
    """
    claims = _parse(raw_json, max_claims=5)
    assert len(claims) == 3
    assert claims[0]["text"] == "Marie Curie was born in Warsaw."
    assert claims[0]["answer_bearing"] is False
    assert claims[0]["depends_on"] == []

    assert claims[1]["depends_on"] == [0]
    assert claims[2]["answer_bearing"] is True
    assert claims[2]["depends_on"] == [0]


def test_parse_fallback_when_invalid():
    raw_invalid = "This is not valid json at all."
    claims = _parse(raw_invalid, max_claims=5)
    assert claims == []


def test_extract_claims_fallback_mechanism():
    llm = MagicMock()
    llm.chat.return_value = "Non-json output"
    tr = Tracker()

    claims = extract_claims(
        llm,
        question="Where was Marie Curie born?",
        answer="Warsaw",
        paras=[{"title": "Curie", "sentences": ["Curie was born in Warsaw."]}],
        tracker=tr,
    )
    assert len(claims) == 1
    assert claims[0]["answer_bearing"] is True
    assert claims[0]["fallback"] is True
    assert "Warsaw" in claims[0]["text"]


def test_self_consistency_confidence():
    llm = MagicMock()
    # 3 samples say "Paris", 2 samples say "Lyon"
    llm.chat.side_effect = ["Paris", "Paris", "Paris", "Lyon", "Lyon"]
    tr = Tracker()

    sc = self_consistency(
        llm,
        question="What is the capital of France?",
        paras=[{"title": "France", "sentences": ["Paris is capital."]}],
        draft="Paris",
        tracker=tr,
        k=5,
        temperature=0.7,
    )
    assert sc["majority"] == "paris"
    assert sc["conf_majority"] == 3 / 5  # 0.6
    assert sc["conf_draft_agreement"] == 3 / 5  # 0.6
    assert len(sc["samples"]) == 5

