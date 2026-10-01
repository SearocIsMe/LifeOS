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

PLANNER_VERSION = "0.2.0"

# Kernel states the planner reads; missing keys fail closed (PlannerError).
# Phase 2 completes the frozen 5-state space (spec F2); valence/arousal are
# read too but are optional for planning (they inform expression only).
REQUIRED_STATES = ("energy", "social_need", "security", "curiosity", "playfulness")

# Engineering-floor weights (ADR required to calibrate; see module docstring).
# Phase 2 ramps the candidate set from 6 to 12 intents (roadmap S1).
PLANNER_WEIGHTS: Mapping[str, float] = {
    # Phase 1 declared six
    "greet": 1.0,
    "reflect_state": 0.6,
    "recall_shared": 0.9,
    "inquire_user": 0.8,
    "comfort": 3.0,
    "stay_quiet": 1.0,
    # Phase 2 adds six (intent changes via ADR + registry, roadmap §1.2)
    "share_observation": 0.7,
    "suggest_action": 0.5,
    "express_valence": 0.6,
    "recall_subject": 0.8,
    "defer_intent": 0.4,
    "clarify_ambiguity": 0.6,
}

STAY_QUIET_BASELINE = 0.5
COMFORT_SECURITY_THRESHOLD = 0.4

MODALITY_BY_INTENT: Mapping[str, IntentModality] = {
    # Phase 1 declared six
    "greet": IntentModality.VERBAL,
    "reflect_state": IntentModality.VERBAL,
    "recall_shared": IntentModality.VERBAL,
    "inquire_user": IntentModality.VERBAL,
    "comfort": IntentModality.VERBAL,
    "stay_quiet": IntentModality.ATTENTIONAL,
    # Phase 2 adds six
    "share_observation": IntentModality.VERBAL,
    "suggest_action": IntentModality.VERBAL,
    "express_valence": IntentModality.VERBAL,
    "recall_subject": IntentModality.VERBAL,
    "defer_intent": IntentModality.ATTENTIONAL,
    "clarify_ambiguity": IntentModality.VERBAL,
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
    # Phase 2 adds six
    if intent_type == "share_observation":
        return float(states["curiosity"])
    if intent_type == "suggest_action":
        return float(states["playfulness"])
    if intent_type == "express_valence":
        return abs(float(states.get("valence", 0.0)))
    if intent_type == "recall_subject":
        if not relationships:
            return 0.0
        return max(float(rel.get("familiarity", 0.0)) for rel in relationships.values())
    if intent_type == "defer_intent":
        return max(0.0, STAY_QUIET_BASELINE - float(states["energy"]))
    if intent_type == "clarify_ambiguity":
        return float(states["curiosity"])
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
        if intent_type == "defer_intent":
            preconditions["energy_lt"] = STAY_QUIET_BASELINE
        proposals.append(
            BehaviorIntent(
                intent_id=derive_id(
                    "BI",
                    {
                        "life_id": life_id,
                        "intent_type": intent_type,
                        "planner_version": planner_version,
                        "ramp": "phase2",
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
                    "score_decomposition": {
                        "weighted_feature": round(weight * raw, 10),
                        "pre_cooldown": round(weight * raw - penalty, 10),
                    },
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
