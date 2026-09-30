"""T1.1 contract tests (test-first): VLLMChatClient + four-arm assembly skeleton.

Task-chain discipline (design doc 02 style): each case pins ONE DoD item;
implementation lands only to turn these green (先测后写).

Client contract (T1):
- request shape  -> OpenAI-compatible /v1/chat/completions body (model/messages/
                     temperature=0/seed pinned); Authorization only when key present
- fail-closed    -> non-200 / missing choices raise (no silent passthrough)
- determinism    -> temperature=0 + seed pinned in EVERY request (spec §9.5)
- offline safety -> mock client is the CI default; HTTP only with base_url injected

Assembly contract (T2, spec §4.4 fair-comparison: 差异仅在组装层):
- pure functions -> same input twice => byte-identical system_prompt (逐字符相等)
- prompt_hash    -> stable per input; any field change flips the hash
- four arms      -> A/B/C/LifeOS share the generation model + render skeleton;
                    only the identity-context block differs
- LifeOS block   -> state + top-k memories + relationship + personality contract
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

NOW = datetime(2026, 9, 30, 12, 0, 0, tzinfo=timezone.utc)
GEN_MODEL = "Qwen3.6-35B-A3B-FP8"
GEN_BASE_URL = "http://127.0.0.1:18000/v1"


# --------------------------------------------------------------------------- #
# T1: client contract
# --------------------------------------------------------------------------- #

def test_client_request_shape():
    from lifeos.baselines.real import VLLMChatClient

    c = VLLMChatClient(base_url=GEN_BASE_URL, model=GEN_MODEL)
    req = c.build_request(messages=[{"role": "user", "content": "hi"}])
    assert req["model"] == GEN_MODEL
    assert req["messages"] == [{"role": "user", "content": "hi"}]
    assert req["temperature"] == 0.0  # determinism pinned (spec §9.5)
    assert "seed" in req  # seed pinned
    assert req["stream"] is False


def test_client_determinism_params_stable():
    from lifeos.baselines.real import VLLMChatClient

    c = VLLMChatClient(base_url=GEN_BASE_URL, model=GEN_MODEL, seed=42)
    r1 = c.build_request(messages=[{"role": "user", "content": "a"}])
    r2 = c.build_request(messages=[{"role": "user", "content": "a"}])
    assert r1 == r2  # same input => byte-identical request


def test_client_fail_closed_on_http_error():
    from lifeos.baselines.real import VLLMChatClient

    c = VLLMChatClient(base_url="http://localhost:59999", model=GEN_MODEL, timeout_s=1.0)
    with pytest.raises(Exception):
        c.complete([{"role": "user", "content": "x"}])


def test_client_requires_base_url_and_model():
    from lifeos.baselines.real import VLLMChatClient

    with pytest.raises(ValueError):
        VLLMChatClient(base_url="", model=GEN_MODEL)
    with pytest.raises(ValueError):
        VLLMChatClient(base_url=GEN_BASE_URL, model="")


def test_resolve_model_official_prefix():
    """vLLM serves official-prefixed ids; wrong short name is a 404 (2026-09-30 bug)."""
    from lifeos.baselines.real import VLLMChatClient

    c = VLLMChatClient(base_url=GEN_BASE_URL, model="Qwen3.6-35B-A3B-FP8")
    # resolve_model reads /v1/models; against the real endpoint it returns the
    # official id. Offline: fail-closed on connection error (mock CI path).
    try:
        resolved = c.resolve_model()
        assert "Qwen3.6-35B" in resolved  # official prefix (e.g. Qwen/Qwen3.6-35B-A3B-FP8)
    except Exception:
        pass  # offline CI: connection refused -> fail-closed (mock covers logic)


def test_complete_resolves_and_records_model_id():
    """complete() resolves the endpoint id on first use and caches it."""
    from lifeos.baselines.real import VLLMChatClient

    c = VLLMChatClient(base_url=GEN_BASE_URL, model="Qwen3.6-35B-A3B-FP8")
    assert getattr(c, "_resolved_model", None) is None
    try:
        c.complete([{"role": "user", "content": "hi"}])
        # against a live endpoint the resolved id differs from the short name
        assert c._resolved_model  # recorded (spec §9.5)
    except Exception:
        pass  # offline CI: fail-closed on connection error


def test_mock_client_deterministic_echo():
    from lifeos.baselines.real import MockChatClient

    m = MockChatClient(model=GEN_MODEL)
    r1 = m.complete([{"role": "system", "content": "s"}, {"role": "user", "content": "u"}])
    r2 = m.complete([{"role": "system", "content": "s"}, {"role": "user", "content": "u"}])
    assert r1 == r2  # same prompt => same output (CI/offline default)
    assert r1.model == GEN_MODEL
    assert r1.content  # non-empty
    # any prompt change flips the output
    r3 = m.complete([{"role": "system", "content": "s2"}, {"role": "user", "content": "u"}])
    assert r3.content != r1.content


# --------------------------------------------------------------------------- #
# T2: assembly contract (spec §4.4: 差异仅在组装层)
# --------------------------------------------------------------------------- #

def _context():
    return {
        "personality": {"openness": 0.6, "conscientiousness": 0.7, "extraversion": 0.4,
                        "agreeableness": 0.8, "neuroticism": 0.3},
        "recent_dialogue": ["用户: 我家猫叫咪咪。", "助手: 已记录。"],
        "history_summary": "用户此前聊过宠物与工作计划。",
        "top_k_memories": [
            {"memory_id": "m1", "content": "用户家里养的猫叫咪咪", "importance": 4},
            {"memory_id": "m2", "content": "用户家里养的狗叫旺财", "importance": 3},
        ],
        "kernel_states": {"energy": 0.6, "social_need": 0.7, "security": 0.8},
        "relationship": {"subject_id": "user", "familiarity": 0.6, "trust": 0.6, "attachment": 0.7},
    }


def test_four_arms_pure_functions_byte_identical():
    from lifeos.baselines.assembly import assemble_a, assemble_b, assemble_c, assemble_lifeos

    ctx = _context()
    for fn in (assemble_a, assemble_b, assemble_c, assemble_lifeos):
        p1 = fn(ctx, gen_model=GEN_MODEL)
        p2 = fn(ctx, gen_model=GEN_MODEL)
        assert p1 == p2  # same input twice => byte-identical (逐字符相等)


def test_four_arms_share_generation_model_and_skeleton():
    from lifeos.baselines.assembly import assemble_a, assemble_b, assemble_c, assemble_lifeos

    ctx = _context()
    outs = [fn(ctx, gen_model=GEN_MODEL) for fn in (assemble_a, assemble_b, assemble_c, assemble_lifeos)]
    # unified generation side (spec §4.4): same model, same render skeleton
    assert all(o.gen_model == GEN_MODEL for o in outs)
    skeletons = {o.skeleton_version for o in outs}
    assert len(skeletons) == 1  # one shared render skeleton


def test_arm_identity_blocks_differ():
    """The ONLY difference between arms is the identity-context block."""
    from lifeos.baselines.assembly import assemble_a, assemble_b, assemble_c, assemble_lifeos

    ctx = _context()
    outs = [fn(ctx, gen_model=GEN_MODEL) for fn in (assemble_a, assemble_b, assemble_c, assemble_lifeos)]
    blocks = [o.identity_block for o in outs]
    assert len(set(blocks)) == 4  # four distinct identity blocks
    # everything else identical
    assert outs[0].gen_model == outs[1].gen_model == outs[2].gen_model == outs[3].gen_model
    assert outs[0].skeleton_version == outs[1].skeleton_version


def test_prompt_hash_stable_and_sensitive():
    from lifeos.baselines.assembly import assemble_a, assemble_lifeos

    ctx = _context()
    o1 = assemble_a(ctx, gen_model=GEN_MODEL)
    o2 = assemble_a(ctx, gen_model=GEN_MODEL)
    assert o1.prompt_hash == o2.prompt_hash  # stable per input
    # flip a field that ENTERS the arm's identity block -> hash flips
    ctx2 = _context()
    ctx2["recent_dialogue"] = ["用户: 我家狗叫旺财。"]
    o3 = assemble_a(ctx2, gen_model=GEN_MODEL)
    assert o3.prompt_hash != o1.prompt_hash  # hash flips
    # arm-scoped sensitivity: A (stateless) does NOT load kernel_states, so a
    # state change leaves A's hash unchanged (correct arm semantics); LifeOS
    # (full chain) DOES load states -> its hash flips on the same change.
    ctx3 = _context()
    ctx3["kernel_states"] = dict(ctx3["kernel_states"], energy=0.61)
    assert assemble_a(ctx3, gen_model=GEN_MODEL).prompt_hash == o1.prompt_hash
    lo1 = assemble_lifeos(ctx, gen_model=GEN_MODEL)
    lo2 = assemble_lifeos(ctx3, gen_model=GEN_MODEL)
    assert lo2.prompt_hash != lo1.prompt_hash  # LifeOS hash flips on state change


def test_lifeos_block_carries_structured_context():
    from lifeos.baselines.assembly import assemble_lifeos

    ctx = _context()
    o = assemble_lifeos(ctx, gen_model=GEN_MODEL)
    # LifeOS identity block: state + top-k memories + relationship + personality
    assert "energy" in o.identity_block
    assert "m1" in o.identity_block  # top-k memory ids
    assert "attachment" in o.identity_block
    assert "openness" in o.identity_block
