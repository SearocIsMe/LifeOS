"""Billing & alerting aggregator for cloud inference calls.

Parameters given by the project owner (2026-09-29, closes the README
"两家云端计费告警配置" legacy item):

- unit price: 0.4 CNY per 1,000,000 tokens (prompt + completion);
- alert line: alert once the accumulated total exceeds 100 CNY, then
  again for every further 100 CNY of growth (100, 200, 300, ...).

Also provides the per-thousand-call cost aggregation (P50/P95) required
by Gate 2 criterion #5 (Invocation aggregation, CNY per 1k calls).
All fields are deterministic; same records always yield same bytes.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Mapping, Sequence

from lifeos.events.protocol import canonical_json, sha256_hex

# Project-owner parameters (2026-09-29). Managed as a versioned constant
# so any change is a new version, never a silent edit (Gate 0 #4).
BILLING_RULES_VERSION = "billing-v1"
UNIT_PRICE_CNY_PER_1M_TOKENS = 0.4
ALERT_LINE_CNY = 100.0
ALERT_STEP_CNY = 100.0

_EPS = 1e-9


def cost_cny(total_tokens: int) -> float:
    """Cost of one record: ``tokens / 1M * 0.4`` (deterministic rounding)."""
    if total_tokens < 0:
        raise ValueError("total_tokens must be non-negative")
    return round(total_tokens / 1_000_000 * UNIT_PRICE_CNY_PER_1M_TOKENS, 10)


@dataclass(frozen=True)
class UsageRecord:
    """One cloud call: provider tag + token counts."""

    provider_id: str
    prompt_tokens: int
    completion_tokens: int

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


def _percentile(sorted_values: Sequence[float], p: float) -> float:
    """Linear-interpolation percentile on a pre-sorted sequence."""
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    k = (len(sorted_values) - 1) * p
    lo = math.floor(k)
    hi = math.ceil(k)
    if lo == hi:
        return float(sorted_values[lo])
    return float(sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (k - lo))


@dataclass
class BillingAggregator:
    """Accumulates usage, computes totals and fires the alert line."""

    records: list[UsageRecord] = field(default_factory=list)
    _alert_level: int = 0  # highest alert line already crossed

    def record(self, rec: UsageRecord) -> Mapping[str, object]:
        """Record one usage record; return the resulting billing state."""
        if rec.prompt_tokens < 0 or rec.completion_tokens < 0:
            raise ValueError("token counts must be non-negative")
        self.records.append(rec)
        fired = self._fire_alerts()
        return self.state(fired=fired)

    def _fire_alerts(self) -> list[float]:
        """Fire threshold N when the accumulated total exceeds N * line.

        ``超过`` is strict: a total exactly equal to N * 100 CNY does not
        fire; only growth past it does.
        """
        fired: list[float] = []
        while (self._alert_level + 1) * ALERT_LINE_CNY < self.total_cny - _EPS:
            self._alert_level += 1
            fired.append(self._alert_level * ALERT_LINE_CNY)
        return fired

    @property
    def total_tokens(self) -> int:
        return sum(r.total_tokens for r in self.records)

    @property
    def total_cny(self) -> float:
        return cost_cny(self.total_tokens)

    @property
    def alert_level(self) -> int:
        return self._alert_level

    def per_call_costs(self) -> list[float]:
        """Cost of each record in the order received."""
        return [cost_cny(r.total_tokens) for r in self.records]

    def per_thousand_calls_cny(self) -> dict[str, float]:
        """Per-1k-calls cost projection (Gate 2 #5): P50/P95 + mean."""
        costs = sorted(self.per_call_costs())
        if not costs:
            return {"P50": 0.0, "P95": 0.0, "mean": 0.0}
        p50 = _percentile(costs, 0.50)
        p95 = _percentile(costs, 0.95)
        mean = sum(costs) / len(costs)
        return {
            "P50": round(p50 * 1000, 6),
            "P95": round(p95 * 1000, 6),
            "mean": round(mean * 1000, 6),
        }

    def state(self, fired: Sequence[float] = ()) -> Mapping[str, object]:
        """Full deterministic billing state (stable dict insertion order)."""
        return {
            "rules_version": BILLING_RULES_VERSION,
            "record_count": len(self.records),
            "total_tokens": self.total_tokens,
            "total_cny": self.total_cny,
            "alert_level": self._alert_level,
            "alerts_fired": list(fired),
            "per_thousand_calls_cny": self.per_thousand_calls_cny(),
            "state_hash": None,  # replaced below
        }

    def state_hash(self) -> str:
        """SHA-256 over canonical state (hash field excluded)."""
        return sha256_hex(self.state())[:24]

    def state_signed(self) -> Mapping[str, object]:
        """State with the hash filled in — same records, same bytes."""
        s = dict(self.state())
        s["state_hash"] = self.state_hash()
        return s

    def export(self) -> str:
        """Canonical export: same logical records always produce same bytes."""
        return canonical_json(self.state_signed())
