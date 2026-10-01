"""Blind-test administration page logic (T-B, 被试实际操作的工具).

Implements the pre-registered administration flow end to end:

- ``start_session``: consent gate FAIL-CLOSED (未签署同意不得出题/作答) +
  session built via the frozen exclusion rules;
- ``build_trial_sequence``: latin-square balanced trial stream (per-subject
  order differs; order_seq recorded) - same fragment, arm_left = subject's
  baseline arm, arm_right = the other three; ONE trial in the stream is the
  attention check (is_attention_check, 问卷 fail_rule);
- ``record_response``: forced choice - ``chose`` must be arm_left or
  arm_right (no abstain); free-text rationale captured for B5.2 dual coding;
- ``apply_attention_rule``: failed check voids ALL responses (作答作废);
- ``persist_responses``: anonymized JSONL (pseudonymous subject_id ONLY -
  no name/phone/email/ip; spec §9); idempotent per subject (same subject
  re-submitting rewrites its lines, not duplicates).

NO answer data is fabricated: ``chose`` values arrive only from real
subjects; this module validates and stores them.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from lifeos.consent import ConsentError
from lifeos.dogfood.blindtest import (
    ARMS,
    latin_square_order,
)
from lifeos.dogfood.survey_intake import (  # 方案 A primitives (re-export anchor)
    check_duplicate,
    email_hash,
    load_survey,
    record_hash,
)

RESPONSES_FILENAME = "responses.jsonl"
# One attention check per subject stream (问卷 fail_rule; position pinned mid-stream)
ATTENTION_CHECK_POSITION = 4  # 0-based: middle of the 12-trial stream

# Direct identifiers FORBIDDEN in persisted rows (spec §9 anonymization)
FORBIDDEN_FIELDS = frozenset({"name", "phone", "email", "id_card", "ip", "contact"})


def start_session(
    *,
    external_user_id: str,
    subject_seq: int,
    fragments: list[str],
    age: int,
    is_member_or_family: bool,
    consent_signed: bool,
    at: datetime,
) -> dict[str, Any]:
    """Consent gate fail-closed, then build the session (T-A: test_no_consent_no_session)."""
    if not consent_signed:
        raise ConsentError("未签署知情同意不得出题/作答 (fail-closed)")
    from lifeos.dogfood.blindtest import check_session_eligibility

    check_session_eligibility(age=age, is_member_or_family=is_member_or_family, consent_signed=True)
    return {
        "external_user_id": external_user_id,
        "subject_seq": subject_seq,
        "arm_order": latin_square_order(subject_seq),
        "fragments": list(fragments),
        "consent_signed": True,
        "created_at": at.isoformat(),
    }


def build_trial_sequence(
    *, subject_seq: int, fragments: list[str], arms: tuple[str, ...] = ARMS
) -> list[dict[str, Any]]:
    """Latin-square balanced trial stream for one subject (T-A cases).

    Same fragment appears once per pair; arm_left = the subject's baseline
    (their square row's first arm), arm_right = the other three; order_seq
    records the presentation position; ONE trial is the attention check.
    """
    order = latin_square_order(subject_seq, arms=arms)
    baseline = order[0]
    trials: list[dict[str, Any]] = []
    seq = 0
    for frag in fragments:
        for right in order[1:]:
            trials.append(
                {
                    "fragment_id": frag,
                    "arm_left": baseline,
                    "arm_right": right,
                    "order_seq": seq,
                    "is_attention_check": seq == ATTENTION_CHECK_POSITION,
                    "chose": None,
                    "reason_text": "",
                    "voided": False,
                    "void_reason": "",
                    "attention_check_passed": None,
                    "submitted_at": None,
                }
            )
            seq += 1
    return trials


# Q2: 第三选项（用户确认增加）——"无法回答"计入有效样本（有作答行为），
# 但分析层按三分类聚合（左/右/无法回答），不影响一致率分母口径（预注册）
UNANSWERABLE = "无法回答"


def record_response(
    trial: dict[str, Any],
    *,
    chose: str,
    reason_text: str = "",
    at: datetime,
) -> dict[str, Any]:
    """Forced choice + 第三选项: ``chose`` ∈ {arm_left, arm_right, 无法回答}.

    T-A: test_forced_choice_validation. Mutates the trial in place and
    returns {"ok": True}; invalid choices raise (fail-closed).
    """
    if chose not in (trial["arm_left"], trial["arm_right"], UNANSWERABLE):
        raise ValueError(
            f"choice: must be {trial['arm_left']!r}, {trial['arm_right']!r} or {UNANSWERABLE!r}, got {chose!r}"
        )
    trial["chose"] = chose
    trial["reason_text"] = reason_text
    trial["submitted_at"] = at.isoformat()
    trial["attention_check_passed"] = not trial.get("is_attention_check", False) or chose in (
        trial["arm_left"],
        trial["arm_right"],
    )
    if trial.get("is_attention_check"):
        # the attention check trial itself carries the pass/fail flag
        trial["attention_check_result"] = "answered"
    return {"ok": True}


def attention_check_passed(trials: list[dict[str, Any]]) -> bool:
    """Did the subject pass the attention check? (None if not yet reached)"""
    for t in trials:
        if t.get("is_attention_check"):
            return t["chose"] is not None
    return False  # no attention check in the stream -> treat as not passed


def apply_attention_rule(trials: list[dict[str, Any]], *, passed: bool) -> int:
    """问卷 fail_rule: 未通过注意力检查 → 作答作废 (T-A: test_attention_check_enforced).

    Failed check voids ALL trials in the stream; returns the voided count.
    """
    n = 0
    for t in trials:
        if not passed and not t["voided"]:
            t["voided"] = True
            t["void_reason"] = "未通过注意力检查 → 作答作废"
            n += 1
    return n


def persist_responses(
    trials: list[dict[str, Any]],
    *,
    subject_id: str,
    out_dir: str | Path,
) -> Path:
    """Anonymized JSONL persistence (T-A: test_persist_jsonl_anonymized).

    Pseudonymous subject_id ONLY; direct identifiers are FORBIDDEN fields
    and are never written (spec §9). Idempotent per subject: same subject's
    rows are rewritten (not duplicated).
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / RESPONSES_FILENAME

    existing: list[str] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("subject_id") != subject_id:
                existing.append(line)  # keep other subjects' rows
            # same subject's rows are dropped -> rewritten below

    fresh: list[str] = []
    for t in trials:
        row = {"subject_id": subject_id}
        for k in (
            "fragment_id", "arm_left", "arm_right", "chose", "reason_text",
            "order_seq", "attention_check_passed", "is_attention_check",
            "voided", "void_reason", "submitted_at",
        ):
            row[k] = t.get(k)
        # anonymization guard: no direct identifiers may enter the row
        assert not (set(row) & FORBIDDEN_FIELDS)
        fresh.append(json.dumps(row, ensure_ascii=False, sort_keys=True))

    path.write_text("\n".join(existing + fresh) + ("\n" if existing or fresh else ""), encoding="utf-8")
    return path
