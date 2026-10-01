#!/usr/bin/env python3
"""Four-baseline real-arm runner (spec §4.4 fair comparison, T5).

Runs the FOUR arms (A/B/C/LifeOS) over the FROZEN scenario probes
(``data/goldset/behavior_scenarios/behavior_scenarios_v0.1.yaml``), each arm
going through its COMPLETE output pipeline (assembly -> client -> Policy
approval -> provenance). Materials are never hand-stitched (spec §4.4:
不允许手工拼接).

Dual mode (same discipline as the H1 real-arm precedent):
- mock (default): MockChatClient - CI/offline, exit code is the verdict;
- real: VLLMChatClient with base_url injected (--base-url), pending the
  endpoint checklist ([`real_arm_checklist.md`](../../reports/baselines/real_arm_checklist.md)).

Outputs (same directory as the mock baselines, mock/real distinguished):
- ``baseline_<X>_real.json`` per arm + ``comparison_real.json``.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from lifeos.baselines.assembly import (  # noqa: E402
    SKELETON_VERSION,
    assemble_a,
    assemble_b,
    assemble_c,
    assemble_lifeos,
)
from lifeos.baselines.real import ChatClient, MockChatClient, VLLMChatClient  # noqa: E402
from lifeos.entities import PolicyResult  # noqa: E402
from lifeos.policy.engine import decide  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
SCENARIOS_FILE = REPO / "data" / "goldset" / "behavior_scenarios" / "behavior_scenarios_v0.1.yaml"
REPORT_DIR = REPO / "reports" / "baselines"

GEN_MODEL = "Qwen3.6-35B-A3B-FP8"
T0 = datetime(2026, 9, 1, 9, 0, 0, tzinfo=timezone.utc)

ARMS = {"A": assemble_a, "B": assemble_b, "C": assemble_c, "LifeOS": assemble_lifeos}


def load_scenarios(
    *,
    situation_filter: set[str] | None = None,
    scenario_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Load frozen probes; filters are deterministic subsets of the frozen set.

    ``scenario_ids`` selects exact probes (blindtest material pool fragments,
    [`material_pool_manifest.json`](../../reports/blindtest/material_pool_manifest.json));
    out-of-set ids are ignored (清单外片段不得入测 discipline).
    """
    import yaml

    doc = yaml.safe_load(SCENARIOS_FILE.read_text(encoding="utf-8"))
    items = doc["items"]
    if situation_filter:
        items = [i for i in items if i.get("situation_tag") in situation_filter]
    if scenario_ids:
        items = [i for i in items if i.get("scenario_id") in scenario_ids]
    return items


def scenario_context(item: dict[str, Any]) -> dict[str, Any]:
    """One frozen probe -> assembly context (deterministic from the preset)."""
    # personality derived from the probe id (placeholder derivation precedent)
    return {
        "personality": {
            "openness": 0.6, "conscientiousness": 0.7, "extraversion": 0.4,
            "agreeableness": 0.8, "neuroticism": 0.3,
        },
        "recent_dialogue": [f"用户: {item['utterance']}"],
        "history_summary": f"此前互动（{item['situation_tag']}）记录于 Life Instance。",
        # Baseline C vector-RAG pool: probe memory candidates (injection=truth
        # analogue: the preset states ARE the truth for this fragment)
        "top_k_memories": [
            {"memory_id": f"ctx-{item['scenario_id']}-{k}", "content": v, "importance": 3}
            for k, v in sorted(item.get("state_preset", {}).items())
        ],
        "kernel_states": dict(item.get("state_preset", {})),
        "relationship": dict(item.get("relationship_preset", {}).get("user", {"familiarity": 0.5, "trust": 0.5, "attachment": 0.5})),
    }


def run_arm(
    arm: str,
    item: dict[str, Any],
    *,
    client: ChatClient,
    decided_at: datetime,
) -> dict[str, Any]:
    """One arm through its COMPLETE pipeline: assemble -> generate -> Policy."""
    assemble = ARMS[arm]
    ctx = scenario_context(item)
    prompt = assemble(ctx, gen_model=GEN_MODEL)
    messages = [
        {"role": "system", "content": prompt.system_prompt},
        {"role": "user", "content": item["utterance"]},
    ]
    resp = client.complete(messages)
    # Policy approval on the same prompt context (主系统门槛 discipline)
    intent = {
        "intent_id": f"intent-{item['scenario_id']}-{arm}",
        "intent_type": item["intent_target"],
        "reason": {"topic_markers": [], "prompt_hash": prompt.prompt_hash},
    }
    decision = decide(intent, {"referenced_memories": []}, decided_at=decided_at)
    return {
        "scenario_id": item["scenario_id"],
        "arm": arm,
        "gen_model": GEN_MODEL,
        "skeleton_version": SKELETON_VERSION,
        "prompt_hash": prompt.prompt_hash,
        "identity_block": prompt.identity_block,
        "response": resp.content,
        "latency_ms": resp.latency_ms,
        "usage": resp.usage,
        "policy_result": decision.result.value,
        "rules_hit": decision.rules_hit,
        "approved": decision.result is PolicyResult.APPROVE,
        # provenance (spec §3.4: 逐笔 ModelInvocation 口径)
        "provenance": {
            "purpose": "baseline-real-arm",
            "model_version": GEN_MODEL,
            "prompt_template_id": SKELETON_VERSION,
            "client": type(client).__name__,
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="four-baseline real-arm runner")
    ap.add_argument("--mode", choices=["mock", "real"], default="mock")
    ap.add_argument("--base-url", default="", help="vLLM base_url for --mode real (checklist 1.2/1.3)")
    ap.add_argument("--model", default=GEN_MODEL)
    ap.add_argument("--limit", type=int, default=0, help="cap the number of probes (0 = all)")
    ap.add_argument(
        "--pool",
        default="",
        help="blindtest material pool manifest (scenario_id filter, e.g. reports/blindtest/material_pool_manifest.json)",
    )
    ap.add_argument(
        "--out-dir",
        default="",
        help="report output dir (default reports/baselines; CI/tests use tmp dirs to avoid overwriting real materials)",
    )
    args = ap.parse_args()

    if args.mode == "real" and not args.base_url:
        print("[BaselinesReal] FAIL: --mode real requires --base-url (checklist 1.2/1.3, no pre-run)")
        return 1
    client: ChatClient = (
        VLLMChatClient(base_url=args.base_url, model=args.model)
        if args.mode == "real"
        else MockChatClient(model=args.model)
    )

    pool_ids: set[str] | None = None
    if args.pool:
        pool = json.loads(Path(args.pool).read_text(encoding="utf-8"))
        pool_ids = {s["scenario_id"] for s in pool["selected_scenarios"]}
    items = load_scenarios(scenario_ids=pool_ids)
    if args.limit:
        items = items[: args.limit]
    # out-dir: CI/tests use tmp dirs to avoid overwriting real materials
    # (素材污染事件修复，2026-09-30)
    out_dir = Path(args.out_dir) if args.out_dir else REPORT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    decided_at = T0

    all_rows: dict[str, list[dict[str, Any]]] = {arm: [] for arm in ARMS}
    for item in items:
        for arm, assemble in ARMS.items():
            all_rows[arm].append(run_arm(arm, item, client=client, decided_at=decided_at))
            decided_at = decided_at + timedelta(seconds=1)

    # per-arm reports (输出分开报告, mock/real distinguished by filename)
    for arm, rows in all_rows.items():
        path = out_dir / f"baseline_{arm}_real.json"
        path.write_text(
            json.dumps({"arm": arm, "mode": args.mode, "gen_model": GEN_MODEL, "rows": rows}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[BaselinesReal] wrote {path}")

    # summary + threshold checks
    summary = []
    ok = True
    for arm, rows in all_rows.items():
        approved = sum(1 for r in rows if r["approved"])
        summary.append(
            {
                "arm": arm,
                "probes": len(rows),
                "policy_approved": approved,
                "avg_latency_ms": round(sum(r["latency_ms"] for r in rows) / len(rows), 3) if rows else 0.0,
            }
        )
    # verdict: mock mode - all arms deterministic + Policy decides; FAIL if any arm empty
    for arm, rows in all_rows.items():
        if not rows:
            print(f"[BaselinesReal] FAIL: arm {arm} produced no rows (exit 1)")
            ok = False

    comparison = {
        "mode": args.mode,
        "gen_model": GEN_MODEL,
        "skeleton_version": SKELETON_VERSION,
        "generated_at": T0.isoformat(),
        "probes": len(items),
        "summary": summary,
        "note": "paired-diff CI awaits blind-test n>=50; this run emits point estimates only",
    }
    comparison_path = out_dir / "comparison_real.json"
    comparison_path.write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[BaselinesReal] wrote {comparison_path}")

    if ok:
        print(f"[BaselinesReal] PASS ({args.mode}, {len(items)} probes x 4 arms, exit 0)")
        return 0
    print("[BaselinesReal] FAIL (exit 1)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
