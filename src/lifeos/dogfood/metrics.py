"""Dogfood long-period metrics (Phase 3 S4, design doc 01 §4).

Four metric families (roadmap §5: 连续性/留存/关系感知/成本), with the
MONITOR vs JUDGE sampling discipline (spec §3.2):

- weekly monitor sampling: 50 records/week - trend monitoring only, NEVER
  a Gate verdict (n=50 CI half-width ~±6pp is insufficient);
- Gate-judge sliding window: merged samples >= JUDGE_WINDOW_MIN (200,
  tentative, ADR-0007) - n=200 CI half-width ~±3pp supports the <=5% call.

Cost aggregates by ``life_id`` (multi-instance口径, spec §3.4): P50/P95 from
``ModelInvocation`` rows + Tier-1 share assertion (>=80%).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

JUDGE_WINDOW_MIN = 200
MONITOR_SAMPLE_WEEKLY = 50
TIER1_SHARE_MIN = 0.80


class JudgeWindowError(ValueError):
    """Raised when a Gate-level judgement is attempted below the window floor."""


@dataclass
class WeeklyReport:
    week: int
    monitor_samples: int
    memory_error_rate: float | None = None
    conflict_rate: float | None = None
    recall_p95_ms: float | None = None
    retention_weekly_active: int = 0
    retention_return_rate: float | None = None
    relationship_perception_score: float | None = None
    cost_p50_ms: float | None = None
    cost_p95_ms: float | None = None
    tier1_share: float | None = None
    human_review_records: int = 0
    high_risk_findings: int = 0
    model_version: str = ""
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "week": self.week,
            "monitor_samples": self.monitor_samples,
            "memory_error_rate": self.memory_error_rate,
            "conflict_rate": self.conflict_rate,
            "recall_p95_ms": self.recall_p95_ms,
            "retention_weekly_active": self.retention_weekly_active,
            "retention_return_rate": self.retention_return_rate,
            "relationship_perception_score": self.relationship_perception_score,
            "cost_p50_ms": self.cost_p50_ms,
            "cost_p95_ms": self.cost_p95_ms,
            "tier1_share": self.tier1_share,
            "human_review_records": self.human_review_records,
            "high_risk_findings": self.high_risk_findings,
            "model_version": self.model_version,
        }


def _pctl(values: list[float], q: float) -> float:
    xs = sorted(values)
    if not xs:
        return 0.0
    k = max(0, min(len(xs) - 1, int(round(q * (len(xs) - 1)))))
    return xs[k]


def aggregate_cost(
    invocations: list[dict[str, Any]],
) -> dict[str, float | None]:
    """Cost by life_id aggregation (spec §3.4): P50/P95 latency + Tier-1 share.

    ``invocations`` rows: {life_id, latency_ms, tier} (ModelInvocation-derived).
    """
    if not invocations:
        return {"p50_ms": None, "p95_ms": None, "tier1_share": None}
    lat = [float(r["latency_ms"]) for r in invocations]
    tier1 = sum(1 for r in invocations if r.get("tier", 1) == 1)
    return {
        "p50_ms": _pctl(lat, 0.50),
        "p95_ms": _pctl(lat, 0.95),
        "tier1_share": tier1 / len(invocations),
    }


def build_weekly_report(
    *,
    week: int,
    monitor_errors: int,
    monitor_samples: int,
    unresolved_conflicts: int,
    total_memories: int,
    weekly_active: int,
    cohort_size: int,
    invocations: list[dict[str, Any]],
    human_review_records: int = MONITOR_SAMPLE_WEEKLY,
    high_risk_findings: int = 0,
    model_version: str = "",
) -> WeeklyReport:
    """One weekly monitoring report (trend only - monitor sampling, no verdict).

    ``monitor_samples`` should be MONITOR_SAMPLE_WEEKLY (50) at full cadence;
    the report records rates for trend charts, never a Gate call.
    """
    if monitor_samples > 0:
        err_rate = monitor_errors / monitor_samples
    else:
        err_rate = None
    conflict_rate = (unresolved_conflicts / total_memories) if total_memories else None
    cost = aggregate_cost(invocations)
    if cost["tier1_share"] is not None and cost["tier1_share"] < TIER1_SHARE_MIN:
        raise JudgeWindowError(
            f"tier-1 share {cost['tier1_share']:.2f} below {TIER1_SHARE_MIN} (spec §3.4)"
        )
    return WeeklyReport(
        week=week,
        monitor_samples=monitor_samples,
        memory_error_rate=err_rate,
        conflict_rate=conflict_rate,
        retention_weekly_active=weekly_active,
        retention_return_rate=(weekly_active / cohort_size) if cohort_size else None,
        cost_p50_ms=cost["p50_ms"],
        cost_p95_ms=cost["p95_ms"],
        tier1_share=cost["tier1_share"],
        human_review_records=human_review_records,
        high_risk_findings=high_risk_findings,
        model_version=model_version,
    )


def judge_memory_error_rate(
    *, cumulative_errors: int, cumulative_samples: int
) -> dict[str, Any]:
    """Gate-level judgement via the sliding merged window (spec §3.2).

    Below JUDGE_WINDOW_MIN (200) samples the call FAILS CLOSED - the weekly
    n=50 sample (CI ±6pp) can never decide a Gate (roadmap §1.2 (a)).
    """
    if cumulative_samples < JUDGE_WINDOW_MIN:
        raise JudgeWindowError(
            f"judge window requires >= {JUDGE_WINDOW_MIN} merged samples, "
            f"got {cumulative_samples} (n=50 weekly CI ±6pp cannot decide)"
        )
    rate = cumulative_errors / cumulative_samples
    return {
        "merged_samples": cumulative_samples,
        "merged_errors": cumulative_errors,
        "error_rate": rate,
        "threshold": 0.05,
        "pass": rate <= 0.05,
        "ci_half_width_pp": 3.0,  # n=200, p=5% approx (roadmap §1.2)
    }
