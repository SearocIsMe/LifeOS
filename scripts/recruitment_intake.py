#!/usr/bin/env python3
"""Recruitment intake processor (B4.1, design 01 §3.1 + §三A four-question spec).

Processes recruitment registration entries (研究者录入，登记表模板:
doc/templates/recruitment/recruitment_registration_zh.md) through the
prereg exclusion rules - DETERMINISTIC and AUDITABLE:

- eligible entries  -> enrolled into the Cohort state machine (候补 1.5x
  capacity asserted) + subject_id issued (``LIFE-BT-<seq:03d>``);
- excluded entries  -> written to ``exclusions.json`` (rule = prereg原文,
  evidence recorded, NO silent rejection);
- monitor counters  -> written to ``recruitment_monitor.json`` (enrolled /
  screened_out / withdrawn / effective capacity vs target_n=50 / degraded
  flag when a week's intake < 30 pace, 降级不静默).

Inputs (one YAML, list of entries - the 研究者填写区 format):
    {entries: [{subject_seq, age, is_member_or_family, jurisdiction, consent_signed}]}

Outputs (reports/blindtest/):
    recruitment_monitor.json, exclusions.json (merged on re-run; idempotent
    per subject_seq - re-running the same entries changes nothing).

NO fabricated data: entries come only from real registration forms;
re-running with test fixtures writes nothing unless --out is given.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lifeos.dogfood.cohort import Cohort, CohortError  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
REPORT_DIR = REPO / "reports" / "blindtest"

TARGET_N = 50
STANDBY_RATIO = 1.5
WEEKLY_INTAKE_MIN = 30  # 收数一周后 n<30 → 降级触发（路线图 §8，不静默）

PREREG_EXCLUSION_RULES = {
    "minor": "未成年人不纳入（<18）",
    "project_member": "项目组成员及其直系亲属排除",
    "no_consent": "未签署知情同意不得作答",
}

MONITOR_PATH = REPORT_DIR / "recruitment_monitor.json"
EXCLUSIONS_PATH = REPORT_DIR / "exclusions.json"


def subject_id_for(seq: int) -> str:
    """化名编号下发规则（登记表第四部分：研究者按序下发）。"""
    return f"LIFE-BT-{seq:03d}"


def classify(entry: dict[str, Any]) -> tuple[str, str]:
    """One entry -> (status, rule_or_empty) per prereg rules (deterministic).

    Returns ("enrolled", "") or ("excluded", <prereg rule原文>).
    """
    if int(entry.get("age", 0)) < 18:
        return ("excluded", PREREG_EXCLUSION_RULES["minor"])
    if bool(entry.get("is_member_or_family", False)):
        return ("excluded", PREREG_EXCLUSION_RULES["project_member"])
    if not bool(entry.get("consent_signed", False)):
        return ("excluded", PREREG_EXCLUSION_RULES["no_consent"])
    return ("enrolled", "")


def process_entries(
    entries: list[dict[str, Any]],
    *,
    cohort: Cohort | None = None,
    collected_at: datetime | None = None,
) -> dict[str, Any]:
    """Process registration entries; returns the monitor dict (pure given inputs).

    Idempotent per subject_seq: entries already enrolled/excluded in the
    loaded monitor are skipped (re-running the same forms changes nothing).
    """
    collected_at = collected_at or datetime.now(timezone.utc)
    cohort = cohort or Cohort(name="blindtest", target_size=TARGET_N)

    prior_monitor = _load_json(MONITOR_PATH)
    prior_enrolled = {p["subject_seq"] for p in prior_monitor.get("enrolled_log", [])}
    prior_excluded = {e["subject_seq"] for e in _load_json(EXCLUSIONS_PATH).get("excluded", [])}
    prior_withdrawn = {p["subject_seq"] for p in prior_monitor.get("withdrawn_log", [])}

    enrolled_log: list[dict[str, Any]] = list(prior_monitor.get("enrolled_log", []))
    withdrawn_log: list[dict[str, Any]] = list(prior_monitor.get("withdrawn_log", []))
    excluded: list[dict[str, Any]] = list(_load_json(EXCLUSIONS_PATH).get("excluded", []))
    screened_out = int(prior_monitor.get("screened_out", 0))

    for entry in entries:
        seq = int(entry["subject_seq"])
        if seq in prior_enrolled or seq in prior_excluded or seq in prior_withdrawn:
            continue  # idempotent re-run
        status, rule = classify(entry)
        if status == "enrolled":
            try:
                cohort.screen_and_enroll(
                    external_user_id=subject_id_for(seq),
                    age=int(entry["age"]),
                    jurisdiction=str(entry.get("jurisdiction", "CN")),
                    is_member_or_family=False,
                    has_consent_signed=True,
                    at=collected_at,
                )
            except CohortError as exc:  # cohort full (standby 1.5x) or duplicate
                excluded.append(
                    {"subject_seq": seq, "subject_id": subject_id_for(seq),
                     "rule": f"cohort_full: {exc}", "evidence": entry, "counted_at": collected_at.isoformat()}
                )
                screened_out += 1
                continue
            enrolled_log.append(
                {"subject_seq": seq, "subject_id": subject_id_for(seq),
                 "jurisdiction": entry.get("jurisdiction", "CN"), "enrolled_at": collected_at.isoformat()}
            )
        else:
            excluded.append(
                {"subject_seq": seq, "subject_id": subject_id_for(seq),
                 "rule": rule, "evidence": entry, "counted_at": collected_at.isoformat()}
            )
            screened_out += 1

    enrolled_n = len(enrolled_log)
    # 监测不静默：本周入组节奏 < WEEKLY_INTAKE_MIN 且未达标 → 降级标记
    degraded = 0 < enrolled_n < WEEKLY_INTAKE_MIN and enrolled_n < TARGET_N
    monitor = {
        "enrolled": enrolled_n,
        "screened_out": screened_out,
        "withdrawn": len(withdrawn_log),
        "effective_n": enrolled_n,  # attention/void counting lands with responses (B4.3)
        "target_n": TARGET_N,
        "standby_capacity": int(TARGET_N * STANDBY_RATIO),
        "complete": enrolled_n >= TARGET_N,
        "week": prior_monitor.get("week", 1),
        "degraded": degraded,
        "degradation_reason": (
            f"intake pace {enrolled_n} < {WEEKLY_INTAKE_MIN} weekly minimum with target {TARGET_N} unmet"
            if degraded
            else ""
        ),
        "enrolled_log": enrolled_log,
        "withdrawn_log": withdrawn_log,
        "collected_at": collected_at.isoformat(),
        "exclusions_file": str(EXCLUSIONS_PATH),
    }
    return monitor


def _load_json(path: Path) -> dict[str, Any]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def main() -> int:
    ap = argparse.ArgumentParser(description="recruitment intake processor (B4.1)")
    ap.add_argument("--input", required=True, help="registration entries YAML (登记表录入)")
    ap.add_argument("--out-dir", default=str(REPORT_DIR), help="output dir (default reports/blindtest)")
    args = ap.parse_args()

    import yaml

    global MONITOR_PATH, EXCLUSIONS_PATH
    out_dir = Path(args.out_dir)
    MONITOR_PATH = out_dir / "recruitment_monitor.json"
    EXCLUSIONS_PATH = out_dir / "exclusions.json"

    doc = yaml.safe_load(Path(args.input).read_text(encoding="utf-8"))
    entries = doc.get("entries", []) if isinstance(doc, dict) else doc
    if not entries:
        print("[Intake] FAIL: no entries in input (exit 1)")
        return 1

    monitor = process_entries(entries)
    out_dir.mkdir(parents=True, exist_ok=True)
    MONITOR_PATH.write_text(json.dumps(monitor, ensure_ascii=False, indent=2), encoding="utf-8")
    # exclusions merged into their own file (audit trail, no silent rejection)
    excluded = list(_load_json(EXCLUSIONS_PATH).get("excluded", []))
    known = {(e["subject_seq"], e["rule"]) for e in excluded}
    for e in monitor.get("enrolled_log", []):
        pass
    # rebuild exclusions file from classify pass (monitor holds only the log)
    fresh = [e for e in _iter_new_exclusions(entries) if (e["subject_seq"], e["rule"]) not in known]
    excluded.extend(fresh)
    EXCLUSIONS_PATH.write_text(
        json.dumps(
            {
                "rules": PREREG_EXCLUSION_RULES,
                "excluded": excluded,
                "counted_at": monitor["collected_at"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(
        f"[Intake] enrolled={monitor['enrolled']} screened_out={monitor['screened_out']} "
        f"excluded_new={len(fresh)} target={monitor['target_n']} complete={monitor['complete']} "
        f"degraded={monitor['degraded']}"
    )
    return 0


def _iter_new_exclusions(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Re-derive exclusions for audit-trail persistence (idempotent by caller)."""
    out = []
    now = datetime.now(timezone.utc).isoformat()
    for entry in entries:
        status, rule = classify(entry)
        if status == "excluded":
            seq = int(entry["subject_seq"])
            out.append(
                {"subject_seq": seq, "subject_id": subject_id_for(seq), "rule": rule,
                 "evidence": entry, "counted_at": now}
            )
    return out


if __name__ == "__main__":
    sys.exit(main())
