"""In-memory authoritative store (Phase 0).

Mirrors the DB semantics needed by Gate 0: append-only event tables, atomic
effect application, mandatory ``life_id`` predicates, and write guards so that
authoritative state can only change through committed L2 effects.

Honest scope: this store exists for CI/replay/CLI (tier A). The PostgreSQL
store (``lifeos.store.db``) is the production shape; both are exercised by the
same acceptance assertions (design doc 01 §12 risk #3).
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable

from lifeos.entities import (
    DEFAULT_TENANT,
    BehaviorIntent,
    BehaviorStatus,
    ConflictState,
    DomainEvent,
    EmbeddingOutbox,
    EventSource,
    InterpretedEvent,
    LifeInstance,
    LifeStatus,
    LifeState,
    MemoryRecord,
    PolicyDecision,
    RawEvent,
    RelationshipState,
)


class IsolationError(ValueError):
    """Raised when a query/write cannot be scoped to a life instance."""


@dataclass
class Effects:
    """Staged authoritative-state changes of exactly one L2 (one transaction)."""

    state_updates: dict[tuple[str, str], float] = field(default_factory=dict)
    # Injected transaction time of the staging L2 (committed_at). Recorded for
    # every applied state key so later lazy-decay reads know their t0. States
    # staged without a state_time (direct test tooling) are treated as
    # never-materialized by decay reads.
    state_time: datetime | None = None
    memory_inserts: list[MemoryRecord] = field(default_factory=list)
    memory_updates: list[MemoryRecord] = field(default_factory=list)
    relationship_upserts: list[RelationshipState] = field(default_factory=list)
    outbox_rows: list[EmbeddingOutbox] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not (
            self.state_updates
            or self.memory_inserts
            or self.memory_updates
            or self.relationship_upserts
            or self.outbox_rows
        )


class InMemoryStore:
    """Authoritative in-memory store, keyed on (tenant_id, life_id) everywhere.

    Tenant scoping (2026-11-27, Idensona v0.9.2 decision 1A): the SAME
    ``life_id`` string may exist in two tenants (``life-1`` in tenant A and in
    tenant B are different lives). Every dict key therefore carries the tenant
    prefix, and every read takes ``tenant_id`` as a required-or-defaulted
    keyword. A read that names the wrong tenant raises ``IsolationError``
    instead of silently returning ``None`` - a silent ``None`` would let a
    caller proceed as if the instance were merely absent.

    ``tenant_id`` defaults to ``"default"`` so all pre-cloud call sites keep
    working unchanged (this is what preserves P0's test suite).
    """

    def __init__(self) -> None:
        # Key = (tenant_id, life_id)
        self.instances: dict[tuple[str, str], LifeInstance] = {}
        self.raw_events: list[RawEvent] = []
        self._raw_by_id: dict[str, RawEvent] = {}
        self.l1_events: list[InterpretedEvent] = []
        self._l1_by_id: dict[str, InterpretedEvent] = {}
        # Key = (tenant_id, life_id) -> ordered L1 ids
        self._l1_order: dict[tuple[str, str], list[str]] = {}
        self.l2_events: list[DomainEvent] = []
        self._l2_by_l1: dict[str, DomainEvent] = {}
        # Key = (tenant_id, life_id, state_key)
        self._states: dict[tuple[str, str, str], float] = {}
        self._state_times: dict[tuple[str, str, str], datetime] = {}
        self.memories: list[MemoryRecord] = []
        # Key = (tenant_id, life_id, subject_id)
        self._relationships: dict[tuple[str, str, str], RelationshipState] = {}
        self.intents: list[BehaviorIntent] = []
        self.decisions: list[PolicyDecision] = []
        self.outbox: list[EmbeddingOutbox] = []
        self.consent_records: list[Any] = []  # Phase 3 S1: append-only consent trail

    # ------------------------------------------------------------------ #
    # instance lifecycle
    # ------------------------------------------------------------------ #

    def create_instance(
        self,
        *,
        life_id: str,
        personality_seed: str,
        born_at: datetime,
        schema_version: str,
        tenant_id: str = DEFAULT_TENANT,
    ) -> LifeInstance:
        key = (tenant_id, life_id)
        if key in self.instances:
            raise ValueError(
                f"life instance already exists: tenant={tenant_id!r} life={life_id!r}"
            )
        inst = LifeInstance(
            tenant_id=tenant_id,
            life_id=life_id,
            born_at=born_at,
            personality_seed=personality_seed,
            schema_version=schema_version,
            status=LifeStatus.ACTIVE,
        )
        self.instances[key] = inst
        return inst

    def get_instance(
        self, *, life_id: str, tenant_id: str = DEFAULT_TENANT
    ) -> LifeInstance | None:
        """Tenant-scoped instance read (no exception when simply absent)."""
        return self.instances.get((tenant_id, life_id))

    def _require_life(self, life_id: str, tenant_id: str = DEFAULT_TENANT) -> None:
        if (tenant_id, life_id) not in self.instances:
            raise IsolationError(
                f"unknown life_id: {life_id!r} in tenant {tenant_id!r}"
            )

    # ------------------------------------------------------------------ #
    # event tables (append-only: insert methods only, no update/delete API)
    # ------------------------------------------------------------------ #

    def ingest_raw(
        self,
        *,
        life_id: str,
        source: EventSource,
        payload: dict[str, Any],
        occurred_at: datetime,
        modality: str = "text",
        tenant_id: str = DEFAULT_TENANT,
    ) -> RawEvent | None:
        """Normalize + dedupe an incoming L0 event. Returns None on duplicate."""
        self._require_life(life_id, tenant_id)
        from lifeos.events.protocol import derive_id

        event_id = derive_id(
            "L0",
            {
                # tenant is part of the hash: the same utterance arriving in two
                # tenants must not produce one shared event id (would collide in
                # the append-only tables' primary keys).
                "tenant_id": tenant_id,
                "life_id": life_id,
                "source": source.value,
                "modality": modality,
                "payload": payload,
                "occurred_at": occurred_at.isoformat(),
            },
        )
        if event_id in self._raw_by_id:
            return None  # idempotent re-ingest
        raw = RawEvent(
            tenant_id=tenant_id,
            event_id=event_id,
            life_id=life_id,
            source=source,
            modality=modality,
            payload=payload,
            occurred_at=occurred_at,
        )
        self.raw_events.append(raw)
        self._raw_by_id[event_id] = raw
        return raw

    def get_raw(self, event_id: str) -> RawEvent | None:
        return self._raw_by_id.get(event_id)

    def archive_l1(self, l1: InterpretedEvent) -> None:
        if l1.event_id in self._l1_by_id:
            raise ValueError(f"L1 already archived: {l1.event_id}")
        if self._raw_by_id.get(l1.raw_event_id) is None:
            raise ValueError(f"L1 references unknown raw event: {l1.raw_event_id}")
        raw = self._raw_by_id[l1.raw_event_id]
        if raw.tenant_id != l1.tenant_id:
            # Cross-tenant stitching would let a handler launder provenance.
            raise IsolationError(
                f"L1 tenant {l1.tenant_id!r} does not match raw event tenant "
                f"{raw.tenant_id!r}"
            )
        self.l1_events.append(l1)
        self._l1_by_id[l1.event_id] = l1
        self._l1_order.setdefault((l1.tenant_id, l1.life_id), []).append(l1.event_id)

    def archive_l2(self, l2: DomainEvent) -> None:
        l1 = self._l1_by_id.get(l2.l1_event_id)
        if l1 is None:
            raise ValueError(f"L2 references unknown L1 event: {l2.l1_event_id}")
        if l1.tenant_id != l2.tenant_id:
            raise IsolationError(
                f"L2 tenant {l2.tenant_id!r} does not match L1 tenant {l1.tenant_id!r}"
            )
        if l2.l1_event_id in self._l2_by_l1:
            raise ValueError(f"L2 already archived for L1: {l2.l1_event_id}")
        self.l2_events.append(l2)
        self._l2_by_l1[l2.l1_event_id] = l2

    def range_l1(
        self,
        *,
        life_id: str,
        from_seq: int = 0,
        to_seq: int | None = None,
        tenant_id: str = DEFAULT_TENANT,
    ) -> list[InterpretedEvent]:
        """L1 archive in ingestion order (replay order, architecture §3.3)."""
        self._require_life(life_id, tenant_id)
        ids = self._l1_order.get((tenant_id, life_id), [])[from_seq:to_seq]
        return [self._l1_by_id[i] for i in ids]

    def get_l2_by_l1(
        self, l1_event_id: str, *, tenant_id: str = DEFAULT_TENANT
    ) -> DomainEvent | None:
        l2 = self._l2_by_l1.get(l1_event_id)
        if l2 is not None and l2.tenant_id != tenant_id:
            raise IsolationError(
                f"L2 {l1_event_id!r} belongs to tenant {l2.tenant_id!r}, "
                f"not {tenant_id!r}"
            )
        return l2

    # ------------------------------------------------------------------ #
    # authoritative state reads (life_id is a REQUIRED keyword everywhere)
    # ------------------------------------------------------------------ #

    def get_state(
        self,
        *,
        life_id: str,
        state_key: str,
        default: float = 0.5,
        tenant_id: str = DEFAULT_TENANT,
    ) -> float:
        self._require_life(life_id, tenant_id)
        return self._states.get((tenant_id, life_id, state_key), default)

    def kernel_state_keys(self, *, tenant_id: str | None = None) -> list[str]:
        """Distinct materialized state keys (Studio/console read view).

        ``tenant_id=None`` means "all tenants" and exists solely for the
        operator view (CH-A usage rollups). Application code must pass it.
        """
        return sorted(
            {
                key
                for (t, _life, key) in self._states
                if tenant_id is None or t == tenant_id
            }
        )

    def get_state_time(
        self, *, life_id: str, state_key: str, tenant_id: str = DEFAULT_TENANT
    ) -> datetime | None:
        """Last-update instant of one kernel state (None = never materialized)."""
        self._require_life(life_id, tenant_id)
        return self._state_times.get((tenant_id, life_id, state_key))

    def query_memories(
        self,
        *,
        life_id: str,
        subject_id: str | None = None,
        slot_key: str | None = None,
        conflict_state: ConflictState | None = None,
        tenant_id: str = DEFAULT_TENANT,
    ) -> list[MemoryRecord]:
        self._require_life(life_id, tenant_id)
        out: list[MemoryRecord] = []
        for m in self.memories:
            # Hard predicates: never scan across tenants, never across lives.
            if m.tenant_id != tenant_id or m.life_id != life_id:
                continue
            if subject_id is not None and m.subject_id != subject_id:
                continue
            if slot_key is not None and m.slot_key != slot_key:
                continue
            if conflict_state is not None and m.conflict_state != conflict_state:
                continue
            out.append(m)
        return out

    def get_relationship(
        self, *, life_id: str, subject_id: str, tenant_id: str = DEFAULT_TENANT
    ) -> RelationshipState | None:
        self._require_life(life_id, tenant_id)
        return self._relationships.get((tenant_id, life_id, subject_id))

    # ------------------------------------------------------------------ #
    # authoritative state writes - GUARDED
    # ------------------------------------------------------------------ #

    def _set_state(
        self,
        life_id: str,
        state_key: str,
        value: float,
        at: datetime | None = None,
        tenant_id: str = DEFAULT_TENANT,
    ) -> None:
        """PRIVATE on purpose: authoritative state writes only via commit_effects."""
        self._states[(tenant_id, life_id, state_key)] = value
        if at is not None:
            self._state_times[(tenant_id, life_id, state_key)] = at

    def commit_effects(
        self,
        effects: Effects,
        *,
        intents: Iterable[BehaviorIntent] = (),
        decisions: Iterable[PolicyDecision] = (),
        fail_before_apply: bool = False,
    ) -> None:
        """Apply one L2's effects atomically (staged first, then single write phase).

        ``fail_before_apply`` is a test hook injecting a failure AFTER staging and
        BEFORE any mutation - proving transaction atomicity (no half-applied state).
        """
        staged_states = dict(effects.state_updates)
        staged_inserts = [copy.deepcopy(m) for m in effects.memory_inserts]
        staged_updates = [copy.deepcopy(m) for m in effects.memory_updates]
        staged_rels = [copy.deepcopy(r) for r in effects.relationship_upserts]
        staged_outbox = [copy.deepcopy(o) for o in effects.outbox_rows]
        staged_intents = list(intents)
        staged_decisions = list(decisions)

        # Intents transition WITH their decisions in the same transaction: the
        # backing check sees persisted + staged decisions together (design 01 §6.2).
        known_decisions: dict[str, PolicyDecision] = {
            d.decision_id: d for d in self.decisions
        }
        for decision in staged_decisions:
            if decision.decision_id in known_decisions:
                raise ValueError(f"decision already recorded: {decision.decision_id}")
            known_decisions[decision.decision_id] = decision
        for intent in staged_intents:
            self._validate_intent_transition(intent, known_decisions.values())

        if fail_before_apply:
            raise RuntimeError("injected failure before apply (atomicity test hook)")

        # ---- single application phase: nothing below may raise ----
        for (tenant_id, life_id, key), value in staged_states.items():
            self._set_state(
                life_id, key, value, at=effects.state_time, tenant_id=tenant_id
            )
        current_ids = {m.memory_id for m in self.memories}
        for m in staged_updates:
            if m.memory_id not in current_ids:
                raise RuntimeError(f"memory update target missing: {m.memory_id}")
            self.memories = [
                m2 if m2.memory_id != m.memory_id else m for m2 in self.memories
            ]
        for m in staged_inserts:
            self.memories.append(m)
        for r in staged_rels:
            self._relationships[(r.tenant_id, r.life_id, r.subject_id)] = r
        self.intents.extend(staged_intents)
        self.decisions.extend(staged_decisions)
        self.outbox.extend(staged_outbox)

    def _validate_intent_transition(
        self, intent: BehaviorIntent, decisions: Iterable[PolicyDecision]
    ) -> None:
        """Status-flow guard: only policy-backed transitions exist (design 01 §6.2)."""
        if intent.status == BehaviorStatus.EXECUTED:
            raise ValueError("status=executed requires rendering (Phase 1) - forbidden")
        if intent.status in (BehaviorStatus.APPROVED, BehaviorStatus.REJECTED):
            backed = any(
                d.intent_id == intent.intent_id
                and (
                    (intent.status == BehaviorStatus.APPROVED and d.result.value == "approve")
                    or (intent.status == BehaviorStatus.REJECTED and d.result.value == "reject")
                )
                for d in decisions
            )
            if not backed:
                raise ValueError(
                    f"intent {intent.intent_id} status={intent.status.value} "
                    "requires a matching PolicyDecision - bypass forbidden"
                )

    # ------------------------------------------------------------------ #
    # snapshot (for zero-side-effect assertions)
    # ------------------------------------------------------------------ #

    def snapshot(self) -> dict[str, Any]:
        return {
            "states": copy.deepcopy(self._states),
            "memories": copy.deepcopy(self.memories),
            "relationships": copy.deepcopy(self._relationships),
            "intents": copy.deepcopy(self.intents),
            "outbox": copy.deepcopy(self.outbox),
            "consent_records": copy.deepcopy(self.consent_records),
        }
