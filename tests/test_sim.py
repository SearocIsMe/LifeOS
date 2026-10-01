"""continuity-sim tests (roadmap S3, design 01 §3).

Covers: seeded determinism, dialogue-fill provenance, injection truthfulness,
and the weekly continuity report.
"""

from __future__ import annotations

from datetime import datetime

from lifeos.entities import ConflictState, MemoryType, PrivacyLevel
from lifeos.sim import SIM_DEFAULT_SEED, generate_skeleton, ramp, write_bundle
from lifeos.sim.simulator import build_bundle, fill_dialogue, inject_bundle
from lifeos.store.memory_store import InMemoryStore


def test_skeleton_is_seeded_deterministic():
    a = generate_skeleton(20260901, 14)
    b = generate_skeleton(20260901, 14)
    c = generate_skeleton(20260902, 14)
    assert a == b  # same seed -> same event sequence
    assert a != c  # different seed -> different sequence
    assert len(a) >= 28  # at least 2 events/day


def test_fill_dialogue_records_invocation_provenance():
    done = fill_dialogue(generate_skeleton(SIM_DEFAULT_SEED, 3), seed=SIM_DEFAULT_SEED)
    for i, e in enumerate(done):
        dlg = e["dialogue"]
        assert dlg["sampling"]["temperature"] == 0.0
        assert dlg["sampling"]["seed"] == SIM_DEFAULT_SEED
        assert dlg["invocation_seq"] == i
        assert dlg["purpose"] == "sim-dialogue-fill"
        assert dlg["assistant_text"]


def test_inject_bundle_injected_truth():
    store = InMemoryStore()
    skeleton = generate_skeleton(20260901, 7)
    done = fill_dialogue(skeleton, seed=20260901)
    bundle = build_bundle(done, seed=20260901)
    n = inject_bundle(store, bundle)
    assert n == len(bundle["memories"])
    assert len(store.memories) == n
    assert "life-sim" in store.instances
    m = store.memories[0]
    assert m.type in (MemoryType.EPISODIC, MemoryType.SEMANTIC)
    assert m.conflict_state == ConflictState.CURRENT


def test_write_bundle_jsonl():
    done = fill_dialogue(generate_skeleton(20260901, 2), seed=20260901)
    bundle = build_bundle(done, seed=20260901)
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as td:
        p = write_bundle(bundle, str(Path(td) / "bundle.jsonl"))
        lines = [l for l in p.read_text(encoding="utf-8").splitlines() if l]
        assert len(lines) == len(bundle["memories"])


def test_ramp_emits_weekly_continuity_report(tmp_path):
    r = ramp([20260901, 20260902], out_dir=str(tmp_path / "sim"))
    report = tmp_path / "sim" / "continuity_report.json"
    assert report.exists()
    import json

    d = json.loads(report.read_text(encoding="utf-8"))
    assert d["total_memories"] == r["total_memories"]
    assert len(d["ramp"]) == 2  # weekly entries
    assert d["ramp"][1]["memories"] >= d["ramp"][0]["memories"]  # monotonic ramp
    assert d["validity_limits"]  # reported validity limitations
