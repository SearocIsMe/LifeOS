"""Relationship Engine v0: r_{t+1} = clip(r_t + w_e * p * c - lambda * dt, 0, 1).

Architecture §5.3 (verbatim update rule). One row per
(life_id, subject_id); full parameter versioning (version increments on
every update); history never deleted (bitemporal fields retained); replay
recomputes instead of replaying intermediate states.

- w_e: event-type weight table - REUSED from lifeos.events.commit
  (RELATIONSHIP_WEIGHTS migration reuse, design doc 01 §1.2);
- p: personality modulation coefficient from PersonalityContract;
  Phase 1 default 1.0 (personality_seed derivation stub, ADR-0005);
- c: event confidence;
- lambda * dt: natural relationship decay, lambda 0.002/h (engineering
  floor, ADR-0005).

Memory isolation invariant (scenario-2 acceptance point): person-related
recall queries MUST carry the subject_id predicate - enforced by
InMemoryStore.query_memories and covered by unit tests.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping

from lifeos.events.commit import RELATIONSHIP_WEIGHTS

# Natural decay rate per hour (engineering floor, ADR-0005).
RELATIONSHIP_DECAY_LAMBDA = 0.002

# Personality modulation default in Phase 1 (stub for personality_seed
# derivation; same seed MUST give same coefficient set).
PERSONALITY_MODULATION_DEFAULT = 1.0


class RelationshipError(ValueError):
    """Raised for invalid relationship updates (fail-closed)."""


def _clip01(x: float) -> float:
    if not math.isfinite(x):
        raise RelationshipError(f"non-finite relationship value: {x!r}")
    return round(min(1.0, max(0.0, x)), 10)


@dataclass
class RelationshipUpdate:
    """Effect of exactly one relationship event (one transaction)."""

    subject_id: str
    familiarity: float
    trust: float
    attachment: float
    version: int
    reason: Mapping[str, Any]


def personality_modulation(personality_seed: str | None) -> float:
    """Derive p from the personality seed (Phase 1 stub).

    Same seed => same coefficient set (design invariant). Phase 1 returns
    the default 1.0 regardless of seed; the deterministic derivation is
    stubbed here so callers and tests pin the contract.
    """
    return PERSONALITY_MODULATION_DEFAULT


def apply_relationship_event(
    current: Mapping[str, Any] | None,
    *,
    subject_id: str,
    weight_key: str,
    confidence: float,
    personality_seed: str | None = None,
    dt_hours: float = 0.0,
    now: Any = None,
) -> RelationshipUpdate:
    """Compute r_{t+1} for one subject (pure given the read view).

    ``current`` is the existing row view (dict with familiarity/trust/
    attachment/version) or None for a fresh relationship (seed 0.2 per
    existing pipeline semantics). dt_hours is the gap since the row's
    updated_at, for the natural-decay term.
    """
    weight = RELATIONSHIP_WEIGHTS.get(weight_key)
    if weight is None:
        raise RelationshipError(f"unknown relationship weight_key: {weight_key!r}")
    if not 0.0 <= confidence <= 1.0:
        raise RelationshipError(f"confidence out of range: {confidence!r}")
    if dt_hours < 0:
        raise RelationshipError(f"negative dt_hours: {dt_hours!r}")

    p = personality_modulation(personality_seed)
    inc = weight * p * float(confidence) - RELATIONSHIP_DECAY_LAMBDA * dt_hours

    if current is None:
        return RelationshipUpdate(
            subject_id=subject_id,
            familiarity=_clip01(0.2 + inc),
            trust=_clip01(0.2 + inc),
            attachment=_clip01(0.2 + inc),
            version=1,
            reason={
                "weight_key": weight_key,
                "weight": weight,
                "p": p,
                "confidence": confidence,
                "decay": RELATIONSHIP_DECAY_LAMBDA * dt_hours,
                "fresh_seed": 0.2,
            },
        )

    base = {
        "familiarity": float(current["familiarity"]),
        "trust": float(current["trust"]),
        "attachment": float(current["attachment"]),
    }
    return RelationshipUpdate(
        subject_id=subject_id,
        familiarity=_clip01(base["familiarity"] + inc),
        trust=_clip01(base["trust"] + inc),
        attachment=_clip01(base["attachment"] + inc),
        version=int(current.get("version", 1)) + 1,
        reason={
            "weight_key": weight_key,
            "weight": weight,
            "p": p,
            "confidence": confidence,
            "decay": RELATIONSHIP_DECAY_LAMBDA * dt_hours,
            "previous": base,
        },
    )
