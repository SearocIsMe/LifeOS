#!/usr/bin/env python3
"""Demo B: topic suppression (design 01 §4.1, RED-02/RED-08).

Low-privacy topic request × sensitive memories -> Policy Engine rejection
path. The Policy must refuse to surface sensitive memories into a
low-privacy topic, and the rejection must leave ZERO state side effects.

Exit code IS the verdict: 0 pass, 1 fail. Mock mode, auto-executable.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from lifeos.entities import PolicyResult  # noqa: E402
from lifeos.policy.engine import decide  # noqa: E402

T0 = datetime(2026, 9, 1, 9, 0, 0, tzinfo=timezone.utc)

SENSITIVE_MEMORIES = [
    {"memory_id": "m-health-1", "privacy_level": "sensitive", "l0_backed": True},
    {"memory_id": "m-finance-1", "privacy_level": "sensitive", "l0_backed": True},
]

LOW_PRIVACY_INTENT = {
    "intent_id": "intent-b-1",
    "intent_type": "topic_request",
    "reason": {"topic_markers": ["聊天", "天气"]},
}


def main() -> int:
    context = {"referenced_memories": SENSITIVE_MEMORIES}
    decision = decide(LOW_PRIVACY_INTENT, context, decided_at=T0)

    print(f"[Demo B] intent_type={LOW_PRIVACY_INTENT['intent_type']}")
    print(f"[Demo B] sensitive_memories={len(SENSITIVE_MEMORIES)}")
    print(f"[Demo B] result={decision.result} rules_hit={decision.rules_hit}")

    ok = True
    # Rejection path: RED-02 must be hit and the result must be a refusal.
    if "RED-02" not in decision.rules_hit:
        print("[Demo B] FAIL: RED-02 not hit (exit 1)")
        ok = False
    if decision.result != PolicyResult.REJECT:
        print("[Demo B] FAIL: policy did not reject (exit 1)")
        ok = False
    # Zero state side effects: the rejected intent carries no state writes.
    if decision.reason.get("state_writes"):
        print("[Demo B] FAIL: rejection produced state writes (exit 1)")
        ok = False

    if ok:
        print("[Demo B] PASS (exit 0)")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
