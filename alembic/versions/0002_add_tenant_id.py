"""0002 add tenant_id to all 15 entities (Idensona v0.9.2, decision 1A).

Why this migration exists separately from 0001:

- 0001 builds tables from ``lifeos.store.tables.metadata``. Fresh databases
  therefore already get ``tenant_id`` from the current metadata and do not need
  this revision's work.
- Databases created *before* 2026-11-27 do not. This revision backfills them.

Design choices (deliberate, recorded):

1. ``server_default='default'`` + ``nullable=False``: existing rows are filled by
   the default without a table rewrite, and the column can never be NULL
   (a NULL tenant would silently widen a predicate - unacceptable for TL-1).
2. Indexes lead with ``tenant_id``. The old ``ix_<table>_life_id`` index is
   dropped because every query now filters tenant first; keeping both would
   double write cost for no read benefit.
3. ``downgrade`` drops the column and restores the single-column index. This is
   destructive by nature (tenant attribution is lost); it exists so that a bad
   deploy can be rolled back *before* CH-A carries real tenants.

Honest scope: this migration has been validated against the SQLAlchemy metadata
(path exercised by ``tests/test_schema_sync.py`` and the in-memory store), but
**the PostgreSQL branch has not been executed against a live cluster in this
workspace** (no DATABASE_URL here). Gate: run it once against a scratch PG before
the first cloud deploy; see ``docs`` note in the P1 plan.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0002_add_tenant_id"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None

#: Tables that received tenant_id. Mirrors ``TABLE_FOR_ENTITY`` in
#: ``lifeos.store.tables``; the schema-sync test fails if a new entity is added
#: to the models but forgotten here.
TENANT_TABLES = (
    "life_instances",
    "personality_contracts",
    "raw_events",
    "interpreted_events",
    "domain_events",
    "life_states",
    "memory_records",
    "relationship_states",
    "behavior_intents",
    "policy_decisions",
    "model_invocations",
    "evaluation_runs",
    "consent_records",
    "gold_set_registry",
    "embedding_outbox",
)

#: Tables that previously carried ``ix_<name>_life_id``.
PREVIOUSLY_LIFE_INDEXED = tuple(t for t in TENANT_TABLES if t != "life_instances")


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for table in TENANT_TABLES:
        existing_cols = {c["name"] for c in inspector.get_columns(table)}

        # Fresh DBs built by 0001 from current metadata already have the column.
        if "tenant_id" not in existing_cols:
            op.add_column(
                table,
                sa.Column(
                    "tenant_id",
                    sa.String(length=64),
                    nullable=False,
                    server_default="default",
                ),
            )

        existing_indexes = {i["name"] for i in inspector.get_indexes(table)}

        # Drop the superseded single-column index if present.
        old_index = f"ix_{table}_life_id"
        if old_index in existing_indexes:
            op.drop_index(old_index, table_name=table)

        # Create the tenant-leading index the current metadata declares.
        if table == "life_instances":
            new_index = f"ix_{table}_tenant"
            cols = ["tenant_id"]
        else:
            new_index = f"ix_{table}_tenant_life"
            cols = ["tenant_id", "life_id"]

        if new_index not in existing_indexes:
            op.create_index(new_index, table, cols, unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for table in TENANT_TABLES:
        existing_indexes = {i["name"] for i in inspector.get_indexes(table)}

        for candidate in (f"ix_{table}_tenant_life", f"ix_{table}_tenant"):
            if candidate in existing_indexes:
                op.drop_index(candidate, table_name=table)

        if table in PREVIOUSLY_LIFE_INDEXED:
            old_index = f"ix_{table}_life_id"
            if old_index not in existing_indexes:
                op.create_index(old_index, table, ["life_id"], unique=False)

        existing_cols = {c["name"] for c in inspector.get_columns(table)}
        if "tenant_id" in existing_cols:
            op.drop_column(table, "tenant_id")
