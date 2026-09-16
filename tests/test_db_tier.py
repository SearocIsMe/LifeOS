"""Tier-B acceptance (AC-02/AC-04/AC-05/AC-08 against PostgreSQL).

Requires ``DATABASE_URL`` pointing at the cluster postgres (ADR-0004): run
in-cluster (ai-stack pod) or on the host via ``kubectl port-forward``. Skipped
automatically when the DB is unreachable - the Gate 0 verdict marks the DB
tier INCOMPLETE in that case (never silently PASS).
"""

from __future__ import annotations

import pytest

from conftest import DB_AVAILABLE

pytestmark = [
    pytest.mark.db,
    pytest.mark.skipif(not DB_AVAILABLE, reason="PostgreSQL not reachable"),
]


def test_tables_and_append_only_privileges():
    from sqlalchemy import text

    from lifeos.store.db import get_engine
    from lifeos.store.tables import tables

    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public'")).fetchall()
        have = {r[0] for r in rows}
        assert set(tables) <= have, f"missing tables: {sorted(set(tables) - have)}"

        role = conn.execute(text("SELECT 1 FROM pg_roles WHERE rolname='lifeos_app'")).first()
        if role:  # created by alembic migration 0001 (AC-02)
            for t in ("raw_events", "interpreted_events", "domain_events"):
                granted = conn.execute(
                    text(f"SELECT has_table_privilege('lifeos_app', '{t}', 'UPDATE')")
                ).scalar()
                assert not granted, f"app role must not UPDATE {t}"


def test_persist_rehydrate_replay_isolation():
    import uuid

    from lifeos.cli import DEMO_EVENTS, _new_store_and_pipeline
    from lifeos.replay import replay
    from lifeos.store.db import (
        ensure_schema,
        get_engine,
        persist_life_instance,
        persist_pipeline_transaction,
        rehydrate,
    )

    engine = get_engine()
    ensure_schema(engine)

    # Unique per run: event tables are append-only, so tests never reuse ids.
    life_id = f"life-db-demo-{uuid.uuid4().hex[:8]}"
    store, pipeline = _new_store_and_pipeline(life_id=life_id)
    events = [{**e, "life_id": life_id} for e in DEMO_EVENTS]
    results = [pipeline.ingest(dict(e)) for e in events]

    persist_life_instance(engine, store.instances[life_id])
    for r in results:
        persist_pipeline_transaction(
            engine,
            raw=r.raw_event,
            l1=r.interpreted,
            l2=r.domain,
            effects=r.effects,
            intents=[r.intent] if r.intent else [],
            decisions=[r.decision] if r.decision else [],
        )

    # AC-05 on persisted data: rehydrate and replay the SAME commit function.
    loaded = type(store)()
    rehydrate(engine, loaded, life_id=life_id)
    report = replay(loaded, life_id=life_id)
    assert report.total == 5
    assert report.matched == report.total, report.to_dict()

    # AC-08 on persisted data: the other life sees nothing.
    other = f"{life_id}-other"
    loaded.create_instance(
        life_id=other,
        personality_seed="s2",
        born_at=results[0].raw_event.occurred_at,
        schema_version="0.1.0",
    )
    assert loaded.query_memories(life_id=other) == []
