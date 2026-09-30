"""S2 artifact generator - deterministic labeled annotation draft + ambiguous queue
(design phases/phase-2/01 §2, roadmap S2).

Outputs:

- ``phases/phase-2/reports/labeled_core_facts_v0.1.draft.yaml``
  300-item labeled annotation draft (L0 event -> memory record) with slots for
  annotator A/B and an arbitrator. This is a DRAFT: human dual annotation +
  arbitration are required before registration into ``GoldSetRegistry``.
- ``phases/phase-2/reports/ambiguous_queue.json``
  Deterministically derived from seeded records via
  ``lifeos.store.conflict.resolve_slot`` - step-1/2 ties with a near-equal
  confidence gap (0 < gap <= 0.05) are routed here, NOT auto-resolved.

Determinism: fixed seed, no wall clock in item content.
"""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from lifeos.entities import ConflictState, MemoryType
from lifeos.store.conflict import resolve_slot

SEED = 20260901
N_ITEMS = 300
ROOT = Path(__file__).resolve().parent.parent
REPORT_DIR = ROOT / "phases" / "phase-2" / "reports"

TYPES = [MemoryType.EPISODIC, MemoryType.SEMANTIC]
SLOT_KEYS = [
    "user.profile.name",
    "user.profile.timezone",
    "user.preference.focus",
    "user.goal.current",
    "user.habit.review",
]
CONTENT_TPL = [
    "用户在 {day} 提到 {topic}",
    "{topic} 的记录（{day}）",
    "关于 {topic} 的要点（{day} 整理）",
]
TOPICS = ["晨间回顾", "周复盘", "阅读笔记", "写作草稿", "健康记录", "财务流水"]

EPOCH = datetime(2026, 9, 1, tzinfo=timezone.utc)


def build_records() -> list[dict]:
    """Generate N_ITEMS deterministic memory records (fixed seed)."""
    rng = random.Random(SEED)
    records = []
    for i in range(N_ITEMS):
        tx = EPOCH + timedelta(days=rng.randint(0, 20), minutes=rng.randint(0, 1440))
        valid = tx - timedelta(days=rng.randint(0, 3))
        # ~10% of items collide into a dedicated random-collision slot so conflict
        # governance paths run WITHOUT polluting the deliberate near-tie slots.
        slot = f"memo.random-collision.{rng.choice(['a', 'b'])}" if i % 10 == 0 else f"memo.{i}"
        records.append(
            {
                "memory_id": f"memo-{SEED}-{i:04d}",
                "life_id": "life-demo",
                "subject_id": "user",
                "type": rng.choice(TYPES),
                "content": rng.choice(CONTENT_TPL).format(
                    day=valid.date().isoformat(), topic=rng.choice(TOPICS)
                ),
                "slot_key": slot,
                "valid_from": valid.isoformat(),
                "transaction_from": tx.isoformat(),
                "confidence": round(rng.uniform(0.5, 1.0), 4),
                "importance": rng.randint(1, 5),
            }
        )
    # Deliberate near-tie collision groups: identical tx AND valid (steps 1+2 both
    # tie) with a confidence gap in (0, 0.05] -> resolve_slot routes them to the
    # ambiguous manual queue instead of auto-resolving.
    for idx, slot in enumerate(SLOT_KEYS):
        base_tx = EPOCH + timedelta(days=1 + idx, hours=9)
        base_valid = base_tx - timedelta(days=1)
        gap = round(0.01 + 0.01 * idx, 4)  # 0.01..0.05 - all within the ambiguous band
        for j, delta in enumerate((0.0, gap)):
            records.append(
                {
                    "memory_id": f"memo-{SEED}-tie{idx:02d}{j}",
                    "life_id": "life-demo",
                    "subject_id": "user",
                    "type": TYPES[idx % len(TYPES)],
                    "content": f"同槽位并列备忘 {slot}（{base_valid.date().isoformat()} 整理）",
                    "slot_key": slot,
                    "valid_from": base_valid.isoformat(),
                    "transaction_from": base_tx.isoformat(),
                    "confidence": round(0.75 + delta, 4),
                    "importance": 2,
                }
            )
    return records


def derive_ambiguous_queue(records: list[dict]) -> list[dict]:
    """Group by slot_key, resolve each slot, collect ambiguous rows."""
    groups: dict[str, list[dict]] = {}
    for r in records:
        groups.setdefault(r["slot_key"], []).append(r)
    rows = []
    for slot, group in sorted(groups.items()):
        # resolve_slot requires datetime objects - coerce from ISO strings.
        coerced = []
        for r in group:
            rc = dict(r)
            rc["valid_from"] = datetime.fromisoformat(rc["valid_from"])
            rc["transaction_from"] = datetime.fromisoformat(rc["transaction_from"])
            coerced.append(rc)
        res = resolve_slot(coerced)
        if res.is_ambiguous:
            rows.append(res.to_queue_row())
    return rows


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    records = build_records()

    queue_path = REPORT_DIR / "ambiguous_queue.json"
    rows = derive_ambiguous_queue(records)
    queue_path.write_text(
        json.dumps(
            {
                "seed": SEED,
                "policy": "steps-1-and-2-tied with confidence gap in (0, 0.05] - no auto adjudication",
                "policy_state": ConflictState.AMBIGUOUS.value,
                "owner": "lifeos-maintainer",
                "queue": rows,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    draft_path = REPORT_DIR / "labeled_core_facts_v0.1.draft.yaml"
    items = []
    for r in records:
        items.append(
    {
        **r,
        # Dual annotation NOT yet performed (DoD phase-2 item 2):
        # annotator fields stay EMPTY until real annotators fill them -
        # pre-filling names would fabricate review provenance.
        "annotation": {
            "annotator_a": "",
            "annotator_b": "",
            "kappa_note": "",
            "arbitrator": "",
            "arbitration_note": "",
        },
    }
)
    draft_path.write_text(
        json.dumps(
            {
                "meta": {
                    "seed": SEED,
                    "kind": "core_facts",
                    "item_count": len(items),  # 300 base + 10 tie rows, must equal len(items)
                    "status": "draft-awaiting-dual-annotation",
                },
                "review": {"author": "", "reviewer": "", "arbitrator": ""},
                "items": items,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {queue_path} ({len(rows)} ambiguous rows)")
    print(f"wrote {draft_path} ({N_ITEMS} items)")


if __name__ == "__main__":
    main()
