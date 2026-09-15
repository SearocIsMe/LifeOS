"""0001 initial schema - LifeOS Phase 0 (15 entities).

Pragmatic note (recorded in execution plan §6 diff register, item 3):
this single Phase-0 migration builds tables from the SQLAlchemy metadata
(``lifeos.store.tables``) instead of hand-written per-column ops, because the
schema has exactly one revision here and a sync test (tests/test_schema_sync.py)
guards metadata vs. Pydantic drift. From Phase 1 onward, schema changes must use
autogenerate diffs (``alembic revision --autogenerate``), one ADR per change.

Deferred on purpose (design doc D3-1): ``MemoryRecord.embedding`` vector column
and its index - the embedding model is chosen in Phase 1 (spec §9.5 version
freeze); a placeholder dimension now would force a full rebuild later.
"""

from sqlalchemy import text

from alembic import op

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None

# Append-only tables (architecture v0.9.1 §4 invariants).
APPEND_ONLY_TABLES = ("raw_events", "interpreted_events", "domain_events")


def upgrade() -> None:
    # pgvector ships in the image; explicit create keeps the migration self-contained.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    from lifeos.store.tables import metadata

    metadata.create_all(bind=op.get_bind())

    # Least-privilege application account: INSERT/SELECT only; the three
    # event tables must not be UPDATE/DELETE-able by the app path (AC-02).
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    bind.execute(
        text(
            """
            DO $$ BEGIN
              IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'lifeos_app') THEN
                CREATE ROLE lifeos_app LOGIN PASSWORD 'lifeos_app';
              END IF;
            END $$;
            GRANT USAGE ON SCHEMA public TO lifeos_app;
            GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA public TO lifeos_app;
            """
        )
    )
    for table in APPEND_ONLY_TABLES:
        bind.execute(text(f"REVOKE UPDATE, DELETE ON TABLE {table} FROM lifeos_app;"))


def downgrade() -> None:
    from lifeos.store.tables import metadata

    metadata.drop_all(bind=op.get_bind())
