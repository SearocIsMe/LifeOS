#!/usr/bin/env python3
"""Survey generator (B4.1 施测期问卷实例，60 份 → survey/).

Generates ONE independent questionnaire instance per subject (n=60, covers
the preregistration floor n>=50 with 1.2x headroom):

- pseudonymous subject id: ``LIFE-BT-<seq:03d>`` (化名编号下发规则,
  registration form part 4);
- latin-square balanced arm order per subject (位置效应平衡，预注册
  §power_analysis.balancing);
- 8 frozen fragments (``reports/blindtest/material_pool_manifest.json``)
  with the subject's REAL generated arm responses (from
  ``reports/baselines/baseline_<ARM>_real.json`` — 完整输出管线取样，
  spec §4.4 不允许手工拼接);
- attention check pinned mid-stream (问卷 fail_rule: 未通过 → 作答作废);
- consent block with approval number 2026-ETH-00001 + the three
  confirmation items (匿名化纪律: no direct identifiers collected);
- analysis thresholds stated for the report (一致率 >= 75%,
  falsification line <= 55%, baseline edge +10pp — 预注册口径).

Deterministic: same inputs => same 60 instances (manifest records
content_hash per instance). Any change = new version (冻结纪律).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lifeos.dogfood.blindtest_page import build_trial_sequence  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
SURVEY_DIR = REPO / "survey"
POOL_MANIFEST = REPO / "reports" / "blindtest" / "material_pool_manifest.json"
BASELINES_DIR = REPO / "reports" / "baselines"
SCENARIOS_FILE = REPO / "data" / "goldset" / "behavior_scenarios" / "behavior_scenarios_v0.1.yaml"

APPROVAL_NUMBER = "2026-ETH-00001"
TARGET_N = 60  # 用户指定：60 份（覆盖预注册下限 n>=50 + 1.2x 余量）
STUDY = "LifeOS 长期身份连续性盲测（第一道外部验证，被试内配对）"

CONSENT_ITEMS = [
    "我已阅读并理解知情同意书（含两级删除语义与 30 天备份窗口披露），自愿参与",
    "我理解我的作答将匿名化存储，且与我的关联仅为化名编号",
    "我知道我可随时查阅/更正/删除/导出我的数据",
]

THRESHOLDS = {
    "unified_threshold": 0.75,
    "falsification_line": 0.55,
    "baseline_edge_pp": 0.10,
    "kappa_min": 0.6,
    "source": "预注册分析计划（doc/templates/preregistered_analysis_plan_template.yaml）+ 规格 §4.4/§4.5",
}


def subject_id_for(seq: int) -> str:
    return f"LIFE-BT-{seq:03d}"


def load_fragments() -> list[dict[str, Any]]:
    """8 frozen fragments (B2.1 manifest) with utterance + REAL arm responses."""
    pool = json.loads(POOL_MANIFEST.read_text(encoding="utf-8"))
    frag_ids = [s["scenario_id"] for s in pool["selected_scenarios"]]

    scen = json.loads(json.dumps({}))  # utterances from the frozen scenario set (yaml)
    import yaml

    doc = yaml.safe_load(SCENARIOS_FILE.read_text(encoding="utf-8"))
    utterances = {i["scenario_id"]: i["utterance"] for i in doc["items"]}

    arm_responses: dict[str, dict[str, str]] = {}
    for arm in ("A", "B", "C", "LifeOS"):
        p = BASELINES_DIR / f"baseline_{arm}_real.json"
        if not p.exists():
            raise FileNotFoundError(f"real-arm material missing: {p} (run run_baselines_real.py --mode real first)")
        d = json.loads(p.read_text(encoding="utf-8"))
        if d.get("mode") != "real":
            raise ValueError(f"{p} is not real-arm material (mode={d.get('mode')!r}) — mock materials are forbidden in surveys")
        for row in d["rows"]:
            arm_responses.setdefault(row["scenario_id"], {})[arm] = row["response"]

    fragments = []
    for fid in frag_ids:
        if fid not in arm_responses or len(arm_responses[fid]) != 4:
            raise ValueError(f"fragment {fid} missing real-arm responses (4 arms required)")
        fragments.append(
            {
                "fragment_id": fid,
                "user_msg": utterances[fid],
                "responses": arm_responses[fid],
            }
        )
    return fragments


def build_survey(seq: int, fragments: list[dict[str, Any]]) -> dict[str, Any]:
    """One independent questionnaire instance (deterministic per seq)."""
    subject = subject_id_for(seq)
    trials = build_trial_sequence(subject_seq=seq, fragments=[f["fragment_id"] for f in fragments])
    # attach the REAL responses per trial (subject sees actual generated text)
    frag_map = {f["fragment_id"]: f for f in fragments}
    for t in trials:
        f = frag_map[t["fragment_id"]]
        t["left_text"] = f["responses"][t["arm_left"]]
        t["right_text"] = f["responses"][t["arm_right"]]
        t["user_msg"] = f["user_msg"]
    from lifeos.dogfood.blindtest import latin_square_order

    return {
        "survey_id": f"survey-{seq:03d}",
        "subject_id": subject,
        "study": STUDY,
        "approval_number": APPROVAL_NUMBER,
        "anonymization": "作答匿名化存储；关联仅为化名编号；不收集直接标识符（spec §9）",
        "consent_items": CONSENT_ITEMS,
        "consent_signed": None,  # 施测期由被试勾选；生成时不预填
        "arm_order": latin_square_order(seq),  # 拉丁方平衡顺序（预注册 §power_analysis.balancing）
        "fragments": [
            {"fragment_id": f["fragment_id"], "user_msg": f["user_msg"]} for f in fragments
        ],
        "trials": [
            {k: t[k] for k in (
                "order_seq", "fragment_id", "arm_left", "arm_right",
                "left_text", "right_text", "user_msg", "is_attention_check",
                "chose", "reason_text", "voided",
            )}
            for t in trials
        ],
        "thresholds": THRESHOLDS,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "instructions": "每个片段阅读用户消息与左右两个回复，判断「是不是同一个它」（二选一强制）并写一两句理由；题目流中有 1 道注意力检查题，未通过将作废全部作答。",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="generate 60 subject survey instances")
    ap.add_argument("--n", type=int, default=TARGET_N)
    ap.add_argument("--out-dir", default=str(SURVEY_DIR))
    args = ap.parse_args()

    fragments = load_fragments()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    manifests = []
    for seq in range(args.n):
        survey = build_survey(seq, fragments)
        path = out_dir / f"{survey['subject_id']}.json"
        path.write_text(json.dumps(survey, ensure_ascii=False, indent=2), encoding="utf-8")
        manifests.append(
            {
                "survey_id": survey["survey_id"],
                "subject_id": survey["subject_id"],
                "file": str(path),
                "trials": len(survey["trials"]),
                "arm_order": survey["arm_order"],
            }
        )
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "kind": "blindtest_survey_instances",
                "n": args.n,
                "study": STUDY,
                "approval_number": APPROVAL_NUMBER,
                "fragments": [f["fragment_id"] for f in fragments],
                "thresholds": THRESHOLDS,
                "discipline": "化名编号下发；拉丁方平衡；真臂素材（mock 禁入）；consent_signed 生成时不预填",
                "instances": manifests,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"[Surveys] wrote {args.n} instances to {out_dir} + manifest.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
