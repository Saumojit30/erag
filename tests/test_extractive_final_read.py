"""Phase 2.7 H19 — extractive final read (tests first).

Tests for `extractive_answer_messages` (prompt builder) and the mocked
end-to-end wiring in `run_erag`. Written before the implementation;
they fail until it lands.
"""

from unittest.mock import MagicMock

from src.llm.client import Tracker
from src.llm.prompts import extractive_answer_messages
from src.systems.erag import run_erag

_POOL = [{"title": "Paris", "sentences": ["Paris is the capital of France."],
          "text": "Paris. Paris is the capital of France."}]


def _claim(text, status="supported", eff=0.9):
    return {"text": text, "status": status, "eff": eff}


# ---------------------------------------------------------------------------
# A.1 — extractive_answer_messages (prompt builder)
# ---------------------------------------------------------------------------

def test_extractive_messages_lists_claims_only_no_context():
    claims = [
        _claim("Paris is the capital of France."),
        _claim("Paris hosted the 2024 Olympics."),
    ]
    msgs = extractive_answer_messages("What is the capital of France?", claims)
    user = msgs[1]["content"]
    assert "Paris is the capital of France." in user
    assert "Paris hosted the 2024 Olympics." in user
    assert "What is the capital of France?" in user
    # The restriction is the mechanism: no context block for the reader
    # to fall back on (unlike support_ranked_answer_messages).
    assert "Context:" not in user
    assert "only" in msgs[0]["content"].lower()


# ---------------------------------------------------------------------------
# A.2 — mocked end-to-end wiring in run_erag
# ---------------------------------------------------------------------------

class _CountingLLM:
    """Mock LLM mirroring LLM.chat: every chat() counts as one LLM call."""

    def __init__(self, responses):
        self._it = iter(responses)
        self.n_calls = 0
        self.last_messages = None

    def chat(self, messages, tracker, **kwargs):
        tracker.llm_calls += 1
        self.n_calls += 1
        self.last_messages = messages
        return next(self._it)


_CLAIMS_RIVAL = (
    '{"claims": ['
    '{"text": "Paris is the capital of France.", "answer": false, "depends_on": [], "source": "question"}, '
    '{"text": "Paris hosted the 2024 Olympics.", "answer": false, "depends_on": [], "source": "question"}, '
    '{"text": "Paris is in France.", "answer": false, "depends_on": [], "source": "question"}, '
    '{"text": "Lyon is the capital.", "answer": true, "depends_on": [], "source": "draft"}'
    ']}'
)

_CLAIMS_BACKED = (
    '{"claims": ['
    '{"text": "Lyon is the capital.", "answer": true, "depends_on": [], "source": "draft"}, '
    '{"text": "Paris is the capital of France.", "answer": false, "depends_on": [], "source": "question"}'
    ']}'
)


def _item():
    return {
        "_id": "test_extractive_1",
        "question": "What is the capital of France?",
        "context": [["Paris", ["Paris is the capital of France."]]],
        "supporting_facts": [["Paris", 0]],
    }


def _supported_nli():
    nli = MagicMock()
    nli.verify.return_value = {"status": "supported", "conflict": False,
                               "sup": [("Paris", 0.9)], "con": []}
    return nli


def _unresolved_nli():
    nli = MagicMock()
    nli.verify.return_value = {"status": "unresolved", "conflict": False,
                               "sup": [], "con": []}
    return nli


def _v1_gated_cfg(**erag_overrides):
    erag = {
        "mode": "active",
        "max_hops": 2,
        "sc_samples": 3,
        "sc_temperature": 0.7,
        "theta_fast": 0.8,
        "theta_gap": 0.6,
        "theta_abs": 0.4,
        "max_claims": 5,
        "pool_cap": 12,
        "sc_mode": "sequential",
        "gate_sc_behind_fast_path": True,
        "claim_strategy": "incremental",
        "post_hop_resample": "never",
        "eig_strategy": "direct",
        "saturation_precheck": True,
    }
    erag.update(erag_overrides)
    return {"retrieval": {"k": 3}, "nli": {"theta_s": 0.5, "theta_c": 0.5}, "erag": erag}


def test_extractive_reread_fires_and_replaces_draft():
    """Draft 'Lyon', supported claims exist: one claims-only re-read,
    draft replaced by the re-read answer."""
    llm = _CountingLLM(["Lyon", _CLAIMS_RIVAL, "Paris"])
    retriever = MagicMock()
    retriever.search.return_value = list(_POOL)
    tr = Tracker()
    out = run_erag(_item(), retriever, llm, _supported_nli(),
                   _v1_gated_cfg(ground_final_read=True, extractive_final_read=True), tr)
    assert tr.llm_calls == 3
    assert out["answer"] == "Paris"
    assert out["draft"] == "Paris"
    assert out["grounded_reread"] is True
    assert out["reread_trigger"] == "extractive"
    assert out["reread_answer"] == "Paris"
    assert out["extractive"] is True
    assert out["trace"][-1]["answer"] == "Lyon"
    # The re-read the mock saw must carry no context block.
    assert "Context:" not in llm.last_messages[1]["content"]


def test_extractive_reread_fires_even_when_draft_backed():
    """Unlike H15's trigger, the extractive read is always on: the draft
    is backed by its own claim and the re-read still fires."""
    llm = _CountingLLM(["Paris", _CLAIMS_BACKED, "Paris"])
    retriever = MagicMock()
    retriever.search.return_value = list(_POOL)
    tr = Tracker()
    out = run_erag(_item(), retriever, llm, _supported_nli(),
                   _v1_gated_cfg(ground_final_read=True, extractive_final_read=True), tr)
    assert tr.llm_calls == 3
    assert out["answer"] == "Paris"
    assert out["extractive"] is True
    assert out["reread_trigger"] == "extractive"


def test_no_extractive_reread_when_no_supported_claims():
    """No supported claim exists: no re-read, draft stands. Note the
    unresolved graph has gaps, so the Fast-Path gate does not skip SC.
    Call order is draft, claims, then the 2 SC samples (sequential SC
    stops early on an unassailable majority) = 4 calls total."""
    llm = _CountingLLM(["Lyon", _CLAIMS_RIVAL, "Lyon", "Lyon"])
    retriever = MagicMock()
    retriever.search.return_value = list(_POOL)
    tr = Tracker()
    out = run_erag(_item(), retriever, llm, _unresolved_nli(),
                   _v1_gated_cfg(ground_final_read=True, extractive_final_read=True), tr)
    assert tr.llm_calls == 4
    assert out["answer"] == "Lyon"
    assert out["draft"] == "Lyon"
    assert out["grounded_reread"] is False
    assert out["reread_trigger"] is None
    assert out["extractive"] is False


def test_no_extractive_field_when_flag_off():
    """Flag off: no extra call, no new field — byte-identical to the
    improved system."""
    llm = _CountingLLM(["Lyon", _CLAIMS_RIVAL])
    retriever = MagicMock()
    retriever.search.return_value = list(_POOL)
    tr = Tracker()
    out = run_erag(_item(), retriever, llm, _supported_nli(),
                   _v1_gated_cfg(ground_final_read=True), tr)
    assert tr.llm_calls == 2
    assert out["answer"] == "Lyon"
    assert out["draft"] == "Lyon"
    assert out["grounded_reread"] is False
    assert out["reread_trigger"] is None
    assert "extractive" not in out


def test_extractive_reread_returning_unknown_keeps_draft():
    """Extractive re-read returns 'unknown' -> original draft stands."""
    llm = _CountingLLM(["Lyon", _CLAIMS_RIVAL, "unknown"])
    retriever = MagicMock()
    retriever.search.return_value = list(_POOL)
    tr = Tracker()
    out = run_erag(_item(), retriever, llm, _supported_nli(),
                   _v1_gated_cfg(ground_final_read=True, extractive_final_read=True), tr)
    assert tr.llm_calls == 3
    assert out["answer"] == "Lyon"
    assert out["draft"] == "Lyon"
    assert out["grounded_reread"] is True
    assert out["reread_trigger"] == "extractive"
    assert out["reread_answer"] == "unknown"
    assert out["extractive"] is True
