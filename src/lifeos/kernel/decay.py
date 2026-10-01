"""Lazy decay: authoritative state materialized ONLY on five triggers.

Architecture §5.1 (verbatim formula):
    x(t) = b + (x(t0) - b) * exp(-lambda * (t - t0))

Design invariants (design doc 01 §1.1):
- pure function: same (t0, x(t0), t) => same x(t), bit-exact;
- decay converges monotonically toward baseline b and never crosses it;
- decay affects ONLY the read view - event history is never modified
  (replay recomputes decay instead of replaying intermediate states);
- materialization happens only on: event / plan / snapshot / eval / export.

Baseline b and decay rate lambda are ENGINEERING FLOORS (source (b)):
initial constants recorded in ADR-0005 with a calibration path; they are
NOT validated conclusions.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping

# Five materialization triggers (architecture §5.1).
DECAY_TRIGGERS = frozenset({"event", "plan", "snapshot", "eval", "export"})

# State keys in the Phase 2 kernel: Phase 1 ramped 3 states, Phase 2
# completes the frozen 5-state space (spec F2, verbatim keys).
KERNEL_STATES = ("energy", "social_need", "security", "curiosity", "playfulness")
VALENCE_AROUSAL = ("valence", "arousal")

# Engineering floors: (baseline, lambda per hour) per state key.
# ADR-0005 covers the Phase 1 ramp; ADR-0006 records the Phase 2
# completion of curiosity/playfulness - NOT validated conclusions.
DECAY_PARAMS: Mapping[str, tuple[float, float]] = {
    "energy": (0.5, 0.02),
    "social_need": (0.6, 0.05),
    "security": (0.7, 0.01),
    "curiosity": (0.6, 0.04),
    "playfulness": (0.5, 0.06),
    "valence": (0.0, 0.10),
    "arousal": (0.0, 0.20),
}


class DecayError(ValueError):
    """Raised for invalid decay inputs (fail-closed)."""


def _params(state_key: str) -> tuple[float, float]:
    if state_key not in DECAY_PARAMS:
        raise DecayError(f"unknown state_key: {state_key!r}")
    return DECAY_PARAMS[state_key]


def decay_value(
    state_key: str,
    value_at_t0: float,
    *,
    t0: float,
    t: float,
    baseline: float | None = None,
    lambda_: float | None = None,
) -> float:
    """x(t) = b + (x(t0) - b) * exp(-lambda * (t - t0)), pure and exact.

    ``t0``/``t`` are hours on the instance clock; the caller converts from
    timestamps. Raises DecayError on unknown key, non-finite value, or t < t0.
    """
    b, lam = _params(state_key) if baseline is None or lambda_ is None else (baseline, lambda_)
    if not math.isfinite(value_at_t0):
        raise DecayError(f"non-finite value_at_t0: {value_at_t0!r}")
    if t < t0:
        raise DecayError(f"t ({t!r}) < t0 ({t0!r})")
    if t == t0:
        return value_at_t0
    x = b + (value_at_t0 - b) * math.exp(-lam * (t - t0))
    return x


def decay_state_map(
    values: Mapping[str, float],
    *,
    t0: float,
    t: float,
    triggers: set[str] | None = None,
) -> dict[str, float]:
    """Decay a whole state snapshot; skips work when no trigger is present.

    ``triggers`` is the set of reasons the read is happening; when it does
    not intersect DECAY_TRIGGERS the map is returned unchanged (lazy).
    """
    if triggers is not None and not (triggers & DECAY_TRIGGERS):
        return dict(values)
    out: dict[str, float] = {}
    for key, val in values.items():
        out[key] = decay_value(key, val, t0=t0, t=t)
    return out


@dataclass(frozen=True)
class KernelSnapshot:
    """Read view of the kernel at one instant (never persisted as history)."""

    t: float
    states: Mapping[str, float]


def snapshot(
    values: Mapping[str, float],
    *,
    t0: float,
    t: float,
    trigger: str = "snapshot",
) -> KernelSnapshot:
    """Materialize a kernel snapshot (trigger defaults to 'snapshot')."""
    if trigger not in DECAY_TRIGGERS:
        raise DecayError(f"invalid snapshot trigger: {trigger!r}")
    return KernelSnapshot(t=t, states=decay_state_map(values, t0=t0, t=t, triggers={trigger}))
