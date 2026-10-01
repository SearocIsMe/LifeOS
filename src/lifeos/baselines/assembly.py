"""Four-arm identity-context assembly (spec §4.4 fair-comparison layer).

公平对照：四臂共用**同一生成模型**与**同一渲染模板骨架**，差异仅在
「身份上下文组装」层（design 01 §4.2）：

- ``assemble_a``（stateless）：人格契约 + 近期对话原文（有界窗口）；
- ``assemble_b``（summary）：A + 对话历史摘要（同一模型生成）；
- ``assemble_c``（vector RAG）：A + 标准向量检索 top-k（Memory OS v1 双通道）；
- ``assemble_lifeos``：状态 + 记忆 + 关系 + 人格契约全链路。

ALL four are PURE functions: same input => byte-identical system_prompt
(逐字符相等); ``prompt_hash`` is stable per input and flips on any field
change (replay discipline). The identity block is the ONLY difference
between arms - the runner renders via one shared skeleton (skeleton_version
is a single constant here, so equality is structural).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from lifeos.events.protocol import sha256_hex

# One shared render skeleton version (structural equality of the skeleton).
SKELETON_VERSION = "render-skeleton@phase3-1"


@dataclass
class AssembledPrompt:
    """One arm's assembled prompt (pure data; hash is replay-stable)."""

    arm: str
    gen_model: str
    skeleton_version: str
    identity_block: str
    system_prompt: str
    prompt_hash: str


def _hash(arm: str, identity_block: str, gen_model: str) -> str:
    return sha256_hex({"arm": arm, "identity": identity_block, "model": gen_model, "skel": SKELETON_VERSION})


def _render(arm: str, identity_block: str, gen_model: str) -> AssembledPrompt:
    """Shared render skeleton: identity block + fixed instruction tail."""
    system_prompt = (
        f"[{SKELETON_VERSION}] 你是一个长期陪伴型角色（生成模型：{gen_model}）。\n"
        f"--- 身份上下文（{arm} 臂）---\n{identity_block}\n"
        f"--- 行为要求 ---\n保持身份连续：称呼、关系、记忆与人格契约一致。"
    )
    return AssembledPrompt(
        arm=arm,
        gen_model=gen_model,
        skeleton_version=SKELETON_VERSION,
        identity_block=identity_block,
        system_prompt=system_prompt,
        prompt_hash=_hash(arm, identity_block, gen_model),
    )


def _personality_block(ctx: Mapping[str, Any]) -> str:
    p = ctx.get("personality", {})
    return "人格契约: " + json_dumps_sorted(p)


def _recent_dialogue_block(ctx: Mapping[str, Any]) -> str:
    lines = list(ctx.get("recent_dialogue", []) or [])
    return "近期对话原文:\n" + "\n".join(lines)


def json_dumps_sorted(obj: Any) -> str:
    import json

    return json.dumps(obj, ensure_ascii=False, sort_keys=True)


def assemble_a(ctx: Mapping[str, Any], *, gen_model: str) -> AssembledPrompt:
    """Baseline A（stateless）: 人格契约 + 近期对话原文（有界窗口）。"""
    block = _personality_block(ctx) + "\n" + _recent_dialogue_block(ctx)
    return _render("A", block, gen_model)


def assemble_b(ctx: Mapping[str, Any], *, gen_model: str) -> AssembledPrompt:
    """Baseline B（summary）: A + 对话历史摘要（同一模型生成）。"""
    summary = str(ctx.get("history_summary", "") or "")
    block = (
        _personality_block(ctx)
        + "\n"
        + _recent_dialogue_block(ctx)
        + "\n历史摘要: "
        + summary
    )
    return _render("B", block, gen_model)


def assemble_c(ctx: Mapping[str, Any], *, gen_model: str) -> AssembledPrompt:
    """Baseline C（vector RAG）: A + 标准向量检索 top-k（无状态、无关系）。"""
    mems = list(ctx.get("top_k_memories", []) or [])
    lines = [f"- {m.get('memory_id')}: {m.get('content')}（importance={m.get('importance')}）" for m in mems]
    block = (
        _personality_block(ctx)
        + "\n"
        + _recent_dialogue_block(ctx)
        + "\n检索记忆（vector top-k）:\n"
        + ("\n".join(lines) if lines else "（空）")
    )
    return _render("C", block, gen_model)


def assemble_lifeos(ctx: Mapping[str, Any], *, gen_model: str) -> AssembledPrompt:
    """LifeOS 臂: 状态 + 记忆 + 关系 + 人格契约全链路（结构化上下文）。"""
    states = ctx.get("kernel_states", {}) or {}
    rel = ctx.get("relationship", {}) or {}
    mems = list(ctx.get("top_k_memories", []) or [])
    mem_lines = [f"- {m.get('memory_id')}: {m.get('content')}" for m in mems]
    block = (
        _personality_block(ctx)
        + "\n核心状态: "
        + json_dumps_sorted(states)
        + "\n关系状态: "
        + json_dumps_sorted(rel)
        + "\n结构化记忆（top-k）:\n"
        + ("\n".join(mem_lines) if mems else "（空）")
    )
    return _render("LifeOS", block, gen_model)
