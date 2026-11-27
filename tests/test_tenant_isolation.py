"""S0d: cross-tenant isolation assertions (Idensona v0.9.2, TL-1/TL-3, SE-3).

These tests encode the contract the multi-tenant cloud (CH-A) depends on:

- A tenant may not observe another tenant's instances, events, memories or
  relationships, even when both use the *same* ``life_id`` string. Identifier
  reuse across tenants is normal (``life-1`` in tenant A and tenant B are two
  different lives), so the store must key on (tenant_id, life_id).
- ``tenant_id`` defaults to ``default`` so every pre-cloud caller keeps working
  unchanged (that is what keeps the 259-test P0 suite green).

Scope honesty: this covers the in-memory authoritative store. The PostgreSQL
store path is asserted by the same predicate shape but is not exercised here
(no DATABASE_URL in this workspace) - see alembic 0002's docstring.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from lifeos.context import RequestContext
from lifeos.entities import (
    DomainEvent,
    EventSource,
    InterpretedEvent,
    InterpreterType,
    MemoryRecord,
    MemoryType,
    RelationshipState,
)
from lifeos.store.memory_store import InMemoryStore, IsolationError


def _now() -> datetime:
    return datetime(2026, 11, 27, tzinfo=timezone.utc)


def _store() -> InMemoryStore:
    return InMemoryStore()


def _mk(life_id: str, tenant_id: str = "default"):
    """Create one instance and return its store key."""
    store = _store()
    store.create_instance(
        life_id=life_id,
        personality_seed="seed",
        born_at=_now(),
        schema_version="v1",
        tenant_id=tenant_id,
    )
    return store


# --------------------------------------------------------------------------- #
# Instance-level: identifier reuse across tenants must not collide
# --------------------------------------------------------------------------- #
def test_same_life_id_in_two_tenants_are_two_instances() -> None:
    store = _store()
    store.create_instance(
        life_id="life-1",
        personality_seed="a",
        born_at=_now(),
        schema_version="v1",
        tenant_id="tenant-a",
    )
    store.create_instance(
        life_id="life-1",
        personality_seed="b",
        born_at=_now(),
        schema_version="v1",
        tenant_id="tenant-b",
    )

    a = store.get_instance(tenant_id="tenant-a", life_id="life-1")
    b = store.get_instance(tenant_id="tenant-b", life_id="life-1")
    assert a is not None and b is not None
    assert a.personality_seed == "a"
    assert b.personality_seed == "b"
    assert a.tenant_id == "tenant-a"
    assert b.tenant_id == "tenant-b"


def test_duplicate_life_id_within_one_tenant_is_rejected() -> None:
    store = _store()
    store.create_instance(
        life_id="life-1",
        personality_seed="a",
        born_at=_now(),
        schema_version="v1",
        tenant_id="tenant-a",
    )
    with pytest.raises(ValueError):
        store.create_instance(
            life_id="life-1",
            personality_seed="b",
            born_at=_now(),
            schema_version="v1",
            tenant_id="tenant-a",
        )


def test_instance_lookup_is_tenant_scoped() -> None:
    store = _mk("life-1", tenant_id="tenant-a")
    # tenant-b never created life-1: must not be able to read it.
    assert store.get_instance(tenant_id="tenant-b", life_id="life-1") is None
    with pytest.raises(IsolationError):
        store._require_life(tenant_id="tenant-b", life_id="life-1")


# --------------------------------------------------------------------------- #
# Event level
# --------------------------------------------------------------------------- #
def test_raw_event_ingest_is_tenant_scoped() -> None:
    store = _mk("life-1", tenant_id="tenant-a")
    assert (
        store.ingest_raw(
            tenant_id="tenant-a",
            life_id="life-1",
            source=EventSource.USER,
            payload={"text": "hello"},
            occurred_at=_now(),
        )
        is not None
    )
    # Same life_id, wrong tenant: no instance -> fail closed.
    with pytest.raises(IsolationError):
        store.ingest_raw(
            tenant_id="tenant-b",
            life_id="life-1",
            source=EventSource.USER,
            payload={"text": "hello"},
            occurred_at=_now(),
        )


def test_l1_order_never_spans_tenants() -> None:
    store = _store()
    for tenant in ("tenant-a", "tenant-b"):
        store.create_instance(
            life_id="life-1",
            personality_seed=tenant,
            born_at=_now(),
            schema_version="v1",
            tenant_id=tenant,
        )

    for tenant, text in (("tenant-a", "from-a"), ("tenant-b", "from-b")):
        raw = store.ingest_raw(
            tenant_id=tenant,
            life_id="life-1",
            source=EventSource.USER,
            payload={"text": text},
            occurred_at=_now(),
        )
        assert raw is not None
        store.archive_l1(
            InterpretedEvent(
                tenant_id=tenant,
                event_id=f"l1-{tenant}",
                life_id="life-1",
                raw_event_id=raw.event_id,
                output_json={"text": text},
                interpreter_type=InterpreterType.RULE,
                input_hash="h",
                extractor_version="v1",
                interpreted_at=_now(),
            )
        )

    a = store.range_l1(tenant_id="tenant-a", life_id="life-1")
    b = store.range_l1(tenant_id="tenant-b", life_id="life-1")
    assert [e.event_id for e in a] == ["l1-tenant-a"]
    assert [e.event_id for e in b] == ["l1-tenant-b"]


def test_l2_lookup_rejects_foreign_tenant() -> None:
    store = _mk("life-1", tenant_id="tenant-a")
    raw = store.ingest_raw(
        tenant_id="tenant-a",
        life_id="life-1",
        source=EventSource.USER,
        payload={"text": "x"},
        occurred_at=_now(),
    )
    assert raw is not None
    l1 = InterpretedEvent(
        tenant_id="tenant-a",
        event_id="l1-1",
        life_id="life-1",
        raw_event_id=raw.event_id,
        output_json={},
        interpreter_type=InterpreterType.RULE,
        input_hash="h",
        extractor_version="v1",
        interpreted_at=_now(),
    )
    store.archive_l1(l1)
    store.archive_l2(
        DomainEvent(
            tenant_id="tenant-a",
            event_id="l2-1",
            life_id="life-1",
            l1_event_id="l1-1",
            event_type="memory_candidates",
            payload={},
            schema_version="v1",
            policy_version="p1",
            committed_at=_now(),
        )
    )

    # tenant-a sees it; tenant-b is refused rather than silently returning None.
    assert store.get_l2_by_l1(tenant_id="tenant-a", l1_event_id="l1-1") is not None
    with pytest.raises(IsolationError):
        store.get_l2_by_l1(tenant_id="tenant-b", l1_event_id="l1-1")


# --------------------------------------------------------------------------- #
# Memory & relationship level
# --------------------------------------------------------------------------- #
def test_memory_query_is_tenant_scoped() -> None:
    store = _mk("life-1", tenant_id="tenant-a")
    store.memories.append(
        MemoryRecord(
            tenant_id="tenant-a",
            memory_id="m1",
            life_id="life-1",
            type=MemoryType.SEMANTIC,
            content="cat named Mimi",
            valid_from=_now(),
            transaction_from=_now(),
            confidence=0.9,
            importance=3,
        )
    )

    assert len(store.query_memories(tenant_id="tenant-a", life_id="life-1")) == 1
    with pytest.raises(IsolationError):
        store.query_memories(tenant_id="tenant-b", life_id="life-1")


def test_relationship_is_tenant_scoped() -> None:
    store = _mk("life-1", tenant_id="tenant-a")
    store._relationships[("tenant-a", "life-1", "subject-1")] = RelationshipState(
        tenant_id="tenant-a",
        life_id="life-1",
        subject_id="subject-1",
        familiarity=0.5,
        trust=0.5,
        attachment=0.5,
        updated_at=_now(),
    )

    got = store.get_relationship(
        tenant_id="tenant-a", life_id="life-1", subject_id="subject-1"
    )
    assert got is not None and got.familiarity == 0.5
    with pytest.raises(IsolationError):
        store.get_relationship(
            tenant_id="tenant-b", life_id="life-1", subject_id="subject-1"
        )


# --------------------------------------------------------------------------- #
# Default-tenant compatibility (the guarantee that keeps P0 green)
# --------------------------------------------------------------------------- #
def test_default_tenant_is_used_when_omitted() -> None:
    store = _store()
    inst = store.create_instance(
        life_id="legacy",
        personality_seed="s",
        born_at=_now(),
        schema_version="v1",
    )
    assert inst.tenant_id == "default"
    assert store.get_instance(tenant_id="default", life_id="legacy") is not None


def test_context_predicates_match_store_signature() -> None:
    ctx = RequestContext(tenant_id="tenant-a", life_id="life-1")
    preds = ctx.as_predicates()
    store = _mk("life-1", tenant_id="tenant-a")
    # The predicate fragment is directly usable as keyword arguments.
    assert store.get_instance(**preds) is not None
