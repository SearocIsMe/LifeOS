"""LifeOS Behavior Planner (Phase 1).

Import-discipline anchor: the planner is PURE - it imports only
``lifeos.entities`` and ``lifeos.events.protocol``, never the pipeline, the
stores, or the policy engine (the planner only PROPOSES; Policy disposes).
"""

from lifeos.planner.engine import (
    COMFORT_SECURITY_THRESHOLD,
    PLANNER_WEIGHTS,
    PLANNER_VERSION,
    STAY_QUIET_BASELINE,
    PlannerError,
    plan_intents,
    select_best,
)

__all__ = [
    "COMFORT_SECURITY_THRESHOLD",
    "PLANNER_WEIGHTS",
    "PLANNER_VERSION",
    "STAY_QUIET_BASELINE",
    "PlannerError",
    "plan_intents",
    "select_best",
]
