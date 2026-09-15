"""Policy Engine v0 minimal skeleton (design doc 01 §6).

Two red lines operationalize the approval flow (full 10-red-line set lands in
Phase 2 S1 - the FLOW SHAPE freezes here, adding rules never changes it):

- RED-01 不做医疗诊断 (spec §3.3 red line 8)
- RED-02 sensitive 记忆不进主动话题 (spec §3.3 red line 7)

``decide`` is a PURE function: same input -> same decision, no storage, no
clock (``decided_at`` injected). Approval happens BEFORE the transaction
opens; rejection produces a PolicyDecision record and ZERO state side effects
(Gate 0 #4). The status transition ``proposed -> approved/rejected`` may only
be performed with a decision in hand (enforced by the store's write guards).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from lifeos.entities import PolicyDecision, PolicyResult
from lifeos.events.protocol import derive_id

POLICY_VERSION = "0.1.0"

RED_LINES: dict[str, str] = {
    "RED-01": "不做医疗诊断",
    "RED-02": "sensitive 记忆不进主动话题",
}

# Phase 0 marker table (policy_version-scoped; extendable via ADR).
MEDICAL_TOPIC_MARKERS = ("诊断", "确诊", "用药", "剂量", "处方", "病症", "病理")


def decide(
    intent: Mapping[str, Any],
    context: Mapping[str, Any],
    *,
    policy_version: str = POLICY_VERSION,
    decided_at: datetime,
) -> PolicyDecision:
    """Evaluate a proposed intent against the red lines.

    Parameters
    ----------
    intent:
        BehaviorIntent-shaped mapping (needs ``intent_id``, ``intent_type``,
        optional ``reason.topic_markers``).
    context:
        Must carry ``referenced_memories``: a list of memory-like mappings with
        ``privacy_level`` - the memories this intent would surface.
    """
    rules_hit: list[str] = []

    intent_type = str(intent.get("intent_type", ""))
    reason = intent.get("reason") or {}
    topic_markers = reason.get("topic_markers") or []
    if isinstance(topic_markers, str):
        topic_markers = [topic_markers]

    if intent_type == "medical_diagnosis" or any(
        m in MEDICAL_TOPIC_MARKERS for m in topic_markers
    ):
        rules_hit.append("RED-01")

    referenced = context.get("referenced_memories") or []
    if any(
        isinstance(mem, Mapping) and mem.get("privacy_level") == "sensitive"
        for mem in referenced
    ):
        rules_hit.append("RED-02")

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
        },
        decided_at=decided_at,
    )
