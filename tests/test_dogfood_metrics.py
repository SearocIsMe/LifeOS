"""Phase 3 S4 acceptance: dogfood metrics (four families + judge sliding window).

Case map (design doc 02 §2 S4):
- four families out   -> weekly report produces continuity/retention/perception/cost values
- judge sliding window -> merged samples < 200 fails closed; >= 200 decides
- model version locked -> report records model_version (spec §9.5)
- cost aggregation     -> by-life P50/P95 + tier-1 share assertion (>=80%)
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from lifeos.dogfood.metrics import (
    JUDGE_WINDOW_MIN,
    JudgeWindowError,
    aggregate_cost,
    build_weekly_report,
    judge_memory_error_rate,
)

NOW = datetime(2026, 9, 30, 12, 0, 0, tzinfo=timezone.utc)


def _invocations() -> list[dict]:
    # 10 invocations, 9 tier-1 (0.9 share), latencies spread for P50/P95
    rows = [
        {"life_id": "l1", "latency_ms": 100 + 10 * i, "tier": 1} for i in range(9)
    ]
    rows.append({"life_id": "l2", "latency_ms": 900, "tier": 2})
    return rows


def test_four_metric_families_out():
    r = build_weekly_report(
        week=1,
        monitor_errors=2,
        monitor_samples=50,
        unresolved_conflicts=1,
        total_memories=300,
        weekly_active=12,
        cohort_size=15,
        invocations=_invocations(),
        model_version="Qwen3.6-35B-A3B-FP8",
    )
    d = r.to_dict()
    # continuity family
    assert d["memory_error_rate"] == 0.04
    assert d["conflict_rate"] is not None
    # retention family
    assert d["retention_weekly_active"] == 12
    assert abs(d["retention_return_rate"] - 0.8) < 1e-9
    # cost family
    assert d["cost_p50_ms"] is not None and d["cost_p95_ms"] is not None
    assert d["tier1_share"] == 0.9
    # all values type-correct
    assert isinstance(d["week"], int) and isinstance(d["monitor_samples"], int)


def test_judge_sliding_window_fails_closed_below_200():
    # weekly n=50 can NEVER decide (roadmap §1.2 (a))
    with pytest.raises(JudgeWindowError):
        judge_memory_error_rate(cumulative_errors=2, cumulative_samples=50)
    with pytest.raises(JudgeWindowError):
        judge_memory_error_rate(cumulative_errors=5, cumulative_samples=199)
    # at the floor (200) it decides
    out = judge_memory_error_rate(cumulative_errors=9, cumulative_samples=200)
    assert out["merged_samples"] == JUDGE_WINDOW_MIN
    assert out["pass"] is True  # 9/200 = 4.5% <= 5%
    out2 = judge_memory_error_rate(cumulative_errors=15, cumulative_samples=200)
    assert out2["pass"] is False  # 7.5% > 5%


def test_tier1_share_assertion():
    # share below 80% fails closed at report build (spec §3.4)
    bad = [{"life_id": "l", "latency_ms": 10, "tier": 1}] + [
        {"life_id": "l", "latency_ms": 10, "tier": 2} for _ in range(3)
    ]  # 0.25 share
    with pytest.raises(JudgeWindowError):
        build_weekly_report(
            week=1,
            monitor_errors=0,
            monitor_samples=50,
            unresolved_conflicts=0,
            total_memories=100,
            weekly_active=10,
            cohort_size=10,
            invocations=bad,
        )


def test_model_version_locked_in_report():
    r = build_weekly_report(
        week=2,
        monitor_errors=1,
        monitor_samples=50,
        unresolved_conflicts=0,
        total_memories=100,
        weekly_active=10,
        cohort_size=10,
        invocations=_invocations(),
        model_version="Qwen3.6-35B-A3B-FP8",
    )
    assert r.model_version == "Qwen3.6-35B-A3B-FP8"  # spec §9.5 recorded


def test_cost_aggregation_by_life():
    agg = aggregate_cost(_invocations())
    assert agg["p50_ms"] == 140  # median of 100..180 + 900
    assert agg["p95_ms"] == 900
    assert abs(agg["tier1_share"] - 0.9) < 1e-9
    assert aggregate_cost([])["p50_ms"] is None
