"""Phase 3 S5 acceptance: Gate 3 six-criteria aggregation + dual signature.

Case map (design doc 02 §2 S5):
- six criteria aggregate -> all out with type-correct values
- closed verdict         -> all pass => PASS; any fail => FAIL (no v1 start)
- dual signature         -> signatures field appended for the two-person rule
- determinism            -> same inputs => same verdict
"""

from __future__ import annotations

from datetime import datetime, timezone

from lifeos.dogfood.gate3 import run_gate3

NOW = datetime(2026, 9, 30, 12, 0, 0, tzinfo=timezone.utc)


def _pass_inputs(**overrides):
    base = dict(
        blind_test_rate=0.85,
        best_baseline_rate=0.70,
        dogfood_high_risk_findings=0,
        cumulative_errors=9,
        cumulative_samples=200,
        cost_p95_ms=250.0,
        perception_score=0.72,
        generated_at=NOW,
    )
    base.update(overrides)
    return base


def test_six_criteria_aggregate():
    r = run_gate3(**_pass_inputs())
    assert len(r.criteria) == 6
    names = [c["name"] for c in r.criteria]
    assert names == [
        "盲测达统一门槛",
        "优于最佳基线",
        "无高危情感操纵",
        "记忆错误不随量失控",
        "成本P95低于产品线",
        "用户明确感知价值",
    ]
    assert all(isinstance(c["pass"], bool) for c in r.criteria)


def test_closed_verdict_pass():
    r = run_gate3(**_pass_inputs())
    assert r.verdict == "PASS"
    assert all(c["pass"] for c in r.criteria)


def test_closed_verdict_fail_any_criterion():
    # criterion 3: one high-risk finding => FAIL
    r = run_gate3(**_pass_inputs(dogfood_high_risk_findings=1))
    assert r.verdict == "FAIL"
    # criterion 1: blind test below 75% => FAIL
    r = run_gate3(**_pass_inputs(blind_test_rate=0.70))
    assert r.verdict == "FAIL"
    # criterion 2: edge below +10pp => FAIL
    r = run_gate3(**_pass_inputs(best_baseline_rate=0.80))
    assert r.verdict == "FAIL"
    # criterion 4: judge window below floor (e.g. 50) => FAIL (fail-closed)
    r = run_gate3(**_pass_inputs(cumulative_samples=50))
    assert r.verdict == "FAIL"
    c4 = r.criteria[3]
    assert c4["pass"] is False and c4["value"] is None
    # criterion 5: P95 above product line => FAIL
    r = run_gate3(**_pass_inputs(cost_p95_ms=400.0))
    assert r.verdict == "FAIL"
    # criterion 6: no perception data => FAIL
    r = run_gate3(**_pass_inputs(perception_score=None))
    assert r.verdict == "FAIL"


def test_dual_signature_field():
    r = run_gate3(**_pass_inputs())
    r.signatures = [
        {"role": "架构负责人", "name": "Jiang Haipeng", "date": "2026-09-30"},
        {"role": "非编写成员复核", "name": "Searoc", "date": "2026-09-30"},
    ]
    d = r.to_dict()
    assert len(d["signatures"]) == 2
    assert d["signatures"][0]["role"] == "架构负责人"


def test_determinism():
    r1 = run_gate3(**_pass_inputs())
    r2 = run_gate3(**_pass_inputs())
    assert r1.verdict == r2.verdict
    assert r1.criteria == r2.criteria


def test_no_data_fails_closed():
    """2026-09-30 hardening: absent real data is NOT evidence of passing.

    ``run_gate3()`` with no inputs must always return FAIL - a caller cannot
    claim "0 high-risk findings" or "cost P95 ok" without dogfood/usage data
    (roadmap §5 Gate 3 requires real-user evidence, not defaults).
    """
    r = run_gate3()  # no data at all
    assert r.verdict == "FAIL"
    assert not any(c["pass"] for c in r.criteria)
    # every real-data criterion carries an explicit fail-closed error note
    for c in r.criteria:
        assert c["value"] is None
        assert "error" in c
    # missing single criterion still fails closed
    r2 = run_gate3(**_pass_inputs(dogfood_high_risk_findings=None))
    assert r2.verdict == "FAIL"
    assert r2.criteria[2]["pass"] is False
    assert "error" in r2.criteria[2]
    r3 = run_gate3(**_pass_inputs(cost_p95_ms=None))
    assert r3.verdict == "FAIL"
    assert r3.criteria[4]["pass"] is False
