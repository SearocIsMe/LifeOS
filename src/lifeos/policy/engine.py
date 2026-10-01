"""Policy Engine v0.2: full 10-red-line set (design doc 01 §1.3).

The FLOW SHAPE froze in Phase 0 (``decide`` pure function + injected clock,
approval BEFORE the transaction opens, rejection => PolicyDecision record and
ZERO state side effects per Gate 0 #4). Phase 2 S1 operationalizes the rules
- adding rules never changes the shape.

Red lines (spec §3.3/§9, verbatim keys; verdicts are FIRST DRAFTS, iteration
goes through ADR per roadmap §1.2):

- RED-01 不做医疗诊断 (spec §3.3 red line 8)
- RED-02 sensitive 记忆不进主动话题 (spec §3.3 red line 7)
- RED-03 不替用户做重大人生决定 (spec §3.3)
- RED-04 不做未经同意的第三方代述 (spec §3.3)
- RED-05 不伪造记忆或时间 (spec §3.3 time discipline)
- RED-06 不高危操纵情感（威胁/恐吓/羞辱）(spec §9.1)
- RED-07 未成年人排除 (spec §9.2)
- RED-08 越权隐私分级提升 (spec §9.3)
- RED-09 权限外直写权威表 (Gate 0 #3 - LLM must go through commit_effects)
- RED-10 动机外高危运动参数 (carrier boundary - frozen structured intent,
  no kinematic parameters)

``decide`` remains a PURE function: same input -> same decision, no storage,
no clock (``decided_at`` injected).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from lifeos.entities import PolicyDecision, PolicyResult
from lifeos.events.protocol import derive_id

POLICY_VERSION = "0.2.0"

RED_LINES: dict[str, str] = {
    "RED-01": "不做医疗诊断",
    "RED-02": "sensitive 记忆不进主动话题",
    "RED-03": "不替用户做重大人生决定",
    "RED-04": "不做未经同意的第三方代述",
    "RED-05": "不伪造记忆或时间",
    "RED-06": "不高危操纵情感（威胁/恐吓/羞辱）",
    "RED-07": "未成年人排除",
    "RED-08": "越权隐私分级提升",
    "RED-09": "权限外直写权威表",
    "RED-10": "动机外高危运动参数",
}

# Exactly ten lines, contiguously numbered (S1 acceptance).
assert len(RED_LINES) == 10
assert sorted(RED_LINES) == [f"RED-{i:02d}" for i in range(1, 11)]

# Phase 0 marker table (policy_version-scoped; extendable via ADR).
MEDICAL_TOPIC_MARKERS = ("诊断", "确诊", "用药", "剂量", "处方", "病症", "病理")

# RED-03: intent types that would decide a major life choice for the user.
MAJOR_DECISION_INTENTS = frozenset(
    {"major_decision", "major_life_decision", "decide_for_user"}
)

# RED-06: high-risk emotional manipulation markers (threat / intimidate / humiliate).
MANIPULATION_MARKERS = ("威胁", "恐吓", "羞辱", "manipulate", "threat", "humiliate")

# RED-10: kinematic parameter keys - frozen structured intent must never carry these.
KINEMATIC_KEYS = frozenset(
    {"velocity", "acceleration", "trajectory", "force", "torque", "joint_angle"}
)


def _mem_privacy(mem: Any) -> Any:
    return mem.get("privacy_level") if isinstance(mem, Mapping) else None


def decide(
    intent: Mapping[str, Any],
    context: Mapping[str, Any],
    *,
    policy_version: str = POLICY_VERSION,
    decided_at: datetime,
) -> PolicyDecision:
    """Evaluate a proposed intent against the ten red lines.

    Parameters
    ----------
    intent:
        BehaviorIntent-shaped mapping (needs ``intent_id``, ``intent_type``,
        optional ``reason.topic_markers`` / ``reason.topic_markers``).
    context:
        Must carry ``referenced_memories``: a list of memory-like mappings with
        ``privacy_level`` - the memories this intent would surface. Optional:
        ``actor_age`` (years), ``consented_subject_ids`` (set-like),
        ``write_target`` (str), ``sampling`` (dict with temperature).
    """
    rules_hit: list[str] = []

    intent_type = str(intent.get("intent_type", ""))
    reason = intent.get("reason") or {}
    payload = intent.get("payload") or {}
    topic_markers = reason.get("topic_markers") or []
    if isinstance(topic_markers, str):
        topic_markers = [topic_markers]

    # RED-01 不做医疗诊断
    if intent_type == "medical_diagnosis" or any(
        m in MEDICAL_TOPIC_MARKERS for m in topic_markers
    ):
        rules_hit.append("RED-01")

    referenced = context.get("referenced_memories") or []

    # RED-02 sensitive 记忆不进主动话题
    if any(_mem_privacy(mem) == "sensitive" for mem in referenced):
        rules_hit.append("RED-02")

    # RED-03 不替用户做重大人生决定
    if intent_type in MAJOR_DECISION_INTENTS:
        rules_hit.append("RED-03")

    # RED-04 不做未经同意的第三方代述: speaking for a subject_id outside the
    # consented scope produces the utterance on their behalf.
    subject_id = intent.get("subject_id") or payload.get("subject_id")
    consented = context.get("consented_subject_ids")
    if subject_id and consented is not None and subject_id not in set(consented):
        rules_hit.append("RED-04")

    # RED-05 不伪造记忆或时间: a memory/time reference not backed by L0.
    unbacked = [mem for mem in referenced if isinstance(mem, Mapping) and not mem.get("l0_backed", True)]
    if unbacked:
        rules_hit.append("RED-05")

    # RED-06 不高危操纵情感
    markers_all = list(topic_markers) + [
        str(m) for m in (reason.get("manipulation_markers") or [])
    ]
    modality = str(intent.get("modality", ""))
    if any(m in MANIPULATION_MARKERS for m in markers_all) or (
        intent_type == "emotional_manipulation"
    ) or (modality.startswith("high_risk")):
        rules_hit.append("RED-06")

    # RED-07 未成年人排除
    actor_age = context.get("actor_age")
    if actor_age is not None and float(actor_age) < 18:
        rules_hit.append("RED-07")

    # RED-08 越权隐私分级提升: intent wants to raise a memory's privacy level.
    wants_raise = bool(payload.get("raise_privacy_level"))
    referenced_privs = {_mem_privacy(mem) for mem in referenced}
    if wants_raise or "confidential" in referenced_privs or "restricted" in referenced_privs:
        rules_hit.append("RED-08")

    # RED-09 权限外直写权威表: LLM writing the authoritative store directly
    # (bypassing commit_effects) is out of scope.
    write_target = context.get("write_target")
    if write_target in {"authoritative_store", "postgres_direct", "authoritative_table"} or bool(
        payload.get("direct_db_write")
    ):
        rules_hit.append("RED-09")

    # RED-10 动机外高危运动参数: frozen structured intent, no kinematic params.
    structured = payload.get("structured") if isinstance(payload, Mapping) else None
    carry_keys: set[str] = set()
    if isinstance(structured, Mapping):
        carry_keys |= set(structured.keys())
        inner = structured.get("proposed_intent")
        if isinstance(inner, Mapping):
            carry_keys |= set(inner.keys())
    if carry_keys & KINEMATIC_KEYS or intent_type in {"kinematic_command", "motion_control"}:
        rules_hit.append("RED-10")

    result = PolicyResult.REJECT if rules_hit else PolicyResult.APPROVE
    decision_id = derive_id(
        "PD",
        {
            "intent_id": intent.get("intent_id", ""),
            "rules_hit": rules_hit,
            "policy_version": policy_version,
            "decided_at": decided_at.isoformat(),
        },
    )

    return PolicyDecision(
        decision_id=decision_id,
        intent_id=str(intent.get("intent_id", "")),
        life_id=str(intent.get("life_id", "")),
        rules_hit=rules_hit,
        result=result,
        reason={
            "evaluated_rules": sorted(RED_LINES),
            "intent_type": intent_type,
            "sensitive_referenced": rules_hit.count("RED-02"),
            "score_decomposition": {"rules_hit": rules_hit},
        },
        decided_at=decided_at,
    )
