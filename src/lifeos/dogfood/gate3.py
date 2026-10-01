"""Gate 3 judgement (Phase 3 S5, spec §10 + design doc 01 §5.1).

Six criteria, aggregated from dogfood + phase-2 blind-test evidence:

| # | 判据 | 数据来源 |
| 1 | 盲测达统一门槛 | blind-test一致率 >= 75% (spec §4.4 Gate 条件) |
| 2 | 优于最佳基线 | paired-diff >= +10pp vs best baseline |
| 3 | 无高危情感操纵 | dogfood weekly reviews aggregate (0 high-risk) |
| 4 | 记忆错误不随量失控 | judge sliding window (>=200 samples, <=5%) |
| 5 | 成本 P95 低于产品线 | ModelInvocation aggregate (product-line threshold injected) |
| 6 | 用户明确感知价值 | dogfood questionnaire aggregate |

Closed-form verdict: all six pass => verdict=PASS; any fail => verdict=FAIL
(no v1 start). PASS is required BEFORE Memory v1 / Kernel v1 / productization
(roadmap §5). Dual signature recorded in the report (signatures field).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from lifeos.dogfood.metrics import judge_memory_error_rate

BLIND_TEST_THRESHOLD = 0.75
BASELINE_EDGE_PP = 0.10
PRODUCT_LINE_P95_MS = 300.0  # spec §3.2 召回性能 P95 < 300 ms (参考配置)


@dataclass
class Gate3Report:
    generated_at: datetime
    verdict: str  # PASS | FAIL
    criteria: list[dict[str, Any]] = field(default_factory=list)
    signatures: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "verdict": self.verdict,
            "criteria": self.criteria,
            "signatures": self.signatures,
        }


def run_gate3(
    *,
    blind_test_rate: float | None = None,
    best_baseline_rate: float | None = None,
    dogfood_high_risk_findings: int | None = None,
    cumulative_errors: int = 0,
    cumulative_samples: int = 0,
    cost_p95_ms: float | None = None,
    perception_score: float | None = None,
    generated_at: datetime | None = None,
) -> Gate3Report:
    """Aggregate the six Gate 3 criteria into a closed verdict.

    Deterministic: same inputs => same verdict. ``perception_score`` is the
    dogfood questionnaire aggregate (criterion 6 reports on it; a score below
    0.5 counts as fail - questionnaire wording pre-registered).

    FAIL-CLOSED against missing real data (2026-09-30 hardening): every
    real-data criterion treats ``None`` (or an empty judge window) as FAIL
    with an error note - absent data is NOT evidence of passing (a caller
    cannot claim "0 high-risk findings" or "cost P95 ok" without dogfood /
    usage data). ``run_gate3()`` with no inputs must always return FAIL.
    """
    generated_at = generated_at or datetime.now(timezone.utc)

    # 1) blind test at the unified threshold
    c1 = {
        "criterion": 1,
        "name": "盲测达统一门槛",
        "value": blind_test_rate,
        "threshold": BLIND_TEST_THRESHOLD,
        "pass": blind_test_rate is not None and blind_test_rate >= BLIND_TEST_THRESHOLD,
    }
    if blind_test_rate is None:
        c1["error"] = "no blind-test data (fail-closed)"
    # 2) better than the best baseline (both arms required)
    if blind_test_rate is not None and best_baseline_rate is not None:
        edge: float | None = blind_test_rate - best_baseline_rate
    else:
        edge = None
    c2 = {
        "criterion": 2,
        "name": "优于最佳基线",
        "value": edge,
        "threshold": BASELINE_EDGE_PP,
        "pass": edge is not None and edge >= BASELINE_EDGE_PP,
    }
    if edge is None:
        c2["error"] = "paired-diff requires both arms (fail-closed)"
    # 3) zero high-risk emotional manipulation (absent data != zero findings)
    c3 = {
        "criterion": 3,
        "name": "无高危情感操纵",
        "value": dogfood_high_risk_findings,
        "threshold": 0,
        "pass": dogfood_high_risk_findings is not None and dogfood_high_risk_findings == 0,
    }
    if dogfood_high_risk_findings is None:
        c3["error"] = "no dogfood review data (fail-closed: absent != zero findings)"
    # 4) memory errors do not spiral with volume (judge sliding window)
    try:
        judge = judge_memory_error_rate(
            cumulative_errors=cumulative_errors, cumulative_samples=cumulative_samples
        )
        c4 = {
            "criterion": 4,
            "name": "记忆错误不随量失控",
            "value": judge["error_rate"],
            "threshold": judge["threshold"],
            "pass": judge["pass"],
            "merged_samples": judge["merged_samples"],
        }
    except ValueError as exc:
        c4 = {
            "criterion": 4,
            "name": "记忆错误不随量失控",
            "value": None,
            "threshold": 0.05,
            "pass": False,
            "error": str(exc),
        }
    # 5) cost P95 below the product line (absent usage data != passing)
    c5 = {
        "criterion": 5,
        "name": "成本P95低于产品线",
        "value": cost_p95_ms,
        "threshold": PRODUCT_LINE_P95_MS,
        "pass": cost_p95_ms is not None and cost_p95_ms < PRODUCT_LINE_P95_MS,
    }
    if cost_p95_ms is None:
        c5["error"] = "no usage data (fail-closed)"
    # 6) users clearly perceive state/relationship/memory value
    c6 = {
        "criterion": 6,
        "name": "用户明确感知价值",
        "value": perception_score,
        "threshold": 0.5,
        "pass": perception_score is not None and perception_score >= 0.5,
    }
    if perception_score is None:
        c6["error"] = "no questionnaire data (fail-closed)"

    criteria = [c1, c2, c3, c4, c5, c6]
    verdict = "PASS" if all(c["pass"] for c in criteria) else "FAIL"
    return Gate3Report(
        generated_at=generated_at, verdict=verdict, criteria=criteria
    )
