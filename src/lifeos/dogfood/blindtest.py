"""Blind-test administration tooling (B3, design: 施测工具建设).

Implements the pre-registered analysis plan's ADMINISTRATION half (no
statistics here - B5 lands with real data):

- ``latin_square_order``: balanced arm presentation order per subject
  (preregistration §power_analysis.balancing: latin square);
- ``build_session``: one subject's paired-comparison session - four arms on
  the same fragment, order balanced, attention check enforced;
- ``check_eligibility``: prereg exclusion rules coded (project members /
  immediate family / minors / attention-check failures) - consistent with
  the frozen preregistration, counts auditable;
- fail-closed: no consent -> no session; failed attention check -> response
  voided (问卷 fail_rule: 未通过注意力检查 → 作答作废).

NO response data is fabricated: sessions are structures; answers arrive
only from real subjects (B4).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from lifeos.consent import ConsentError, check_cohort_eligibility

ARMS = ("A", "B", "C", "LifeOS")

# Prereg exclusion rules (doc/templates/preregistered_analysis_plan_template.yaml).
EXCLUSION_RULES = {
    "project_member": "项目组成员及其直系亲属排除",
    "minor": "未成年人不纳入（<18）",
    "attention_check_failed": "未通过注意力检查 → 作答作废",
    "no_consent": "未签署知情同意不得作答",
}


def latin_square_order(subject_seq: int, *, arms: tuple[str, ...] = ARMS) -> list[str]:
    """Balanced presentation order for one subject (latin square, deterministic).

    Subject i gets the square row (i mod n) rotated - over n subjects each
    arm appears in each position exactly once (平衡).
    """
    n = len(arms)
    row = subject_seq % n
    return [arms[(row + j) % n] for j in range(n)]


@dataclass
class Trial:
    """One paired-comparison trial: same fragment, two arms, forced choice."""

    fragment_id: str
    arm_left: str
    arm_right: str
    chose: str | None = None  # subject's choice; None until answered
    reason_text: str = ""  # free-text rationale (B5.2 dual-coding input)
    voided: bool = False
    void_reason: str = ""


@dataclass
class Session:
    """One subject's blind-test session (structure only - answers come from B4)."""

    external_user_id: str
    subject_seq: int
    arm_order: list[str]
    fragments: list[str]
    trials: list[Trial] = field(default_factory=list)
    consent_signed: bool = False
    attention_check_passed: bool | None = None
    created_at: datetime | None = None

    def summary(self) -> dict[str, Any]:
        return {
            "external_user_id": self.external_user_id,
            "arm_order": self.arm_order,
            "fragments": len(self.fragments),
            "trials": len(self.trials),
            "voided": sum(1 for t in self.trials if t.voided),
            "answered": sum(1 for t in self.trials if t.chose is not None),
        }


def check_session_eligibility(
    *,
    age: int,
    is_member_or_family: bool,
    consent_signed: bool,
) -> None:
    """Prereg exclusion rules, fail-closed (B3.3).

    Same three screens as cohort entry + consent requirement; attention
    checks are per-trial (B3.1) and void responses, not sessions.
    """
    try:
        check_cohort_eligibility(
            age=age, is_member_or_family=is_member_or_family, has_consent_signed=consent_signed
        )
    except ConsentError:
        raise


def build_session(
    *,
    external_user_id: str,
    subject_seq: int,
    fragments: list[str],
    age: int,
    is_member_or_family: bool,
    consent_signed: bool,
    at: datetime,
) -> Session:
    """Build one paired-comparison session (fail-closed on exclusions).

    Arm order = latin square row; trials pair adjacent arms on the SAME
    fragment (被试内配对: each subject judges every arm against the first
    arm in their order, giving n>=50 judgments per arm at n subjects).
    """
    check_session_eligibility(
        age=age, is_member_or_family=is_member_or_family, consent_signed=consent_signed
    )
    order = latin_square_order(subject_seq)
    trials: list[Trial] = []
    for frag in fragments:
        # adjacent pairs in the subject's balanced order: (order[0] vs order[1]),
        # (order[0] vs order[2]), (order[0] vs order[3]) - baseline is order[0]
        for other in order[1:]:
            trials.append(Trial(fragment_id=frag, arm_left=order[0], arm_right=other))
    return Session(
        external_user_id=external_user_id,
        subject_seq=subject_seq,
        arm_order=order,
        fragments=list(fragments),
        trials=trials,
        consent_signed=consent_signed,
        created_at=at,
    )


def void_on_attention_check(session: Session, *, passed: bool) -> int:
    """Apply the attention-check fail rule (问卷 fail_rule: 作答作废).

    Failed check voids ALL of this subject's trials (prereg: 作答作废).
    Returns the number of voided trials.
    """
    session.attention_check_passed = passed
    if passed:
        return 0
    n = 0
    for t in session.trials:
        if not t.voided:
            t.voided = True
            t.void_reason = EXCLUSION_RULES["attention_check_failed"]
            n += 1
    return n


def effective_n(sessions: list[Session]) -> int:
    """Valid subjects = answered >=1 non-voided trial with attention passed."""
    count = 0
    for s in sessions:
        if s.attention_check_passed is not True:
            continue  # None (not yet checked) or False (failed) -> invalid
        if any(t.chose is not None and not t.voided for t in s.trials):
            count += 1
    return count
