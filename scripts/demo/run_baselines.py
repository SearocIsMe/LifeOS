#!/usr/bin/env python3
"""Baseline comparison runner (design 01 §4.2, roadmap S4).

Runs the FOUR baselines (A/B/C/D) against the three-Demo scenario set and
emits one report per baseline + a comparison table, SEPARATE from the main
system metrics (分开报告).

Exit code IS the verdict: 0 pass, 1 fail. Mock mode, auto-executable.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from lifeos.baselines import (  # noqa: E402
    GENERATION_MODEL,
    GENERATION_PROVIDER,
    baseline_a_stateless,
    baseline_b_rag,
    baseline_c_rule_suppression,
    baseline_d_protocol_control,
)
from lifeos.policy.engine import decide  # noqa: E402

T0 = datetime(2026, 9, 1, 9, 0, 0, tzinfo=timezone.utc)
REPORT_DIR = Path(__file__).resolve().parents[2] / "reports" / "baselines"

SENSITIVE_MEMORIES = [
    {
        "memory_id": "m-health-1",
        "privacy_level": "sensitive",
        "l0_backed": True,
        "topic_markers": ["诊断", "用药"],
    },
    {
        "memory_id": "m-finance-1",
        "privacy_level": "sensitive",
        "l0_backed": True,
        "topic_markers": ["收入", "负债"],
    },
]

NORMAL_MEMORY = {
    "memory_id": "m-week-1",
    "privacy_level": "normal",
    "l0_backed": True,
    "topic_markers": ["跑步", "爬山"],
}

SCENARIOS = [
    {
        "name": "privacy_suppression",
        "intent": {
            "intent_id": "intent-sc-1",
            "intent_type": "topic_request",
            "reason": {"topic_markers": ["聊天", "诊断"]},
        },
        # Sensitive memories would surface for this topic (RED-02 / medical markers).
        "referenced_memories": [SENSITIVE_MEMORIES[0], SENSITIVE_MEMORIES[1], NORMAL_MEMORY],
        "recall_all": True,
        "expect_suppression": True,
    },
    {
        "name": "topic_request_normal",
        "intent": {
            "intent_id": "intent-sc-2",
            "intent_type": "topic_request",
            "reason": {"topic_markers": ["跑步", "聊天"]},
        },
        # Planner only surfaces the normal memory for this topic.
        "referenced_memories": [NORMAL_MEMORY],
        "recall_all": False,
        "expect_suppression": False,
    },
]


def _run_scenario(scenario: dict) -> dict:
    intent = scenario["intent"]
    recall_pool = scenario["referenced_memories"]

    rows = []
    # Baseline A: stateless - no memory lookup at all.
    resp_a = baseline_a_stateless(intent)
    rows.append(resp_a.to_report_row())

    # Baseline B: RAG - recall everything, top-k stuffed into prompt.
    resp_b = baseline_b_rag(intent, recall_pool if scenario["recall_all"] else recall_pool)
    rows.append(resp_b.to_report_row())

    # Baseline C: hardcoded suppression, NO Policy Engine.
    resp_c = baseline_c_rule_suppression(intent, recall_pool)
    rows.append(resp_c.to_report_row())

    # Baseline D: protocol control.
    resp_d = baseline_d_protocol_control(intent, recall_pool)
    rows.append(resp_d.to_report_row())

    # Main system: Policy Engine rejection latency for the same intent.
    start = datetime.now(timezone.utc)
    context = {"referenced_memories": recall_pool}
    decision = decide(intent, context, decided_at=T0)
    latency_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000
    main_suppressed = bool(decision.rules_hit)

    return {
        "scenario": scenario["name"],
        "expect_suppression": scenario["expect_suppression"],
        "main_system": {
            "provider": GENERATION_PROVIDER,
            "model": GENERATION_MODEL,
            "suppressed": main_suppressed,
            "suppression_source": "policy_engine",
            "rules_hit": decision.rules_hit,
            "rejection_latency_ms": round(latency_ms, 3),
        },
        "baselines": rows,
    }


def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    results = [_run_scenario(s) for s in SCENARIOS]

    ok = True
    for result in results:
        main_row = result["main_system"]
        baseline_rows = {b["baseline"]: b for b in result["baselines"]}

        # Main system MUST match expectation (统一门槛).
        if result["main_system"]["suppressed"] != result["expect_suppression"]:
            print(f"[Baselines] FAIL: {result['scenario']} main system mismatch (exit 1)")
            ok = False

        # Baseline A can never suppress (no store) - capability 混淆对照.
        if baseline_rows["A"]["suppressed"]:
            print(f"[Baselines] FAIL: {result['scenario']} baseline A suppressed (exit 1)")
            ok = False

        # Baseline B never suppresses (stuffs everything into the prompt).
        if baseline_rows["B"]["suppressed"]:
            print(f"[Baselines] FAIL: {result['scenario']} baseline B suppressed (exit 1)")
            ok = False

        # Baseline C suppression is hardcoded, NOT policy-driven.
        c_row = baseline_rows["C"]
        if c_row["suppressed"] and c_row["suppression_source"] != "hardcoded":
            print(f"[Baselines] FAIL: {result['scenario']} baseline C source (exit 1)")
            ok = False

    # Per-baseline reports (输出分开报告).
    for baseline_id in ("A", "B", "C", "D"):
        rows = [b for r in results for b in r["baselines"] if b["baseline"] == baseline_id]
        path = REPORT_DIR / f"baseline_{baseline_id}.json"
        path.write_text(json.dumps({"baseline": baseline_id, "rows": rows}, ensure_ascii=False, indent=2))
        print(f"[Baselines] wrote {path.relative_to(REPORT_DIR.parents[2])}")

    comparison = {
        "provider": GENERATION_PROVIDER,
        "model": GENERATION_MODEL,
        "generated_at": T0.isoformat(),
        "scenarios": results,
        "summary": [
            {
                "scenario": r["scenario"],
                "main_suppressed": r["main_system"]["suppressed"],
                "baseline_A": next(b["suppressed"] for b in r["baselines"] if b["baseline"] == "A"),
                "baseline_B": next(b["suppressed"] for b in r["baselines"] if b["baseline"] == "B"),
                "baseline_C": next(b["suppressed"] for b in r["baselines"] if b["baseline"] == "C"),
                "baseline_D": next(b["suppressed"] for b in r["baselines"] if b["baseline"] == "D"),
            }
            for r in results
        ],
    }
    comparison_path = REPORT_DIR / "comparison.json"
    comparison_path.write_text(json.dumps(comparison, ensure_ascii=False, indent=2))
    print(f"[Baselines] wrote {comparison_path.relative_to(REPORT_DIR.parents[2])}")

    if ok:
        print("[Baselines] PASS (exit 0)")
        return 0
    print("[Baselines] FAIL (exit 1)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
