"""T5.1 acceptance: real-arm runner CI coverage (mock mode, exit code = verdict).

Case map:
- runner mock PASS      -> 30 frozen probes x 4 arms, exit 0, reports written
- real fail-closed      -> --mode real without --base-url => exit 1 (no pre-run)
- reports structure     -> per-arm rows carry prompt_hash/provenance/policy_result
- determinism           -> same run twice => identical comparison_real summary
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RUNNER = REPO / "scripts" / "demo" / "run_baselines_real.py"
REPORT_DIR = REPO / "reports" / "baselines"


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(RUNNER), *args],
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_runner_mock_pass_30_probes():
    r = _run("--mode", "mock")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "PASS (mock, 30 probes x 4 arms" in r.stdout


def test_runner_real_fail_closed_without_base_url():
    r = _run("--mode", "real")
    assert r.returncode == 1  # no pre-run (checklist pending)
    assert "requires --base-url" in r.stdout


def test_reports_written_with_provenance():
    r = _run("--mode", "mock", "--limit", "3")
    assert r.returncode == 0
    for arm in ("A", "B", "C", "LifeOS"):
        path = REPORT_DIR / f"baseline_{arm}_real.json"
        assert path.exists()
        d = json.loads(path.read_text(encoding="utf-8"))
        assert d["arm"] == arm and d["mode"] == "mock"
        assert len(d["rows"]) == 3
        row = d["rows"][0]
        # full-pipeline provenance (spec §3.4/§4.4)
        assert row["prompt_hash"]
        assert row["policy_result"] in ("approve", "reject")
        assert row["provenance"]["purpose"] == "baseline-real-arm"
        assert row["skeleton_version"]


def test_runner_deterministic():
    _run("--mode", "mock", "--limit", "4")
    s1 = json.loads((REPORT_DIR / "comparison_real.json").read_text(encoding="utf-8"))["summary"]
    _run("--mode", "mock", "--limit", "4")
    s2 = json.loads((REPORT_DIR / "comparison_real.json").read_text(encoding="utf-8"))["summary"]
    assert s1 == s2  # same input => same summary (replay discipline)
