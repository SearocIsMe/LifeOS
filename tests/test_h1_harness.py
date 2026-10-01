"""S4 acceptance cases: H1 harness offline regression (design doc 02 §2 S4)."""

import pytest

from lifeos.evalharness import (
    CaseResult,
    H1Report,
    HarnessError,
    judge_pair,
    parse_intent,
    run_h1,
)

MOCK_PROVIDERS = {"A": {"kind": "mock"}, "B": {"kind": "mock"}}

CASE_OK = {
    "case_id": "case-001",
    "user_message": "今天有点累，想聊聊。",
    "contract": {"personality_seed": "ps-001"},
    "state_summary": {
        "energy": 0.7, "social_need": 0.5, "security": 0.8,
        "valence": 0.0, "arousal": 0.1,
    },
    "recall_bundle": {"memories": [], "summary": ""},
    "relationship_scores": {},
    "params": {},
}


class TestOfflineRegression:
    def test_mock_mode_runs_without_network(self):
        report = run_h1([CASE_OK], MOCK_PROVIDERS)
        assert report.total_cases == 1
        assert report.h1_score in (0.0, 1.0)

    def test_report_artifact_contract(self):
        report = run_h1([CASE_OK], MOCK_PROVIDERS)
        d = report.to_dict()
        assert d["benchmark"] == "H1"
        assert d["prompt_template_id"] == "system@phase1-1"
        assert d["total_cases"] == 1
        assert len(d["cases"]) == 1
        assert len(d["cases"][0]["prompt_hash"]) == 64

    def test_deterministic_rerun(self):
        r1 = run_h1([CASE_OK], MOCK_PROVIDERS)
        r2 = run_h1([CASE_OK], MOCK_PROVIDERS)
        assert r1.h1_score == r2.h1_score
        assert r1.cases[0].prompt_hash == r2.cases[0].prompt_hash


class TestIntentParse:
    def test_valid_json(self):
        intent = parse_intent('{"intent_type": "chat", "slot_key": null, "safety_flag": "none"}')
        assert intent is not None and intent["intent_type"] == "chat"

    def test_invalid_json_returns_none(self):
        assert parse_intent("not json") is None

    def test_non_dict_returns_none(self):
        assert parse_intent("[1, 2, 3]") is None


class TestJudge:
    def test_identical_intents_consistent(self):
        a = {"intent_type": "chat", "slot_key": None, "safety_flag": "none"}
        assert judge_pair(a, a) is True

    def test_different_type_inconsistent(self):
        a = {"intent_type": "chat", "slot_key": None, "safety_flag": "none"}
        b = {"intent_type": "plan", "slot_key": None, "safety_flag": "none"}
        assert judge_pair(a, b) is False


class TestFailClosed:
    def test_missing_user_message(self):
        with pytest.raises(HarnessError):
            run_h1([{"case_id": "x"}], MOCK_PROVIDERS)

    def test_missing_state_key_via_harness(self):
        bad = dict(CASE_OK, state_summary={"energy": 0.5})
        with pytest.raises(HarnessError):
            run_h1([bad], MOCK_PROVIDERS)

    def test_unknown_provider_kind(self):
        with pytest.raises(HarnessError):
            run_h1([CASE_OK], {"A": {"kind": "mock"}, "B": {"kind": "mystery"}})
