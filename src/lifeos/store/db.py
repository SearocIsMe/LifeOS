"""PostgreSQL persistence for the Phase 0 pipeline (pytest -m db tier).

Semantics mirror the in-memory store: L2 effects + intent + decision + outbox
rows commit in ONE transaction; the three event tables are insert-only from
the application path (UPDATE/DELETE revoked from the app role in migration
0001). ``rehydrate`` loads one life's rows back into an InMemoryStore so the
same replay/isolation assertions run against persisted data.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from lifeos.entities import (
    BehaviorIntent,
    DomainEvent,
    EmbeddingOutbox,
    InterpretedEvent,
    LifeInstance,
    MemoryRecord,
    PolicyDecision,
    RawEvent,
    RelationshipState,
)
from lifeos.store.memory_store import Effects, InMemoryStore
from lifeos.store.tables import metadata, tables

# Cluster-internal Service DNS (ADR-0004 / HANDOVER §5). The real password lives
# ONLY in the K8s Secret `lifeos-postgres` (key DATABASE_URL) and is injected at
# runtime - never commit credentials. Host-side dev: `kubectl port-forward` +
# exported DATABASE_URL (see scripts/gate0_check.sh --with-db).
DEFAULT_DATABASE_URL = "postgresql+psycopg://lifeos:CHANGE_ME@postgres.lifeos-dev.svc.cluster.local:5432/lifeos"


def get_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)


def get_engine(url: str | None = None) -> Engine:
    return create_engine(url or get_url(), future=True)


def ensure_schema(engine: Engine) -> None:
    """Test/dev bootstrap (production path is `alembic upgrade head`)."""
    with engine.begin() as conn:
        if engine.dialect.name == "postgresql":
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
    metadata.create_all(engine)


def wait_for_db(engine: Engine, *, timeout_s: int = 30) -> bool:
    import time

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception:
            time.sleep(1.0)
    return False


def persist_life_instance(engine: Engine, inst: LifeInstance) -> None:
    t = tables["life_instances"]
    with engine.begin() as conn:
        conn.execute(
            t.insert().values(
                life_id=inst.life_id,
                born_at=inst.born_at,
                personality_seed=inst.personality_seed,
                schema_version=inst.schema_version,
                active_provider=inst.active_provider,
                status=inst.status.value,
            )
        )


def persist_pipeline_transaction(
    engine: Engine,
    *,
    raw: RawEvent,
    l1: InterpretedEvent,
    l2: DomainEvent,
    effects: Effects,
    intents: list[BehaviorIntent],
    decisions: list[PolicyDecision],
) -> None:
    """One DB transaction = one L2 and all of its effects (architecture §7)."""
    with Session(engine) as session, session.begin():
        session.execute(
            tables["raw_events"].insert().values(**_raw_values(raw, ingested_at=None))
        )
        session.execute(
            tables["interpreted_events"].insert().values(**_l1_values(l1))
        )
        session.execute(
            tables["domain_events"].insert().values(**_l2_values(l2))
        )
        for (life_id, state_key), value in effects.state_updates.items():
            upsert_life_state(session, life_id, state_key, value, l2.committed_at)
        for m in effects.memory_updates:
            session.execute(
                tables["memory_records"]
                .update()
                .where(tables["memory_records"].c.memory_id == m.memory_id)
                .values(
                    valid_to=m.valid_to,
                    transaction_to=m.transaction_to,
                    conflict_state=m.conflict_state.value,
                )
            )
        for m in effects.memory_inserts:
            session.execute(
                tables["memory_records"].insert().values(**_memory_values(m))
            )
        for r in effects.relationship_upserts:
            upsert_relationship(session, r)
        for intent in intents:
            session.execute(
                tables["behavior_intents"].insert().values(**_intent_values(intent))
            )
        for decision in decisions:
            session.execute(
                tables["policy_decisions"].insert().values(**_decision_values(decision))
            )
        for o in effects.outbox_rows:
            session.execute(tables["embedding_outbox"].insert().values(**_outbox_values(o)))


def _raw_values(raw: RawEvent, *, ingested_at: datetime | None) -> dict[str, Any]:
    return {
        "event_id": raw.event_id,
        "life_id": raw.life_id,
        "source": raw.source.value,
        "modality": raw.modality,
        "payload": raw.payload,
        "occurred_at": raw.occurred_at,
    }


def _l1_values(l1: InterpretedEvent) -> dict[str, Any]:
    return {
        "event_id": l1.event_id,
        "life_id": l1.life_id,
        "raw_event_id": l1.raw_event_id,
        "output_json": l1.output_json,
        "interpreter_type": l1.interpreter_type.value,
        "model_provider": l1.model_provider,
        "model_name": l1.model_name,
        "model_version": l1.model_version,
        "prompt_template_id": l1.prompt_template_id,
        "prompt_hash": l1.prompt_hash,
        "input_hash": l1.input_hash,
        "sampling_params": l1.sampling_params,
        "extractor_version": l1.extractor_version,
        "interpreted_at": l1.interpreted_at,
    }


def _l2_values(l2: DomainEvent) -> dict[str, Any]:
    return {
        "event_id": l2.event_id,
        "life_id": l2.life_id,
        "l1_event_id": l2.l1_event_id,
        "event_type": l2.event_type,
        "payload": l2.payload,
        "schema_version": l2.schema_version,
        "policy_version": l2.policy_version,
        "rules_version": l2.rules_version,
        "committed_at": l2.committed_at,
        "ingested_at": datetime.now(timezone.utc),  # non-semantic wall clock
    }


def _memory_values(m: MemoryRecord) -> dict[str, Any]:
    return {
        "memory_id": m.memory_id,
        "life_id": m.life_id,
        "subject_id": m.subject_id,
        "type": m.type.value,
        "content": m.content,
        "slot_key": m.slot_key,
        "valid_from": m.valid_from,
        "valid_to": m.valid_to,
        "transaction_from": m.transaction_from,
        "transaction_to": m.transaction_to,
        "confidence": m.confidence,
        "importance": m.importance,
        "emotional_weight": m.emotional_weight,
        "privacy_level": m.privacy_level.value,
        "source_event_ids": m.source_event_ids,
        "conflict_state": m.conflict_state.value,
        "version": m.version,
    }


def _intent_values(i: BehaviorIntent) -> dict[str, Any]:
    return {
        "intent_id": i.intent_id,
        "life_id": i.life_id,
        "intent_type": i.intent_type,
        "modality": i.modality.value,
        "utility_score": i.utility_score,
        "reason": i.reason,
        "preconditions": i.preconditions,
        "status": i.status.value,
        "created_at": i.created_at,
    }


def _decision_values(d: PolicyDecision) -> dict[str, Any]:
    return {
        "decision_id": d.decision_id,
        "intent_id": d.intent_id,
        "life_id": d.life_id,
        "rules_hit": d.rules_hit,
        "result": d.result.value,
        "reason": d.reason,
        "overridden_by": d.overridden_by,
        "decided_at": d.decided_at,
    }


def _outbox_values(o: EmbeddingOutbox) -> dict[str, Any]:
    return {
        "outbox_id": o.outbox_id,
        "life_id": o.life_id,
        "memory_id": o.memory_id,
        "embedding_model_version": o.embedding_model_version,
        "status": o.status.value,
        "retry_count": o.retry_count,
        "created_at": o.created_at,
        "embedded_at": o.embedded_at,
    }


def upsert_life_state(
    session: Session, life_id: str, state_key: str, value: float, at: datetime
) -> None:
    t = tables["life_states"]
    row = session.execute(
        t.select().where(t.c.life_id == life_id).where(t.c.state_key == state_key)
    ).first()
    if row:
        session.execute(
            t.update()
            .where(t.c.life_id == life_id)
            .where(t.c.state_key == state_key)
            .values(value_at_last_update=value, last_updated_at=at)
        )
    else:
        session.execute(
            t.insert().values(
                life_id=life_id,
                state_key=state_key,
                value_at_last_update=value,
                last_updated_at=at,
                kernel_version="phase0",
            )
        )


def upsert_relationship(session: Session, r: RelationshipState) -> None:
    t = tables["relationship_states"]
    row = session.execute(
        t.select()
        .where(t.c.life_id == r.life_id)
        .where(t.c.subject_id == r.subject_id)
    ).first()
    values = {
        "familiarity": r.familiarity,
        "trust": r.trust,
        "attachment": r.attachment,
        "updated_at": r.updated_at,
        "version": r.version,
    }
    if row:
        session.execute(
            t.update()
            .where(t.c.life_id == r.life_id)
            .where(t.c.subject_id == r.subject_id)
            .values(**values)
        )
    else:
        session.execute(
            t.insert().values(life_id=r.life_id, subject_id=r.subject_id, **values)
        )


def rehydrate(engine: Engine, store: InMemoryStore, *, life_id: str) -> None:
    """Load one life's persisted rows back into an InMemoryStore (replay tier B)."""
    with engine.connect() as conn:
        inst = conn.execute(
            tables["life_instances"].select().where(
                tables["life_instances"].c.life_id == life_id
            )
        ).first()
        if inst is None:
            raise ValueError(f"life not found in DB: {life_id}")
        store.create_instance(
            life_id=inst.life_id,
            personality_seed=inst.personality_seed,
            born_at=inst.born_at,
            schema_version=inst.schema_version,
        )
        for row in conn.execute(
            tables["raw_events"].select().where(tables["raw_events"].c.life_id == life_id)
        ):
            store.raw_events.append(
                RawEvent(
                    event_id=row.event_id,
                    life_id=row.life_id,
                    source=row.source,
                    modality=row.modality,
                    payload=row.payload,
                    occurred_at=row.occurred_at,
                )
            )
            store._raw_by_id[row.event_id] = store.raw_events[-1]
        for row in conn.execute(
            tables["interpreted_events"]
            .select()
            .where(tables["interpreted_events"].c.life_id == life_id)
        ):
            l1 = InterpretedEvent(
                event_id=row.event_id,
                life_id=row.life_id,
                raw_event_id=row.raw_event_id,
                output_json=row.output_json,
                interpreter_type=row.interpreter_type,
                model_provider=row.model_provider,
                model_name=row.model_name,
                model_version=row.model_version,
                prompt_template_id=row.prompt_template_id,
                prompt_hash=row.prompt_hash,
                input_hash=row.input_hash,
                sampling_params=row.sampling_params,
                extractor_version=row.extractor_version,
                interpreted_at=row.interpreted_at,
            )
            store.l1_events.append(l1)
            store._l1_by_id[l1.event_id] = l1
            store._l1_order.setdefault(l1.life_id, []).append(l1.event_id)
        for row in conn.execute(
            tables["domain_events"].select().where(tables["domain_events"].c.life_id == life_id)
        ):
            l2 = DomainEvent(
                event_id=row.event_id,
                life_id=row.life_id,
                l1_event_id=row.l1_event_id,
                event_type=row.event_type,
                payload=row.payload,
                schema_version=row.schema_version,
                policy_version=row.policy_version,
                rules_version=row.rules_version,
                committed_at=row.committed_at,
                ingested_at=row.ingested_at,
            )
            store.l2_events.append(l2)
            store._l2_by_l1[l2.l1_event_id] = l2
        for row in conn.execute(
            tables["memory_records"].select().where(
                tables["memory_records"].c.life_id == life_id
            )
        ):
            store.memories.append(
                MemoryRecord(
                    memory_id=row.memory_id,
                    life_id=row.life_id,
                    subject_id=row.subject_id,
                    type=row.type,
                    content=row.content,
                    slot_key=row.slot_key,
                    valid_from=row.valid_from,
                    valid_to=row.valid_to,
                    transaction_from=row.transaction_from,
                    transaction_to=row.transaction_to,
                    confidence=row.confidence,
                    importance=row.importance,
                    emotional_weight=row.emotional_weight,
                    privacy_level=row.privacy_level,
                    source_event_ids=row.source_event_ids,
                    conflict_state=row.conflict_state,
                    version=row.version,
                )
            )
