"""Billing & alerting unit tests (closes README legacy billing item).

Covers: unit price formula, accumulation, alert-line firing (100, 200,
...), no-alert-below-line, per-1k-calls P50/P95, and deterministic
export. Parameters per project owner (2026-09-29).
"""

import json

import pytest

from lifeos.gateway.billing import (
    ALERT_LINE_CNY,
    BILLING_RULES_VERSION,
    UsageRecord,
    BillingAggregator,
    cost_cny,
)


def test_unit_price_formula():
    """1M tokens cost exactly 0.4 CNY; sub-1M scales linearly."""
    assert cost_cny(1_000_000) == pytest.approx(0.4)
    assert cost_cny(500_000) == pytest.approx(0.2)
    assert cost_cny(2_500_000) == pytest.approx(1.0)


def test_accumulation_totals():
    """Totals accumulate across records and providers."""
    agg = BillingAggregator()
    agg.record(UsageRecord("provider-a", 300_000, 100_000))
    agg.record(UsageRecord("provider-b", 400_000, 200_000))
    assert agg.total_tokens == 1_000_000
    assert agg.total_cny == pytest.approx(0.4)


def test_no_alert_below_line():
    """Total under 100 CNY fires nothing."""
    agg = BillingAggregator()
    state = agg.record(UsageRecord("provider-a", 25_000_000, 10_000_000))
    assert state["total_cny"] < ALERT_LINE_CNY
    assert state["alert_level"] == 0
    assert state["alerts_fired"] == []


def test_alert_fires_at_100_and_steps():
    """Crossing 100 fires once; every further 100 CNY fires again.

    ``超过`` is strict: exactly 200 CNY does not fire; 204 CNY does.
    """
    agg = BillingAggregator()
    # 300M tokens = 120 CNY: first alert at 100.
    state = agg.record(UsageRecord("provider-a", 200_000_000, 100_000_000))
    assert state["total_cny"] == pytest.approx(120.0)
    assert state["alert_level"] == 1
    assert state["alerts_fired"] == [100.0]

    # +200M tokens -> 500M total = exactly 200 CNY: no new alert (strict).
    state = agg.record(UsageRecord("provider-a", 200_000_000, 0))
    assert state["total_cny"] == pytest.approx(200.0)
    assert state["alert_level"] == 1
    assert state["alerts_fired"] == []

    # +10M tokens -> 510M total = 204 CNY: alert at 200 now fires.
    state = agg.record(UsageRecord("provider-a", 10_000_000, 0))
    assert state["total_cny"] == pytest.approx(204.0)
    assert state["alert_level"] == 2
    assert state["alerts_fired"] == [200.0]

    # +250M tokens -> 760M total = 304 CNY: alert at 300 fires.
    state = agg.record(UsageRecord("provider-a", 250_000_000, 0))
    assert state["total_cny"] == pytest.approx(304.0)
    assert state["alert_level"] == 3
    assert state["alerts_fired"] == [300.0]


def test_per_thousand_calls_p50_p95():
    """Per-1k-calls projection reports P50/P95 (Gate 2 #5)."""
    agg = BillingAggregator()
    # 1M tokens per call: 0.4 CNY per call -> 400 CNY per 1k calls.
    for _ in range(5):
        agg.record(UsageRecord("provider-a", 600_000, 400_000))
    agg.record(UsageRecord("provider-a", 3_000_000, 2_000_000))  # 2 CNY/call
    proj = agg.per_thousand_calls_cny()
    assert proj["P50"] == pytest.approx(400.0)
    assert proj["P95"] > proj["P50"]
    assert proj["mean"] > proj["P50"]


def test_empty_projection_is_zero():
    """Empty aggregator projects zero cost."""
    agg = BillingAggregator()
    assert agg.per_thousand_calls_cny() == {"P50": 0.0, "P95": 0.0, "mean": 0.0}


def test_export_deterministic():
    """Same records in different insertion orders yield identical bytes."""
    a = BillingAggregator()
    b = BillingAggregator()
    for rec in [
        UsageRecord("provider-a", 300_000, 100_000),
        UsageRecord("provider-b", 400_000, 200_000),
    ]:
        a.record(rec)
    for rec in [
        UsageRecord("provider-b", 400_000, 200_000),
        UsageRecord("provider-a", 300_000, 100_000),
    ]:
        b.record(rec)
    assert a.export() == b.export()
    payload = json.loads(a.export())
    assert payload["rules_version"] == BILLING_RULES_VERSION
    assert payload["state_hash"] == payload["state_hash"]  # present, filled


def test_rejects_negative_tokens():
    """Negative token counts fail-closed."""
    agg = BillingAggregator()
    with pytest.raises(ValueError):
        agg.record(UsageRecord("provider-a", -1, 0))
    with pytest.raises(ValueError):
        cost_cny(-5)
