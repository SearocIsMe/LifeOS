#!/usr/bin/env python3
"""Demo C: lifecycle trace (design 01 §4.1).

Same memory in three versions (current / superseded / ambiguous) -> lifecycle
trace output. Conflict resolution never deletes history; ambiguous rows queue
for manual review only (resolve_slot -> ConflictResolution.to_queue_row).

Exit code IS the verdict: 0 pass, 1 fail. Mock mode, auto-executable.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from lifeos.entities import ConflictState, MemoryType, PrivacyLevel  # noqa: E402
from lifeos.store.conflict import resolve_slot  # noqa: E402

T0 = datetime(2026, 9, 1, 9, 0, 0, tzinfo=timezone.utc)


def _memory(memory_id: str, content: str, *, tx_offset: int, conf: float) -> dict:
    """MemoryRecord-shaped mapping sharing one (life_id, slot_key)."""
    return {
        "memory_id": memory_id,
        "life_id": "life-demo-c",
        "type": MemoryType.SEMANTIC.value,
        "content": content,
        "slot_key": "user.goal.current",
        "valid_from": (T0 + timedelta(minutes=tx_offset)).isoformat(),
        "transaction_from": (T0 + timedelta(minutes=tx_offset)).isoformat(),
        "confidence": conf,
        "importance": 3,
        "privacy_level": PrivacyLevel.NORMAL.value,
        "conflict_state": ConflictState.CURRENT.value,
        "version": 1,
    }


def main() -> int:
    # Lifecycle trace via TWO chained resolutions on one memory slot:
    #
    # Resolution 1 (resolved): newest transaction wins ->
    #   winner keeps CURRENT, older write is marked SUPERSEDED.
    # Resolution 2 (ambiguous gate): winner vs a same-instant candidate
    #   with a confidence gap <= 0.05 -> NO auto resolution; candidates
    #   are routed to the manual queue for the named owner.
    resolved = resolve_slot(
        [
            _memory("m-cur", "目标：完成 Phase 2 评审。", tx_offset=30, conf=0.9),
            _memory("m-sup", "目标：完成 Phase 1 评审。", tx_offset=10, conf=0.85),
        ]
    )

    print(f"[Demo C] slot_key={resolved.slot_key} life_id={resolved.life_id}")
    if resolved.winner is not None:
        print(f"[Demo C] resolution_1 winner={resolved.winner.memory_id} (CURRENT)")
    print(f"[Demo C] resolution_1 superseded={[m.memory_id for m in resolved.superseded]}")

    queued = resolve_slot(
        [
            _memory("m-cur", "目标：完成 Phase 2 评审。", tx_offset=30, conf=0.9),
            _memory("m-amb", "目标：完成评审（来源不明）。", tx_offset=30, conf=0.88),
        ]
    )
    print(f"[Demo C] resolution_2 ambiguous={[m.memory_id for m in queued.ambiguous]} (manual queue)")

    ok = True
    # Exactly one CURRENT winner; loser SUPERSEDED; ambiguous gate routes
    # to the manual queue for the named owner only (never auto-resolved).
    if resolved.winner is None or resolved.winner.memory_id != "m-cur":
        print("[Demo C] FAIL: resolution_1 wrong winner (exit 1)")
        ok = False
    if [m.memory_id for m in resolved.superseded] != ["m-sup"]:
        print("[Demo C] FAIL: resolution_1 wrong superseded set (exit 1)")
        ok = False
    if not queued.is_ambiguous or [m.memory_id for m in queued.ambiguous] != ["m-cur", "m-amb"]:
        print("[Demo C] FAIL: resolution_2 ambiguous gate did not fire (exit 1)")
        ok = False

    if ok:
        queue = queued.to_queue_row()
        print(f"[Demo C] queue_row owner={queue['owner']} status={queue['status']}")
        if queue["owner"] != "lifeos-maintainer" or queue["status"] != "pending":
            print("[Demo C] FAIL: bad queue row (exit 1)")
            ok = False

    if ok:
        print("[Demo C] PASS (exit 0)")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
