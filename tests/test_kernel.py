"""S1 acceptance cases: lazy decay + pipeline decay increment (design doc 02 §2 S1 table)."""

import math
from datetime import timedelta

import pytest

from lifeos.cli import T0, _new_store_and_pipeline

from lifeos.kernel.decay import (
    DECAY_PARAMS,
    DECAY_TRIGGERS,
    KERNEL_STATES,
    DecayError,
    decay_state_map,
    decay_value,
    snapshot,
)


class TestDecayPureFunction:
    def test_same_inputs_same_value(self):
        a = decay_value("energy", 0.8, t0=0.0, t=5.0)
        b = decay_value("energy", 0.8, t0=0.0, t=5.0)
        assert a == b

    def test_bit_exact_repeat(self):
        a = decay_value("security", 0.3, t0=2.0, t=7.5)
        b = decay_value("security", 0.3, t0=2.0, t=7.5)
        assert a == b and math.isfinite(a)


class TestDecayMonotonicity:
    def test_converges_toward_baseline(self):
        # above baseline: decay decreases toward b
        prev = decay_value("energy", 0.9, t0=0.0, t=0.0)
        for t in (1.0, 5.0, 20.0, 100.0):
            cur = decay_value("energy", 0.9, t0=0.0, t=t)
            assert cur < prev
            assert cur > DECAY_PARAMS["energy"][0]
            prev = cur

    def test_below_baseline_rises(self):
        # below baseline: decay increases toward b, never crosses it
        prev = decay_value("energy", 0.1, t0=0.0, t=0.0)
        for t in (1.0, 10.0, 50.0):
            cur = decay_value("energy", 0.1, t0=0.0, t=t)
            assert cur > prev
            assert cur < DECAY_PARAMS["energy"][0]
            prev = cur

    def test_exact_baseline_stays(self):
        b = DECAY_PARAMS["security"][0]
        assert decay_value("security", b, t0=0.0, t=42.0) == pytest.approx(b)


class TestMaterializationTriggers:
    def test_no_trigger_is_lazy(self):
        values = {"energy": 0.8, "social_need": 0.5}
        out = decay_state_map(values, t0=0.0, t=10.0, triggers=set())
        assert out == values  # unchanged: no decay computed

    def test_trigger_materializes(self):
        values = {"energy": 0.8}
        out = decay_state_map(values, t0=0.0, t=10.0, triggers={"snapshot"})
        assert out["energy"] < 0.8

    def test_all_five_triggers_are_valid(self):
        assert DECAY_TRIGGERS == {"event", "plan", "snapshot", "eval", "export"}

    def test_snapshot_invalid_trigger_raises(self):
        with pytest.raises(DecayError):
            snapshot({"energy": 0.8}, t0=0.0, t=1.0, trigger="read")

    def test_snapshot_valid(self):
        snap = snapshot({"energy": 0.8}, t0=0.0, t=4.0)
        assert snap.t == 4.0 and snap.states["energy"] < 0.8


class TestFailClosed:
    def test_unknown_state_key(self):
        with pytest.raises(DecayError):
            decay_value("mood", 0.5, t0=0.0, t=1.0)

    def test_t_before_t0(self):
        with pytest.raises(DecayError):
            decay_value("energy", 0.5, t0=5.0, t=1.0)

    def test_non_finite_value(self):
        with pytest.raises(DecayError):
            decay_value("energy", float("nan"), t0=0.0, t=1.0)


class TestStateSpace:
    def test_five_kernel_states(self):
        # Phase 2 completes the frozen 5-state space (spec F2, roadmap S1).
        assert KERNEL_STATES == (
            "energy",
            "social_need",
            "security",
            "curiosity",
            "playfulness",
        )
        for key in KERNEL_STATES:
            assert key in DECAY_PARAMS


LID = "life-kernel"


def _l0(state_deltas, occurred_at, text):
    return {
        "life_id": LID,
        "source": "user",
        "occurred_at": occurred_at,
        "payload": {"text": text, "structured": {"state_deltas": state_deltas}},
    }


class TestPipelineDecayIncrement:
    """S1 pipeline case: L2 state_delta = lazy-decay to now THEN add delta."""

    def test_first_write_no_decay_and_time_recorded(self):
        store, pipeline = _new_store_and_pipeline(LID)
        pipeline.ingest(_l0({"energy": 0.2}, T0, "e0"))
        # default 0.5 + 0.2, untouched by decay (no t0 yet)
        assert store.get_state(life_id=LID, state_key="energy") == pytest.approx(0.7)
        assert store.get_state_time(life_id=LID, state_key="energy") == T0

    def test_decays_to_now_before_delta(self):
        store, pipeline = _new_store_and_pipeline(LID)
        pipeline.ingest(_l0({"energy": 0.2}, T0, "e0"))  # 0.7 @ T0
        t2 = T0 + timedelta(hours=10)
        pipeline.ingest(_l0({"energy": 0.1}, t2, "e1"))
        expected = min(1.0, max(0.0, decay_value("energy", 0.7, t0=0.0, t=10.0) + 0.1))
        cur = store.get_state(life_id=LID, state_key="energy")
        assert cur == pytest.approx(expected, abs=1e-9)
        assert cur < 0.8  # the 10h gap pulled the value toward b=0.5 first

    def test_same_sequence_same_states(self):
        # replaying the identical L0 sequence in a fresh store yields the
        # identical state trajectory (decay is a pure function of the gap)
        events = [
            _l0({"energy": 0.2, "social_need": -0.1}, T0, "e0"),
            _l0({"energy": 0.1}, T0 + timedelta(hours=10), "e1"),
            _l0({"energy": -0.05, "security": 0.2}, T0 + timedelta(hours=30), "e2"),
        ]
        s1, p1 = _new_store_and_pipeline(LID)
        s2, p2 = _new_store_and_pipeline(LID)
        for e in events:
            p1.ingest(dict(e))
            p2.ingest(dict(e))
        assert s1.snapshot()["states"] == s2.snapshot()["states"]

    def test_out_of_order_state_write_fails_closed(self):
        store, pipeline = _new_store_and_pipeline(LID)
        pipeline.ingest(_l0({"energy": 0.2}, T0 + timedelta(hours=5), "e0"))
        before = store.snapshot()["states"]
        with pytest.raises(DecayError):
            pipeline.ingest(_l0({"energy": 0.1}, T0, "e1"))  # earlier occurred_at
        # zero state side effects: DecayError fires before any write
        assert store.snapshot()["states"] == before
