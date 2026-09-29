"""Behavior Planner v0 - Utility Scoring (design doc 01 §3.1, architecture §5.4).

The Phase 1 candidate set is SMALL and closed, so Utility Scoring beats the
alternatives under comparison: every score is a closed-form function of the
current read view and emits its own ``reason`` evidence chain. py_trees and
LangGraph stay out of the critical path (roadmap decision); GOAP is
unnecessary because Phase 1 behaviors have no action chains.

Closed-form formula (components recorded per candidate in ``reason``):

    utility(intent) = w_intent * feature(states, relationships)
                      - cooldown_penalty(intent)

- ``feature`` is a precondition severity in [0, 1] (e.g. comfort ramps up as
  ``security`` falls below ``COMFORT_SECURITY_THRESHOLD``; ``recall_shared``
  tracks the strongest subject ``familiarity``).
- ``stay_quiet`` carries the 0.5 BASELINE as a subtraction floor: any intent
  must beat 0.5 to be selected over silence.
- ``cooldown_penalty`` suppresses an intent that was just executed, preventing
  repetitive loops (e.g. greet -> greet).

Weights in ``PLANNER_WEIGHTS`` are ENGINEERING FLOOR constants: changing them
requires an ADR, never an inline tweak (same discipline as DECAY_PARAMS).

Purity contract: ``plan_intents`` is a pure function - same read view, same
proposals (intent ids are content-addressed via ``derive_id``). No storage, no
wall clock (``created_at`` injected). Proposals keep ``status=proposed``; only
the Policy Engine may transition to approved/rejected (design doc 01 §6.2).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from lifeos.entities import BehaviorIntent, BehaviorStatus, IntentModality
from lifeos.events.protocol import derive_id

PLANNER_VERSION = "0.1.0"

# Kernel states the planner reads; missing keys fail closed (PlannerError).
REQUIRED_STATES = ("energy", "social_need", "security")

# Engineering-floor weights (ADR required to calibrate; see module docstring).
PLANNER_WEIGHTS: Mapping[str, float] = {
    "greet": 1.0,
    "reflect_state": 0.6,
    "recall_shared": 0.9,
    "inquire_user": 0.8,
    "comfort": 3.0,
    "stay_quiet": 1.0,
}

STAY_QUIET_BASELINE = 0.5
COMFORT_SECURITY_THRESHOLD = 0.4

MODALITY_BY_INTENT: Mapping[str, IntentModality] = {
    "greet": IntentModality.VERBAL,
    "reflect_state": IntentModality.VERBAL,
    "recall_shared": IntentModality.VERBAL,
    "inquire_user": IntentModality.VERBAL,
    "comfort": IntentModality.VERBAL,
    "stay_quiet": IntentModality.ATTENTIONAL,
}


class PlannerError(Exception):
    """Planner precondition violated (e.g. missing kernel state key)."""


def _feature(
    intent_type: str,
    states: Mapping[str, float],
    relationships: Mapping[str, Mapping[str, Any]],
) -> float:
    """Precondition severity in [0, 1] for one candidate intent."""
    if intent_type == "greet":
        return float(states["social_need"])
    if intent_type == "reflect_state":
        return float(states["energy"])
    if intent_type == "recall_shared":
        if not relationships:
            return 0.0
        return max(float(rel.get("familiarity", 0.0)) for rel in relationships.values())
    if intent_type == "inquire_user":
        return float(states["social_need"])
    if intent_type == "comfort":
        security = float(states["security"])
        return max(0.0, COMFORT_SECURITY_THRESHOLD - security)
    if intent_type == "stay_quiet":
        return STAY_QUIET_BASELINE
    raise PlannerError(f"unknown intent_type: {intent_type!r}")


def plan_intents(
    life_id: str,
    states: Mapping[str, float],
    relationships: Mapping[str, Mapping[str, Any]] | None = None,
    *,
    cooldown: Mapping[str, float] | None = None,
    created_at: datetime,
    planner_version: str = PLANNER_VERSION,
) -> list[BehaviorIntent]:
    """Score all six candidate intents against the current read view.

    Returns the proposals sorted by ``utility_score`` descending (stable sort:
    equal utilities keep the declared candidate order, so output is
    deterministic). Raises ``PlannerError`` if any kernel state is missing -
    fail closed before any proposal is produced.
    """
    missing = [key for key in REQUIRED_STATES if key not in states]
    if missing:
        raise PlannerError(f"missing kernel states: {missing}")
    rels = dict(relationships or {})
    cd = dict(cooldown or {})

    proposals: list[BehaviorIntent] = []
    for intent_type, weight in PLANNER_WEIGHTS.items():
        penalty = float(cd.get(intent_type, 0.0))
        raw = _feature(intent_type, states, rels)
        utility = round(weight * raw - penalty, 10)
        preconditions: dict[str, Any] = {"required_states": list(REQUIRED_STATES)}
        if intent_type == "comfort":
            preconditions["security_lt"] = COMFORT_SECURITY_THRESHOLD
        proposals.append(
            BehaviorIntent(
                intent_id=derive_id(
                    "BI",
                    {
                        "life_id": life_id,
                        "intent_type": intent_type,
                        "planner_version": planner_version,
                    },
                ),
                life_id=life_id,
                intent_type=intent_type,
                modality=MODALITY_BY_INTENT[intent_type],
                utility_score=utility,
                reason={
                    "feature": round(raw, 10),
                    "weight": weight,
                    "cooldown_penalty": penalty,
                },
                preconditions=preconditions,
                status=BehaviorStatus.PROPOSED,
                created_at=created_at,
            )
        )
    proposals.sort(key=lambda bi: bi.utility_score, reverse=True)
    return proposals


def select_best(*args: Any, **kwargs: Any) -> BehaviorIntent:
    """Convenience wrapper: the single highest-utility proposal."""
    return plan_intents(*args, **kwargs)[0]
