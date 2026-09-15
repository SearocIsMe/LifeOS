"""AC-09 tooling: validator + registration manifest (structure-level only).

The validator supports the HUMAN authoring process; it cannot verify human
authorship or semantic quality (03 doc §5 honest split) - these tests pin the
machine-checkable half only.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from lifeos.goldset.registry import build_manifest, content_hash
from lifeos.goldset.validator import (
    CORE_FACT_TOTAL,
    SCENARIO_TOTAL,
    validate_core_facts,
    validate_document,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_FACTS = REPO_ROOT / "data/goldset/core_facts/core_facts_template.yaml"
TEMPLATE_SCENARIOS = REPO_ROOT / "data/goldset/behavior_scenarios/behavior_scenarios_template.yaml"


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_template_examples_pass_structural_checks():
    facts = validate_core_facts(_load(TEMPLATE_FACTS), expect_count=3)
    assert facts["valid"], facts["errors"]
    scenarios = validate_document("behavior_scenario", _load(TEMPLATE_SCENARIOS), expect_count=2)
    assert scenarios["valid"], scenarios["errors"]


def test_full_set_count_is_enforced():
    data = _load(TEMPLATE_FACTS)
    report = validate_core_facts(data, expect_count=CORE_FACT_TOTAL)
    assert not report["valid"]
    assert any("expected exactly 50" in e for e in report["errors"])


def test_duplicate_fact_id_rejected():
    data = _load(TEMPLATE_FACTS)
    data["items"].append(copy.deepcopy(data["items"][0]))
    report = validate_core_facts(data, expect_count=4)
    assert not report["valid"]
    assert any("duplicate fact_id" in e for e in report["errors"])


def test_non_chinese_content_rejected():
    data = _load(TEMPLATE_FACTS)
    data["items"][0]["content"] = "The user's cat is called Mimi at home"
    report = validate_core_facts(data, expect_count=3)
    assert not report["valid"]
    assert any("Chinese ratio" in e for e in report["errors"])


def test_scenario_count_enforced():
    report = validate_document("behavior_scenario", _load(TEMPLATE_SCENARIOS), expect_count=SCENARIO_TOTAL)
    assert not report["valid"]


def test_registration_requires_dual_review_signatures():
    data = _load(TEMPLATE_FACTS)
    # expect_count=3: template-scale check. Real registration (CLI) always
    # enforces the full 50/30 - this test pins the REVIEW gate, not quotas.
    with pytest.raises(ValueError, match="dual-review"):
        build_manifest("core_facts", "0.1.0", data, expect_count=3)

    data["review"] = {"author": "alice", "reviewer": "alice"}
    with pytest.raises(ValueError, match="dual-review"):
        build_manifest("core_facts", "0.1.0", data, expect_count=3)


def test_registration_rejects_invalid_materials():
    data = _load(TEMPLATE_FACTS)
    data["items"][0]["content"] = "太短"
    with pytest.raises(ValueError, match="failed validation"):
        build_manifest("core_facts", "0.1.0", data, expect_count=3)


def test_manifest_hash_is_stable():
    data = _load(TEMPLATE_FACTS)
    data["review"] = {"author": "alice", "reviewer": "bob", "review_date": "2026-09-20"}
    m1 = build_manifest("core_facts", "0.1.0", data, expect_count=3)
    m2 = build_manifest("core_facts", "0.1.0", data, expect_count=3)
    assert m1["content_hash"] == m2["content_hash"]
    assert m1["content_hash"] == content_hash(data["items"])
    assert m1["item_count"] == 3
