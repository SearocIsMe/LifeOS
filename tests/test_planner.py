"""Behavior Planner v0 unit tests (design doc 01 §3.1)."""

from datetime import datetime, timezone

import pytest

from lifeos.planner import (
    PLANNER_VERSION,
    PlannerError,
    plan_intents,
    select_best,
)

NOW = datetime(2026, 9, 20, 10, 0, 0, tzinfo=timezone.utc)
LID = "l1"
NEUTRAL = {"energy": 0.5, "social_need": 0.4, "security": 0.8}


def _types(proposals):
    return [bi.intent_type for bi in proposals]


def test_pure_determinism():
    a = plan_intents(LID, NEUTRAL, created_at=NOW)
    b = plan_intents(LID, NEUTRAL, created_at=NOW)
    assert a == b


def test_all_six_proposed_sorted_desc():
    proposals = plan_intents(LID, NEUTRAL, created_at=NOW)
    assert len(proposals) == 6
    assert all(bi.status.value == "proposed" for bi in proposals)
    scores = [bi.utility_score for bi in proposals]
    assert scores == sorted(scores, reverse=True)


def test_low_security_selects_comfort():
    states = {"energy": 0.5, "social_need": 0.8, "security": 0.1}
    best = select_best(LID, states, created_at=NOW)
    assert best.intent_type == "comfort"
    # severity = 0.4 - security = 0.3, recorded in the reason chain
    assert best.reason["feature"] == pytest.approx(0.3)
    assert best.preconditions["security_lt"] == 0.4


def test_mild_insecurity_keeps_silence():
    states = {"energy": 0.5, "social_need": 0.4, "security": 0.35}
    proposals = plan_intents(LID, states, created_at=NOW)
    comfort = next(bi for bi in proposals if bi.intent_type == "comfort")
    quiet = next(bi for bi in proposals if bi.intent_type == "stay_quiet")
    # severity 0.05 * 3.0 = 0.15 < 0.5 baseline -> silence wins
    assert comfort.utility_score < quiet.utility_score
    assert _types(proposals)[0] != "comfort"


def test_high_social_need_selects_greet():
    states = {"energy": 0.5, "social_need": 0.8, "security": 0.8}
    best = select_best(LID, states, created_at=NOW)
    assert best.intent_type == "greet"
    assert best.reason["feature"] == pytest.approx(0.8)


def test_stay_quiet_baseline_selected():
    proposals = plan_intents(LID, NEUTRAL, created_at=NOW)
    best = proposals[0]
    assert best.intent_type == "stay_quiet"
    assert best.utility_score == pytest.approx(0.5)
    assert best.modality.value == "attentional"


def test_cooldown_penalty_suppresses_greet():
    states = {"energy": 0.5, "social_need": 0.8, "security": 0.8}
    proposals = plan_intents(LID, states, cooldown={"greet": 1.0}, created_at=NOW)
    greet = next(bi for bi in proposals if bi.intent_type == "greet")
    # 1.0 * 0.8 - 1.0 = -0.2 -> falls below every other candidate
    assert greet.utility_score == pytest.approx(-0.2)
    best = proposals[0]
    assert best.intent_type == "inquire_user"
    assert best.reason["cooldown_penalty"] == 0.0


def test_missing_state_fails_closed():
    bad = {k: v for k, v in NEUTRAL.items() if k != "security"}
    with pytest.raises(PlannerError) as exc:
        plan_intents(LID, bad, created_at=NOW)
    assert "security" in str(exc.value)


def test_reason_breakdown_complete():
    states = {"energy": 0.7, "social_need": 0.6, "security": 0.2}
    proposals = plan_intents(
        LID, states, relationships={"alice": {"familiarity": 0.5}}, created_at=NOW
    )
    for bi in proposals:
        assert set(bi.reason) == {"feature", "weight", "cooldown_penalty"}
        assert "required_states" in bi.preconditions
    comfort = next(bi for bi in proposals if bi.intent_type == "comfort")
    assert comfort.utility_score == pytest.approx(0.6)  # 3.0 * 0.2


def test_recall_shared_uses_familiarity():
    states = {"energy": 0.5, "social_need": 0.4, "security": 0.8}
    proposals = plan_intents(
        LID, states, relationships={"alice": {"familiarity": 0.9}}, created_at=NOW
    )
    best = proposals[0]
    assert best.intent_type == "recall_shared"
    assert best.utility_score == pytest.approx(0.81)  # 0.9 * 0.9


def test_ids_content_addressed_and_distinct():
    first = plan_intents(LID, NEUTRAL, created_at=NOW)
    again = plan_intents(LID, NEUTRAL, created_at=datetime(2030, 1, 1, tzinfo=timezone.utc))
    ids = {bi.intent_id for bi in first}
    assert len(ids) == 6
    # content-addressed over candidate identity: created_at and utility do NOT affect ids
    assert [bi.intent_id for bi in first] == [bi.intent_id for bi in again]
    # candidate identity is stable across read views (score lives in reason);
    # ordering changes with the read view, so compare per-type maps
    changed = plan_intents(LID, {**NEUTRAL, "security": 0.1}, created_at=NOW)
    map_first = {bi.intent_type: bi.intent_id for bi in first}
    map_changed = {bi.intent_type: bi.intent_id for bi in changed}
    assert map_first == map_changed
    # but distinct candidates get distinct ids
    assert len(set(map_first.values())) == 6
