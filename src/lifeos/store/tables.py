"""SQLAlchemy definitions of the 15 entities (architecture v0.9.1 §4).

Column names deliberately mirror the Pydantic field names in
``lifeos.entities`` one-to-one; ``tests/test_schema_sync.py`` asserts the two
contract surfaces never drift (design doc 01 D2-1).

Deferred on purpose (D3-1): no ``vector`` column - the embedding model is
selected in Phase 1 (spec §9.5); a placeholder dimension would force a full
table rebuild later. ``CREATE EXTENSION vector`` still runs in migration 0001
so the extension presence is a settled fact from day one.
"""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
)
from sqlalchemy import JSON as SAJSON

metadata = MetaData()

_TABLE_ARGS: dict[str, list[Column]] = {
    "life_instances": [
        Column("life_id", String(64), primary_key=True),
        Column("born_at", DateTime(timezone=True), nullable=False),
        Column("personality_seed", String(128), nullable=False),
        Column("schema_version", String(32), nullable=False),
        Column("active_provider", String(64), nullable=False, default="none"),
        Column("status", String(16), nullable=False, default="active"),
    ],
    "personality_contracts": [
        Column("contract_id", String(80), primary_key=True),
        Column("life_id", String(64), nullable=False),
        Column("big_five_params", SAJSON, nullable=False),
        Column("expression_style", SAJSON, nullable=False),
        Column("frozen_at", DateTime(timezone=True), nullable=False),
    ],
    "raw_events": [
        Column("event_id", String(80), primary_key=True),
        Column("life_id", String(64), nullable=False),
        Column("source", String(16), nullable=False),
        Column("modality", String(32), nullable=False, default="text"),
        Column("payload", SAJSON, nullable=False),
        Column("occurred_at", DateTime(timezone=True), nullable=False),
    ],
    "interpreted_events": [
        Column("event_id", String(80), primary_key=True),
        Column("life_id", String(64), nullable=False),
        Column("raw_event_id", String(80), nullable=False),
        Column("output_json", SAJSON, nullable=False),
        Column("interpreter_type", String(16), nullable=False),
        Column("model_provider", String(64)),
        Column("model_name", String(128)),
        Column("model_version", String(64)),
        Column("prompt_template_id", String(128)),
        Column("prompt_hash", String(64)),
        Column("input_hash", String(64), nullable=False),
        Column("sampling_params", SAJSON, nullable=False, default=dict),
        Column("extractor_version", String(64), nullable=False),
        Column("interpreted_at", DateTime(timezone=True), nullable=False),
    ],
    "domain_events": [
        Column("event_id", String(80), primary_key=True),
        Column("life_id", String(64), nullable=False),
        Column("l1_event_id", String(80), nullable=False),
        Column("event_type", String(32), nullable=False),
        Column("payload", SAJSON, nullable=False),
        Column("schema_version", String(32), nullable=False),
        Column("policy_version", String(32), nullable=False),
        Column("rules_version", String(32), nullable=False, default=""),
        Column("committed_at", DateTime(timezone=True), nullable=False),
        Column("ingested_at", DateTime(timezone=True)),  # wall clock, NON-semantic
    ],
    "life_states": [
        Column("life_id", String(64), primary_key=True),
        Column("state_key", String(32), primary_key=True),
        Column("value_at_last_update", Float, nullable=False),
        Column("last_updated_at", DateTime(timezone=True), nullable=False),
        Column("decay_function", String(32), nullable=False, default="none"),
        Column("decay_parameter", Float, nullable=False, default=0.0),
        Column("baseline", Float, nullable=False, default=0.5),
        Column("kernel_version", String(32), nullable=False, default=""),
    ],
    "memory_records": [
        Column("memory_id", String(80), primary_key=True),
        Column("life_id", String(64), nullable=False),
        Column("subject_id", String(64)),
        Column("type", String(16), nullable=False),
        Column("content", Text, nullable=False),
        Column("slot_key", String(128)),
        Column("valid_from", DateTime(timezone=True), nullable=False),
        Column("valid_to", DateTime(timezone=True)),
        Column("transaction_from", DateTime(timezone=True), nullable=False),
        Column("transaction_to", DateTime(timezone=True)),
        Column("confidence", Float, nullable=False),
        Column("importance", Integer, nullable=False),
        Column("emotional_weight", Float, nullable=False, default=0.0),
        Column("privacy_level", String(16), nullable=False, default="normal"),
        Column("source_event_ids", SAJSON, nullable=False, default=list),
        Column("conflict_state", String(16), nullable=False, default="current"),
        Column("version", Integer, nullable=False, default=1),
    ],
    "relationship_states": [
        Column("life_id", String(64), primary_key=True),
        Column("subject_id", String(64), primary_key=True),
        Column("familiarity", Float, nullable=False, default=0.2),
        Column("trust", Float, nullable=False, default=0.2),
        Column("attachment", Float, nullable=False, default=0.2),
        Column("updated_at", DateTime(timezone=True), nullable=False),
        Column("version", Integer, nullable=False, default=1),
    ],
    "behavior_intents": [
        Column("intent_id", String(80), primary_key=True),
        Column("life_id", String(64), nullable=False),
        Column("intent_type", String(64), nullable=False),
        Column("modality", String(16), nullable=False),
        Column("utility_score", Float, nullable=False, default=0.0),
        Column("reason", SAJSON, nullable=False, default=dict),
        Column("preconditions", SAJSON, nullable=False, default=dict),
        Column("status", String(16), nullable=False, default="proposed"),
        Column("created_at", DateTime(timezone=True), nullable=False),
    ],
    "policy_decisions": [
        Column("decision_id", String(80), primary_key=True),
        Column("intent_id", String(80), nullable=False),
        Column("life_id", String(64), nullable=False),
        Column("rules_hit", SAJSON, nullable=False, default=list),
        Column("result", String(16), nullable=False),
        Column("reason", SAJSON, nullable=False, default=dict),
        Column("overridden_by", String(64)),
        Column("decided_at", DateTime(timezone=True), nullable=False),
    ],
    "model_invocations": [
        Column("invocation_id", String(80), primary_key=True),
        Column("life_id", String(64), nullable=False),
        Column("provider", String(64), nullable=False),
        Column("model", String(128), nullable=False),
        Column("model_version", String(64), nullable=False),
        Column("tokens", Integer, nullable=False, default=0),
        Column("latency_ms", Integer, nullable=False, default=0),
        Column("cost_usd", Float, nullable=False, default=0.0),
        Column("purpose", String(64), nullable=False),
        Column("called_at", DateTime(timezone=True), nullable=False),
    ],
    "evaluation_runs": [
        Column("run_id", String(80), primary_key=True),
        Column("life_id", String(64), nullable=False),
        Column("gold_set_id", String(64), nullable=False),
        Column("gold_set_version", String(32), nullable=False),
        Column("model_version", String(64), nullable=False),
        Column("metrics_json", SAJSON, nullable=False),
        Column("ci_pass", Boolean, nullable=False),
        Column("ran_at", DateTime(timezone=True), nullable=False),
    ],
    "consent_records": [
        Column("consent_id", String(80), primary_key=True),
        Column("external_user_id", String(64), nullable=False),
        Column("life_id", String(64), nullable=False),
        Column("consent_type", String(64), nullable=False),
        Column("scope", SAJSON, nullable=False),
        Column("jurisdiction", String(16), nullable=False),
        Column("locale", String(16), nullable=False),
        Column("document_version", String(32), nullable=False),
        Column("granted_at", DateTime(timezone=True), nullable=False),
        Column("revoked_at", DateTime(timezone=True)),
    ],
    "gold_set_registry": [
        Column("gold_set_id", String(64), primary_key=True),
        Column("kind", String(32), nullable=False),
        Column("version", String(32), primary_key=True),
        Column("item_count", Integer, nullable=False),
        Column("content_hash", String(64), nullable=False),
        Column("frozen_at", DateTime(timezone=True), nullable=False),
        Column("notes", Text, nullable=False, default=""),
    ],
    "embedding_outbox": [
        Column("outbox_id", String(80), primary_key=True),
        Column("life_id", String(64), nullable=False),
        Column("memory_id", String(80), nullable=False),
        Column("embedding_model_version", String(64), nullable=False, default=""),
        Column("status", String(16), nullable=False, default="pending"),
        Column("retry_count", Integer, nullable=False, default=0),
        Column("created_at", DateTime(timezone=True), nullable=False),
        Column("embedded_at", DateTime(timezone=True)),
    ],
}

tables: dict[str, Table] = {}
for name, columns in _TABLE_ARGS.items():
    table = Table(name, metadata, *columns)
    # Multi-instance isolation: every table carries a life_id-leading index
    # (design doc 01 §8). gold_set_registry / life_instances are global.
    if "life_id" in table.c and name not in ("life_instances",):
        table.append_constraint(
            Index(f"ix_{name}_life_id", table.c.life_id)
        )
    tables[name] = metadata.tables[name]

# entity-class-name -> table-name mapping (used by the schema-sync test)
TABLE_FOR_ENTITY: dict[str, str] = {
    "LifeInstance": "life_instances",
    "PersonalityContract": "personality_contracts",
    "RawEvent": "raw_events",
    "InterpretedEvent": "interpreted_events",
    "DomainEvent": "domain_events",
    "LifeState": "life_states",
    "MemoryRecord": "memory_records",
    "RelationshipState": "relationship_states",
    "BehaviorIntent": "behavior_intents",
    "PolicyDecision": "policy_decisions",
    "ModelInvocation": "model_invocations",
    "EvaluationRun": "evaluation_runs",
    "ConsentRecord": "consent_records",
    "GoldSetRegistry": "gold_set_registry",
    "EmbeddingOutbox": "embedding_outbox",
}
