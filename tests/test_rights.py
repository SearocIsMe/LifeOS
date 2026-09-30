"""Phase 3 S1 acceptance: personal rights channel (query / correct / delete / export).

Case map (design doc 02 §2 S1):
- rights four ops   -> each channel one case; export without dual approval rejected
- correct via L2    -> correction must go through the committed pipeline (RED-09)
- delete delegates  -> delete -> user_erase (physical, all media)
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from lifeos.events.pipeline import EventPipeline
from lifeos.rights import (
    RejectedError,
    correct_user_memory,
    delete_user_memories,
    export_user_data,
    query_user_memories,
)
from lifeos.store.memory_store import InMemoryStore

NOW = datetime(2026, 9, 30, 12, 0, 0, tzinfo=timezone.utc)
LIFE = "life-rights"


def _store() -> tuple[InMemoryStore, list[str]]:
    store = InMemoryStore()
    store.create_instance(
        life_id=LIFE, personality_seed="s1", born_at=NOW, schema_version="0.1.0"
    )
    pipe = EventPipeline(store)
    ids: list[str] = []
    for i in range(2):
        res = pipe.ingest(
            {
                "life_id": LIFE,
                "source": "user",
                "payload": {
                    "text": f"我家猫叫咪咪{i}。",
                    "structured": {
                        "memory_candidates": [
                            {
                                "type": "semantic",
                                "content": f"用户家里养的猫叫咪咪{i}",
                                "slot_key": f"user.pet_{i}",
                                "subject_id": "user",
                                "confidence": 0.95,
                                "importance": 3,
                            }
                        ]
                    },
                },
                "occurred_at": NOW,
            }
        )
        ids.extend(m.memory_id for m in res.effects.memory_inserts)
    return store, ids


def test_query_channel():
    store, _ = _store()
    r = query_user_memories(store, life_id=LIFE, subject_id="user")
    assert r.ok and r.detail["count"] == 2


def test_correct_channel_via_l2():
    store, _ = _store()
    pipe = EventPipeline(store)
    # correction goes through the committed L2 pipeline first (RED-09)
    pipe.ingest(
        {
            "life_id": LIFE,
            "source": "user",
            "payload": {
                "text": "我家猫改名了。",
                "structured": {
                    "memory_candidates": [
                        {
                            "type": "semantic",
                            "content": "用户家里的猫改名了",
                            "slot_key": "user.pet_0",
                            "subject_id": "user",
                            "confidence": 0.99,
                            "importance": 3,
                        }
                    ]
                },
            },
            "occurred_at": NOW,
        }
    )
    r = correct_user_memory(store, life_id=LIFE, new_content="用户家里的猫改名了", slot_key="user.pet_0")
    assert r.ok and r.detail["superseded"] >= 1
    # direct correction without an L2 record fails closed
    with pytest.raises(RejectedError):
        correct_user_memory(store, life_id=LIFE, new_content="不存在的内容", slot_key="user.pet_0")


def test_delete_channel_delegates_erase():
    store, ids = _store()
    report = delete_user_memories(
        store, life_id=LIFE, memory_ids=ids, requested_by="user-1", at=NOW
    )
    assert report.ir_recoverable
    assert len(store.query_memories(life_id=LIFE)) == 0


def test_export_requires_dual_approval():
    store, _ = _store()
    with pytest.raises(RejectedError):
        export_user_data(store, life_id=LIFE, approvals=["a"])
    r = export_user_data(store, life_id=LIFE, approvals=["a", "b"])
    assert r.ok and r.detail["count"] == 2
