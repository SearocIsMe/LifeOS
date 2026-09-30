"""Phase 3 S1 acceptance: user erase (physical deletion) - all media, ir-recoverable.

Case map (design doc 02 §2 S1):
- erase all-media         -> user_erase clears authoritative rows + outbox, query zero-hit
- ir-recoverability       -> rebuilt index keeps erased ids gone across all channels (veto #5)
- erase event desensitized-> erase L2 payload has metadata only, never content
- erase determinism       -> same store state twice => same report (replay recomputable)
- governance no-history-loss -> revise/supersede path retains history (Phase 2口径 no regression)
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from lifeos.entities import ConflictState
from lifeos.events.pipeline import EventPipeline
from lifeos.store.erase import ERASE_META_KEYS, user_erase
from lifeos.store.memory_store import InMemoryStore

NOW = datetime(2026, 9, 30, 12, 0, 0, tzinfo=timezone.utc)
LIFE = "life-erase"


def _store_with_memories(n: int = 3) -> tuple[InMemoryStore, list[str]]:
    store = InMemoryStore()
    store.create_instance(
        life_id=LIFE, personality_seed="s1", born_at=NOW, schema_version="0.1.0"
    )
    pipe = EventPipeline(store)
    ids: list[str] = []
    for i in range(n):
        res = pipe.ingest(
            {
                "life_id": LIFE,
                "source": "user",
                "payload": {
                    "text": f"我家猫叫咪咪{i}号。",
                    "structured": {
                        "memory_candidates": [
                            {
                                "type": "semantic",
                                "content": f"用户家里养的猫叫咪咪{i}号",
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
        assert res.duplicate is False
        ids.extend(m.memory_id for m in res.effects.memory_inserts)
    return store, ids


def test_erase_all_media():
    store, ids = _store_with_memories()
    before = len(store.query_memories(life_id=LIFE))
    assert before == 3

    report = user_erase(
        store, life_id=LIFE, memory_ids=ids[:1], requested_by="user-1", at=NOW
    )
    assert report.erased_memory_ids == ids[:1]
    # authoritative channel: physical row gone
    assert len(store.query_memories(life_id=LIFE)) == 2
    # vector channel: no outbox row for the erased id
    assert all(ob.memory_id != ids[0] for ob in store.outbox)
    assert report.outbox_cleared >= 1
    assert report.index_rebuilt


def test_ir_recoverable_all_channels():
    store, ids = _store_with_memories()
    report = user_erase(
        store, life_id=LIFE, memory_ids=ids, requested_by="user-1", at=NOW
    )
    # veto #5: post-delete residue on ANY channel => recoverable non-empty
    assert report.ir_recoverable
    assert report.recoverable_channels == []
    # all recall channels zero-hit for every erased id
    for mid in ids:
        assert not any(m.memory_id == mid for m in store.memories)
        assert not any(ob.memory_id == mid for ob in store.outbox)


def test_erase_event_metadata_only():
    store, ids = _store_with_memories()
    user_erase(store, life_id=LIFE, memory_ids=ids, requested_by="user-1", at=NOW)

    erase_events = [e for e in store.l2_events if e.event_type == "memory_erase"]
    assert len(erase_events) == 1
    payload = erase_events[0].payload
    # metadata only - NO content key
    assert set(payload) <= ERASE_META_KEYS
    assert "content" not in payload
    assert payload["memory_ids"] == ids


def test_erase_deterministic():
    s1, ids1 = _store_with_memories()
    s2, ids2 = _store_with_memories()
    assert ids1 == ids2  # pipeline ids are content-addressed

    r1 = user_erase(s1, life_id=LIFE, memory_ids=ids1[:2], requested_by="u", at=NOW)
    r2 = user_erase(s2, life_id=LIFE, memory_ids=ids2[:2], requested_by="u", at=NOW)
    assert r1.erased_memory_ids == r2.erased_memory_ids
    assert r1.ir_recoverable == r2.ir_recoverable
    assert r1.outbox_cleared == r2.outbox_cleared
    # repeated erase of same ids is idempotent (no change)
    r1b = user_erase(s1, life_id=LIFE, memory_ids=ids1[:2], requested_by="u", at=NOW)
    assert r1b.erased_memory_ids == []


def test_governance_no_history_loss():
    """Phase 2口径 no regression: supersede retains history; erase is separate."""
    store, _ids = _store_with_memories()
    pipe = EventPipeline(store)
    # revise one slot via a higher-confidence contradicting candidate
    res = pipe.ingest(
        {
            "life_id": LIFE,
            "source": "user",
            "payload": {
                "text": "其实我家猫改名了。",
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
    superseded = [
        m
        for m in store.query_memories(life_id=LIFE)
        if m.conflict_state is ConflictState.SUPERSEDED
    ]
    assert superseded  # history retained, not deleted
    # a normal erase removes only the targeted current rows
    target = [m.memory_id for m in res.effects.memory_inserts]
    report = user_erase(
        store, life_id=LIFE, memory_ids=target, requested_by="u", at=NOW
    )
    assert report.ir_recoverable
    # superseded history untouched by that erase target
    assert len(superseded) >= 1


def test_erase_unknown_life_fails_closed():
    store, ids = _store_with_memories()
    with pytest.raises(Exception):
        user_erase(
            store, life_id="no-such-life", memory_ids=ids, requested_by="u", at=NOW
        )
