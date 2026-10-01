"""Survey generator acceptance (B4.1 施测期问卷实例，60 份 → survey/).

Case map:
- 60 instances        -> survey/*.json = 60 subject questionnaires + manifest
- pseudonymous ids    -> LIFE-BT-<seq:03d> (登记表第四部分下发规则)
- latin square        -> arm orders rotate across subjects (位置效应平衡)
- real-arm materials  -> left/right text from baseline_*_real.json; mock forbidden
- attention check     -> pinned mid-stream (问卷 fail_rule)
- consent not prefill -> consent_signed=None at generation (施测期勾选)
- determinism         -> same inputs => same instances
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GEN = REPO / "scripts" / "gen_surveys.py"
SURVEY_DIR = REPO / "survey"


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(GEN), *args], capture_output=True, text=True, timeout=120)


def test_60_instances_generated():
    r = _run()
    assert r.returncode == 0, r.stdout + r.stderr
    files = sorted(SURVEY_DIR.glob("LIFE-BT-*.json"))
    assert len(files) == 60
    manifest = json.loads((SURVEY_DIR / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["n"] == 60
    assert manifest["approval_number"] == "2026-ETH-00001"
    assert len(manifest["instances"]) == 60


def test_pseudonymous_ids_and_latin_rotation():
    s0 = json.loads((SURVEY_DIR / "LIFE-BT-000.json").read_text(encoding="utf-8"))
    s59 = json.loads((SURVEY_DIR / "LIFE-BT-059.json").read_text(encoding="utf-8"))
    assert s0["subject_id"] == "LIFE-BT-000"
    # latin square: orders rotate (000 starts A, 059 starts LifeOS)
    assert s0["arm_order"] == ["A", "B", "C", "LifeOS"]
    assert s59["arm_order"] == ["LifeOS", "A", "B", "C"]
    # each instance: 24 trials (8 fragments x 3 pairs) + attention check
    for s in (s0, s59):
        assert len(s["trials"]) == 24
        assert sum(1 for t in s["trials"] if t["is_attention_check"]) == 1


def test_real_arm_materials_only():
    s = json.loads((SURVEY_DIR / "LIFE-BT-001.json").read_text(encoding="utf-8"))
    # trial text comes from the real-arm pool (non-stub responses)
    t = s["trials"][0]
    assert t["left_text"] and t["right_text"]
    assert not t["left_text"].startswith("[mock-gen")  # mock materials forbidden in surveys


def test_consent_not_prefilled():
    s = json.loads((SURVEY_DIR / "LIFE-BT-002.json").read_text(encoding="utf-8"))
    assert s["consent_signed"] is None  # 施测期由被试勾选；生成时不预填
    assert len(s["consent_items"]) == 3
    assert s["approval_number"] == "2026-ETH-00001"


def test_determinism(tmp_path):
    r1 = _run("--n", "2", "--out-dir", str(tmp_path))
    assert r1.returncode == 0
    a = json.loads((tmp_path / "LIFE-BT-000.json").read_text(encoding="utf-8"))
    b = json.loads((SURVEY_DIR / "LIFE-BT-000.json").read_text(encoding="utf-8"))
    # trial content (arm pairs, order_seq, texts) identical; only generated_at differs
    assert a["trials"] == b["trials"]
    assert a["arm_order"] == b["arm_order"]
