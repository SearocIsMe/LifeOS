"""Online event pipeline: normalize -> interpret -> commit -> decide -> apply.

Order is FIXED (architecture §1.4 four locks):
- L1 output_json flows ONLY to the InterpretedEvent archive and into
  ``deterministic_commit`` - never to state writes directly;
- Policy ``decide`` runs BEFORE the transaction opens (pure function);
- commit_effects applies L2 effects + intent + decision in ONE atomic step;
- a rejected intent produces the decision record and ZERO state side effects
  (the L2's own perceptual effects still apply - rejection cancels the
  response, not the perception; design doc 01 §6.3).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lifeos import POLICY_VERSION, RULES_VERSION, SCHEMA_VERSION
from lifeos.entities import (
    BehaviorIntent,
    BehaviorStatus,
    ConflictState,
    DomainEvent,
    EmbeddingOutbox,
    EventSource,
    IntentModality,
    InterpretedEvent,
    MemoryRecord,
    MemoryType,
    OutboxStatus,
    PolicyDecision,
    PolicyResult,
    PrivacyLevel,
    RawEvent,
    RelationshipState,
)
from lifeos.events.commit import (
    AMBIGUOUS_CONFIDENCE_THRESHOLD,
    RELATIONSHIP_WEIGHTS,
    CommitError,
    deterministic_commit,
)
from lifeos.events.interpret import rule_interpret
from lifeos.events.protocol import derive_id
from lifeos.policy.engine import decide
from lifeos.store.memory_store import Effects, InMemoryStore


def _clip01(x: float) -> float:
    return round(min(1.0, max(0.0, x)), 10)


def build_effects(store: InMemoryStore, l2: DomainEvent) -> Effects:
    """Compute the authoritative-state effects of one L2 (pure given the store read view)."""
    effects = Effects()
    life_id = l2.life_id
    now = l2.committed_at

    for key, delta in l2.payload["state_deltas"].items():
        cur = store.get_state(life_id=life_id, state_key=key)
        effects.state_updates[(life_id, key)] = _clip01(cur + delta)

    for cand in l2.payload["memory_candidates"]:
        memory_id = derive_id(
            "M",
            {
                "l2": l2.event_id,
                "content": cand["content"],
                "slot": cand.get("slot_key"),
                "subject": cand.get("subject_id"),
            },
        )
        record = MemoryRecord(
            memory_id=memory_id,
            life_id=life_id,
            subject_id=cand.get("subject_id"),
            type=MemoryType(cand["type"]),
            content=cand["content"],
            slot_key=cand.get("slot_key"),
            valid_from=now,
            transaction_from=now,
            confidence=float(cand["confidence"]),
            importance=int(cand["importance"]),
            privacy_level=PrivacyLevel(cand.get("privacy_level", "normal")),
            source_event_ids=[l2.event_id],
            version=1,
        )
        slot = cand.get("slot_key")
        if slot:
            current = [
                m
                for m in store.query_memories(life_id=life_id, slot_key=slot)
                if m.conflict_state is ConflictState.CURRENT
            ]
            if current:
                old = current[0]
                if cand["confidence"] >= AMBIGUOUS_CONFIDENCE_THRESHOLD:
                    # update semantics: supersede old version, history retained
                    effects.memory_updates.append(
                        old.model_copy(
                            update={
                                "transaction_to": now,
                                "conflict_state": ConflictState.SUPERSEDED,
                            }
                        )
                    )
                else:
                    # contradict/low-confidence: both flagged ambiguous (human queue)
                    effects.memory_updates.append(
                        old.model_copy(update={"conflict_state": ConflictState.AMBIGUOUS})
                    )
                    record = record.model_copy(
                        update={"conflict_state": ConflictState.AMBIGUOUS}
                    )
        effects.memory_inserts.append(record)
        effects.outbox_rows.append(
            EmbeddingOutbox(
                outbox_id=derive_id("OB", {"memory": record.memory_id}),
                life_id=life_id,
                memory_id=record.memory_id,
                embedding_model_version="",  # chosen in Phase 1 (D3-1)
                status=OutboxStatus.PENDING,
                created_at=now,
            )
        )

    rd = l2.payload.get("relationship_delta")
    if rd:
        weight = RELATIONSHIP_WEIGHTS.get(rd["weight_key"])
        if weight is None:
            raise CommitError(f"unknown relationship weight_key: {rd['weight_key']!r}")
        inc = weight * float(rd["confidence"])  # personality modulation p=1.0 in Phase 0
        cur = store.get_relationship(life_id=life_id, subject_id=rd["subject_id"])
        if cur is None:
            effects.relationship_upserts.append(
                RelationshipState(
                    life_id=life_id,
                    subject_id=rd["subject_id"],
                    familiarity=_clip01(0.2 + inc),
                    trust=_clip01(0.2 + inc),
                    attachment=_clip01(0.2 + inc),
                    updated_at=now,
                    version=1,
                )
            )
        else:
            effects.relationship_upserts.append(
                cur.model_copy(
                    update={
                        "familiarity": _clip01(cur.familiarity + inc),
                        "trust": _clip01(cur.trust + inc),
                        "attachment": _clip01(cur.attachment + inc),
                        "updated_at": now,
                        "version": cur.version + 1,
                    }
                )
            )
    return effects


@dataclass
class PipelineResult:
    raw_event: RawEvent | None
    interpreted: InterpretedEvent | None
    domain: DomainEvent | None
    intent: BehaviorIntent | None
    decision: PolicyDecision | None
    effects: Effects | None
    duplicate: bool = False


class EventPipeline:
    """The ONLY orchestration of the L0->L2 path (import-discipline anchor)."""

    def __init__(
        self,
        store: InMemoryStore,
        *,
        schema_version: str = SCHEMA_VERSION,
        policy_version: str = POLICY_VERSION,
        rules_version: str = RULES_VERSION,
        extractor_version: str = "rule@phase0-0001",
    ) -> None:
        self.store = store
        self.schema_version = schema_version
        self.policy_version = policy_version
        self.rules_version = rules_version
        self.extractor_version = extractor_version

    def ingest(self, l0: dict[str, Any]) -> PipelineResult:
        raw = self.store.ingest_raw(
            life_id=l0["life_id"],
            source=EventSource(l0["source"]),
            payload=l0["payload"],
            occurred_at=l0["occurred_at"],
            modality=l0.get("modality", "text"),
        )
        if raw is None:
            return PipelineResult(None, None, None, None, None, None, duplicate=True)

        l1 = rule_interpret(raw, extractor_version=self.extractor_version)
        self.store.archive_l1(l1)

        l2 = deterministic_commit(
            l1.output_json,
            life_id=raw.life_id,
            l1_event_id=l1.event_id,
            raw_event_id=raw.event_id,
            occurred_at=raw.occurred_at,
            schema_version=self.schema_version,
            policy_version=self.policy_version,
            rules_version=self.rules_version,
        )
        self.store.archive_l2(l2)

        # Policy BEFORE the transaction opens (design 01 §6.3).
        intent: BehaviorIntent | None = None
        decision: PolicyDecision | None = None
        proposed = l2.payload.get("proposed_intent")
        if proposed:
            intent = BehaviorIntent(
                intent_id=derive_id("BI", {"l2": l2.event_id, "proposed": proposed}),
                life_id=l2.life_id,
                intent_type=proposed["intent_type"],
                modality=IntentModality(proposed["modality"]),
                reason=proposed.get("reason") or {},
                created_at=l2.committed_at,
                status=BehaviorStatus.PROPOSED,
            )
            context = {"referenced_memories": l2.payload["memory_candidates"]}
            decision = decide(
                intent.model_dump(),
                context,
                policy_version=self.policy_version,
                decided_at=l2.committed_at,
            )
            intent = intent.model_copy(
                update={
                    "status": (
                        BehaviorStatus.APPROVED
                        if decision.result is PolicyResult.APPROVE
                        else BehaviorStatus.REJECTED
                    )
                }
            )

        effects = build_effects(self.store, l2)
        self.store.commit_effects(
            effects,
            intents=[intent] if intent else (),
            decisions=[decision] if decision else (),
        )
        return PipelineResult(raw, l1, l2, intent, decision, effects)
