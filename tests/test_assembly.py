"""S2 acceptance cases: Context Assembly (design doc 02 §2 S2 table)."""

import json

import pytest

from lifeos.assembly.assemble import AssemblyError, assemble
from lifeos.assembly.templates import TemplateError, get_template

CONTRACT = {"personality_seed": "ps-001", "summary": "温和、有条理"}
STATES = {
    "energy": 0.72,
    "social_need": 0.55,
    "security": 0.8,
    "valence": 0.1,
    "arousal": 0.2,
}
RECALL = {
    "memories": [
        {"slot_key": "work_style", "content": "用户偏好早上处理深度工作"},
        {"slot_key": "family", "content": "用户妻子名字叫小红"},
    ],
    "summary": "3 条工作偏好、1 条家庭信息",
}
RELATIONS = {
    "alice": {"familiarity": 0.6, "trust": 0.55, "attachment": 0.4},
}


class TestSameSnapshotSamePrompt:
    def test_deterministic(self):
        a = assemble(CONTRACT, STATES, RECALL, RELATIONS, "system@phase1-1")
        b = assemble(CONTRACT, STATES, RECALL, RELATIONS, "system@phase-1".replace("phase-1", "phase1-1"))
        assert a.prompt_hash == b.prompt_hash
        assert a.system_prompt == b.system_prompt

    def test_hash_is_sha256_hex(self):
        r = assemble(CONTRACT, STATES, RECALL, RELATIONS, "system@phase1-1")
        assert len(r.prompt_hash) == 64
        int(r.prompt_hash, 16)  # valid hex

    def test_cross_provider_inputs_bit_comparable(self):
        # same inputs must produce identical hashes for both providers (A/B)
        r1 = assemble(CONTRACT, STATES, RECALL, RELATIONS, "system@phase1-1")
        r2 = assemble(CONTRACT, STATES, RECALL, RELATIONS, "system@phase1-1")
        assert r1.prompt_hash == r2.prompt_hash
        # serializable so it can be sent across provider A/B unmodified
        json.dumps(r1.prompt_hash)


class TestInputSensitivity:
    def test_state_change_changes_hash(self):
        r1 = assemble(CONTRACT, STATES, RECALL, RELATIONS, "system@phase1-1")
        changed = dict(STATES, energy=0.5)
        r2 = assemble(CONTRACT, changed, RECALL, RELATIONS, "system@phase1-1")
        assert r1.prompt_hash != r2.prompt_hash

    def test_memory_change_changes_hash(self):
        r1 = assemble(CONTRACT, STATES, RECALL, RELATIONS, "system@phase1-1")
        changed = {"memories": RECALL["memories"][:1], "summary": RECALL["summary"]}
        r2 = assemble(CONTRACT, STATES, changed, RELATIONS, "system@phase1-1")
        assert r1.prompt_hash != r2.prompt_hash

    def test_relationship_change_changes_hash(self):
        r1 = assemble(CONTRACT, STATES, RECALL, RELATIONS, "system@phase1-1")
        changed = {"alice": {"familiarity": 0.9, "trust": 0.55, "attachment": 0.4}}
        r2 = assemble(CONTRACT, STATES, RECALL, changed, "system@phase1-1")
        assert r1.prompt_hash != r2.prompt_hash


class TestTemplateRegistry:
    def test_registered_id_ok(self):
        t = get_template("system@phase1-1")
        assert "energy=" in t

    def test_unknown_id_fails_closed(self):
        with pytest.raises(TemplateError):
            get_template("system@unknown-9")


class TestFailClosed:
    def test_missing_state_key(self):
        bad = {k: v for k, v in STATES.items() if k != "arousal"}
        with pytest.raises(AssemblyError):
            assemble(CONTRACT, bad, RECALL, RELATIONS, "system@phase1-1")

    def test_prompt_contains_scores(self):
        r = assemble(CONTRACT, STATES, RECALL, RELATIONS, "system@phase1-1")
        assert "alice" in r.system_prompt  # relationship subject included
        assert "小红" in r.system_prompt  # memory content included
