"""``deterministic_commit`` - the single L1 -> L2 transform (design doc 01 §4.3).

Contract (Gate 0 #2 foundation):
1. NO internal clock   - committed_at := occurred_at (injected; D4-2);
2. NO randomness       - event_id derived from content hash;
3. NO I/O              - validation + projection only;
4. Same input -> byte-identical canonical output.

Fail-closed: any out-of-contract field raises CommitError - no silent clipping
(silent repair would mask L1 extraction quality regressions in Phase 1).

Import discipline (CI-checked): only ``lifeos.events.pipeline`` may import this
module - it is the only path from interpretations to authoritative state.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from pydantic import ConfigDict, Field, ValidationError, field_validator, model_validator

from lifeos.entities import (
    DomainEvent,
    IntentModality,
    MemoryType,
    PrivacyLevel,
    _Contract,
)
from lifeos.events.protocol import derive_id

# Kernel states (architecture §5.1; Phase 1 activates 3 of 5 first).
KERNEL_STATES = ("energy", "social_need", "security", "curiosity", "playfulness")

# L2 event types in Phase 0 (system_note covers audit/simulation events).
EVENT_TYPES = ("user_message", "system_note")

# Relationship event weight table (rules_version-scoped; engineering placeholders,
# calibration via ADR in Phase 1/2 - spec §5.2 honesty note).
RELATIONSHIP_WEIGHTS: dict[str, float] = {
    "positive_interaction": 0.05,
    "negative_interaction": -0.05,
    "reunion": 0.08,
    "conflict": -0.10,
}

# Same-slot conflict threshold: >= THRESHOLD supersedes, < THRESHOLD -> ambiguous.
# Engineering placeholder, rules_version-scoped (spec §5.2: no evidence-based
# value yet; calibration via ADR).
AMBIGUOUS_CONFIDENCE_THRESHOLD = 0.8


class CommitError(ValueError):
    """Raised when L1 output violates the output_json contract (fail-closed)."""


class _Strict(_Contract):
    model_config = ConfigDict(extra="forbid")


class EmotionCue(_Strict):
    valence: float = Field(ge=-1.0, le=1.0)
    arousal: float = Field(ge=0.0, le=1.0)


class MemoryCandidate(_Strict):
    type: MemoryType
    content: str = Field(min_length=1, max_length=500)
    slot_key: str | None = None
    subject_id: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    importance: int = Field(ge=1, le=5)
    privacy_level: PrivacyLevel = PrivacyLevel.NORMAL
    emotion: EmotionCue | None = None


class RelationshipDelta(_Strict):
    subject_id: str = Field(min_length=1)
    weight_key: str
    confidence: float = Field(ge=0.0, le=1.0)


class ProposedIntent(_Strict):
    intent_type: str = Field(min_length=1)
    modality: IntentModality
    reason: dict[str, Any] = Field(default_factory=dict)


class InterpretedOutput(_Strict):
    """The ONLY legal shape of L1 ``output_json`` (design doc 01 §4.2).

    ``extra="forbid"``: any smuggled field (e.g. ``authoritative_state_write``)
    fails validation - first lock of the LLM boundary (AC-06).
    """

    event_type: str
    emotion: EmotionCue | None = None
    state_deltas: dict[str, float] = Field(default_factory=dict)
    memory_candidates: list[MemoryCandidate] = Field(default_factory=list)
    relationship_delta: RelationshipDelta | None = None
    proposed_intent: ProposedIntent | None = None

    @field_validator("event_type")
    @classmethod
    def _event_type_known(cls, v: str) -> str:
        if v not in EVENT_TYPES:
            raise ValueError(f"unknown event_type {v!r}; allowed: {EVENT_TYPES}")
        return v

    @model_validator(mode="after")
    def _state_deltas_in_range(self) -> "InterpretedOutput":
        for key, value in self.state_deltas.items():
            if key not in KERNEL_STATES:
                raise ValueError(f"unknown state key {key!r}; allowed: {KERNEL_STATES}")
            if not (-1.0 <= value <= 1.0):
                raise ValueError(f"state delta {key}={value} outside [-1, 1]")
        return self


def deterministic_commit(
    output_json: Mapping[str, Any],
    *,
    life_id: str,
    l1_event_id: str,
    raw_event_id: str,
    occurred_at: datetime,
    schema_version: str,
    policy_version: str,
    rules_version: str,
) -> DomainEvent:
    """Commit an interpretation into an authoritative L2 DomainEvent.

    Pure function (see module docstring). Used by BOTH the online path and the
    replay path - the repository must never contain a second implementation.
    """
    try:
        parsed = InterpretedOutput.model_validate(dict(output_json))  # fail-closed
    except ValidationError as exc:
        raise CommitError(f"output_json violates the L1 contract: {exc}") from exc

    payload: dict[str, Any] = {
        "emotion": parsed.emotion.model_dump() if parsed.emotion else None,
        "state_deltas": {k: float(v) for k, v in parsed.state_deltas.items()},
        "memory_candidates": [c.model_dump() for c in parsed.memory_candidates],
        "relationship_delta": (
            parsed.relationship_delta.model_dump() if parsed.relationship_delta else None
        ),
        "proposed_intent": (
            parsed.proposed_intent.model_dump() if parsed.proposed_intent else None
        ),
    }

    event_id = derive_id(
        "L2",
        {
            "l1_event_id": l1_event_id,
            "output_json": dict(output_json),
            "schema_version": schema_version,
            "policy_version": policy_version,
            "rules_version": rules_version,
        },
    )

    # committed_at := occurred_at (D4-2). Wall clock is never semantic time;
    # the store records a non-semantic ingested_at separately.
    return DomainEvent(
        event_id=event_id,
        life_id=life_id,
        l1_event_id=l1_event_id,
        event_type=parsed.event_type,
        payload=payload,
        schema_version=schema_version,
        policy_version=policy_version,
        rules_version=rules_version,
        committed_at=occurred_at,
    )
