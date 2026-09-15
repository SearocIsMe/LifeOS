"""LifeOS Phase 0 data contract: 15 entities (12 core + 3 support).

Single authoritative definition of entity shapes (architecture v0.9.1 §4).
Every entity carries ``life_id`` - the multi-instance isolation predicate
(architecture §4 invariants). All models are strict (``extra="forbid"``):
unknown fields are rejected, which is the first lock against LLM outputs
carrying payload into authoritative tables (design doc 01 §7).

Provisional naming (design doc 01 D3-2, honest annotation): the spec says
``privacy_level`` has four tiers but does not name them; we use
public/normal/personal/sensitive until the spec supersedes.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# --------------------------------------------------------------------------- #
# Enumerations
# --------------------------------------------------------------------------- #


class EventSource(str, Enum):
    """RawEvent.source - sim events are distinguishable from human events (arch §4)."""

    USER = "user"
    CARRIER = "carrier"
    SYSTEM = "system"
    SIM = "sim"


class InterpreterType(str, Enum):
    LLM = "llm"
    CLASSIFIER = "classifier"
    RULE = "rule"


class PrivacyLevel(str, Enum):
    """Four tiers per spec §9.3; names provisional (design doc D3-2)."""

    PUBLIC = "public"
    NORMAL = "normal"
    PERSONAL = "personal"
    SENSITIVE = "sensitive"


class MemoryType(str, Enum):
    EPISODIC = "episodic"
    SEMANTIC = "semantic"


class ConflictState(str, Enum):
    """MemoryRecord conflict state machine (architecture §5.2)."""

    CURRENT = "current"
    SUPERSEDED = "superseded"
    AMBIGUOUS = "ambiguous"
    COEXISTS = "coexists"


class BehaviorStatus(str, Enum):
    """BehaviorIntent.status transitions (architecture §5.4)."""

    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"  # requires rendering - Phase 1


class IntentModality(str, Enum):
    """BehaviorIntent.modality - hint only, NO motor parameters (arch §2 boundary)."""

    VERBAL = "verbal"
    EXPRESSIVE = "expressive"
    ATTENTIONAL = "attentional"


class PolicyResult(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"


class GoldSetKind(str, Enum):
    """GoldSetRegistry.kind - human and synthetic materials registered separately (spec §4.6)."""

    CORE_FACTS = "core_facts"
    MEMORY_EXTRACTION = "memory_extraction"
    PERSONA_PROBE = "persona_probe"
    BEHAVIOR_SCENARIO = "behavior_scenario"
    HUMAN_GOLD = "human_gold"
    SYNTHETIC_LABELED = "synthetic_labeled"


class OutboxStatus(str, Enum):
    """EmbeddingOutbox.status - only updatable fields are status/retry_count/embedded_at."""

    PENDING = "pending"
    DONE = "done"
    FAILED = "failed"


class LifeStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"


# --------------------------------------------------------------------------- #
# Contract base
# --------------------------------------------------------------------------- #


class _Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


# --------------------------------------------------------------------------- #
# 12 core entities
# --------------------------------------------------------------------------- #


class LifeInstance(_Contract):
    """Root entity of a life instance (arch §4). active_provider stays 'none' in Phase 0."""

    life_id: str = Field(min_length=1)
    born_at: datetime
    personality_seed: str
    schema_version: str
    active_provider: str = "none"  # dual-provider binding arrives in Phase 1
    status: LifeStatus = LifeStatus.ACTIVE


class PersonalityContract(_Contract):
    """Frozen after generation; changes go through ADR (arch §4).

    Phase 0 derives placeholder parameters deterministically from the seed;
    the real derivation lands with Life Kernel v0 (Phase 1 S1).
    """

    contract_id: str
    life_id: str
    big_five_params: dict[str, float]
    expression_style: dict[str, Any]
    frozen_at: datetime


class RawEvent(_Contract):
    """L0 raw event - immutable (append-only)."""

    event_id: str
    life_id: str
    source: EventSource
    modality: str = "text"  # carrier modalities not finalized in Phase 0
    payload: dict[str, Any]
    occurred_at: datetime  # injected by caller; system never mints semantic time


class InterpretedEvent(_Contract):
    """L1 interpreted event - immutable; carries the FULL provenance set (arch §3.2)."""

    event_id: str
    life_id: str
    raw_event_id: str
    output_json: dict[str, Any]
    # --- provenance (architecture §3.2, all required, "缺一不入库") ---
    interpreter_type: InterpreterType
    model_provider: str | None = None  # required when interpreter_type == llm
    model_name: str | None = None
    model_version: str | None = None
    prompt_template_id: str | None = None
    prompt_hash: str | None = None
    input_hash: str
    sampling_params: dict[str, Any] = Field(default_factory=dict)
    extractor_version: str
    interpreted_at: datetime


class DomainEvent(_Contract):
    """L2 committed domain event - immutable; the ONLY writer of authoritative state."""

    event_id: str
    life_id: str
    l1_event_id: str
    event_type: str
    payload: dict[str, Any]
    schema_version: str
    policy_version: str
    rules_version: str = ""
    committed_at: datetime  # semantic time == L0.occurred_at (design doc D4-2)
    ingested_at: datetime | None = None  # wall clock, NON-semantic, excluded from hashes


class LifeState(_Contract):
    """One row per (life_id, state_key). Lazy decay fields present but inert in Phase 0."""

    life_id: str
    state_key: str
    value_at_last_update: float = Field(ge=0.0, le=1.0)
    last_updated_at: datetime
    decay_function: str = "none"  # exponential decay materialization is Phase 1
    decay_parameter: float = 0.0
    baseline: float = 0.5
    kernel_version: str


class MemoryRecord(_Contract):
    """Bitemporal memory; conflict resolution never deletes history (arch §4 invariants).

    subject_id is nullable and is the dependency for scenario-2 memory isolation.
    NOTE: the ``embedding`` vector column is intentionally deferred to Phase 1 (D3-1).
    """

    memory_id: str
    life_id: str
    subject_id: str | None = None
    type: MemoryType
    content: str
    slot_key: str | None = None
    valid_from: datetime
    valid_to: datetime | None = None
    transaction_from: datetime
    transaction_to: datetime | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    importance: int = Field(ge=1, le=5)
    emotional_weight: float = 0.0
    privacy_level: PrivacyLevel = PrivacyLevel.NORMAL
    source_event_ids: list[str] = Field(default_factory=list)
    conflict_state: ConflictState = ConflictState.CURRENT
    version: int = 1


class RelationshipState(_Contract):
    """One row per relationship instance, replay-recomputable (arch §5.3)."""

    life_id: str
    subject_id: str
    familiarity: float = Field(default=0.2, ge=0.0, le=1.0)
    trust: float = Field(default=0.2, ge=0.0, le=1.0)
    attachment: float = Field(default=0.2, ge=0.0, le=1.0)
    updated_at: datetime
    version: int = 1


class BehaviorIntent(_Contract):
    """Proposed behavior; only Policy transitions status (design doc 01 §6.2)."""

    intent_id: str
    life_id: str
    intent_type: str
    modality: IntentModality
    utility_score: float = 0.0
    reason: dict[str, Any] = Field(default_factory=dict)  # evidence-chain JSON
    preconditions: dict[str, Any] = Field(default_factory=dict)
    status: BehaviorStatus = BehaviorStatus.PROPOSED
    created_at: datetime


class PolicyDecision(_Contract):
    """Approval record; rejection leaves ZERO state side effects (Gate 0 #4)."""

    decision_id: str
    intent_id: str
    life_id: str
    rules_hit: list[str] = Field(default_factory=list)
    result: PolicyResult
    reason: dict[str, Any] = Field(default_factory=dict)
    overridden_by: str | None = None  # manual override channel - audited
    decided_at: datetime


class ModelInvocation(_Contract):
    """Per-call cost & version record (arch §5.6). Phase 0 produces no rows (no LLM)."""

    invocation_id: str
    life_id: str
    provider: str
    model: str
    model_version: str
    tokens: int = 0
    latency_ms: int = 0
    cost_usd: float = 0.0
    purpose: str
    called_at: datetime


class EvaluationRun(_Contract):
    """Evaluation record (arch §5.9). Phase 0 produces no rows (no metrics yet)."""

    run_id: str
    life_id: str
    gold_set_id: str
    gold_set_version: str
    model_version: str
    metrics_json: dict[str, Any]
    ci_pass: bool
    ran_at: datetime


# --------------------------------------------------------------------------- #
# 3 support entities
# --------------------------------------------------------------------------- #


class ConsentRecord(_Contract):
    """Append-only informed-consent trail; jurisdiction/locale for multi-jurisdiction (v0.9.1).

    Activated for real users in Phase 3; Phase 0 validates schema + isolation only.
    """

    consent_id: str
    external_user_id: str
    life_id: str
    consent_type: str
    scope: dict[str, Any]
    jurisdiction: str  # e.g. CN / SG / HK / MO (spec §9.4)
    locale: str  # e.g. zh-CN
    document_version: str
    granted_at: datetime
    revoked_at: datetime | None = None


class GoldSetRegistry(_Contract):
    """Evaluation-material registry; human vs. synthetic reported separately (spec §4.6)."""

    gold_set_id: str
    kind: GoldSetKind
    version: str
    item_count: int = Field(ge=0)
    content_hash: str
    frozen_at: datetime
    notes: str = ""


class EmbeddingOutbox(_Contract):
    """Async embedding outbox; row created in the L2 transaction, worker is Phase 1."""

    outbox_id: str
    life_id: str
    memory_id: str
    embedding_model_version: str  # frozen per spec §9.5; empty until Phase 1
    status: OutboxStatus = OutboxStatus.PENDING
    retry_count: int = 0
    created_at: datetime
    embedded_at: datetime | None = None


# --------------------------------------------------------------------------- #
# Registry used by tests / CLI (AC-03, schema-sync test)
# --------------------------------------------------------------------------- #

ENTITY_MODELS: dict[str, type[_Contract]] = {
    "LifeInstance": LifeInstance,
    "PersonalityContract": PersonalityContract,
    "RawEvent": RawEvent,
    "InterpretedEvent": InterpretedEvent,
    "DomainEvent": DomainEvent,
    "LifeState": LifeState,
    "MemoryRecord": MemoryRecord,
    "RelationshipState": RelationshipState,
    "BehaviorIntent": BehaviorIntent,
    "PolicyDecision": PolicyDecision,
    "ModelInvocation": ModelInvocation,
    "EvaluationRun": EvaluationRun,
    "ConsentRecord": ConsentRecord,
    "GoldSetRegistry": GoldSetRegistry,
    "EmbeddingOutbox": EmbeddingOutbox,
}

CORE_ENTITIES = [
    "LifeInstance",
    "PersonalityContract",
    "RawEvent",
    "InterpretedEvent",
    "DomainEvent",
    "LifeState",
    "MemoryRecord",
    "RelationshipState",
    "BehaviorIntent",
    "PolicyDecision",
    "ModelInvocation",
    "EvaluationRun",
]
SUPPORT_ENTITIES = ["ConsentRecord", "GoldSetRegistry", "EmbeddingOutbox"]
