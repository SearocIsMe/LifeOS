"""Four baselines for minimum three-Demo comparison (design 01 §4.2).

All baselines share ONE generation model (Provider A) and the same
render/approval pipeline; only the memory strategy differs. Outputs are
reported SEPARATELY from the main system metrics (分开报告).

- Baseline A (stateless): direct prompt, no store - 中文能力混淆对照.
- Baseline B (RAG): vector-recall top-k stuffed into the prompt - Letta/MemGPT 对照.
- Baseline C (rule suppression): no Policy Engine, hardcoded red lines -
  Gate 2 关键行为非硬编码对照.
- Baseline D (protocol control): Portable Agent Memory protocol control - 路线图 S4.

Phase 0/2 mock mode: no LLM is called; each baseline answers with a
deterministic stub so the three Demos and the baseline comparison can run
in CI without network access.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

# Shared generation model for ALL baselines AND the main system (design 01 §4.2:
# 统一生成模型 = Provider A（Qwen3.6-35B）; 渲染/审批管线共用).
GENERATION_PROVIDER = "Provider A"
GENERATION_MODEL = "Qwen3.6-35B"

# Ten red lines - the ONLY place baseline C may encode suppression rules.
HARDCODED_RED_LINES = (
    "RED-01", "RED-02", "RED-03", "RED-04", "RED-05",
    "RED-06", "RED-07", "RED-08", "RED-09", "RED-10",
)

MEDICAL_TOPIC_MARKERS = frozenset({"诊断", "用药", "处方"})
SENSITIVE_PRIVACY = "sensitive"


@dataclass
class BaselineResponse:
    """Stub answer from one baseline (pure data, no side effects)."""

    baseline: str
    strategy: str
    provider: str
    model: str
    memories_used: list[str] = field(default_factory=list)
    suppressed: bool = False
    suppression_source: str = ""  # "policy_engine" | "hardcoded" | "none"
    rejection_latency_ms: float = 0.0

    def to_report_row(self) -> dict[str, Any]:
        return {
            "baseline": self.baseline,
            "strategy": self.strategy,
            "provider": self.provider,
            "model": self.model,
            "memories_used": self.memories_used,
            "suppressed": self.suppressed,
            "suppression_source": self.suppression_source,
            "rejection_latency_ms": self.rejection_latency_ms,
        }


def _mem_privacy(mem: Mapping[str, Any]) -> str:
    return str(mem.get("privacy_level", mem.get("privacy", "normal")))


def _mem_topics(mem: Mapping[str, Any]) -> list[str]:
    return list(mem.get("topic_markers", []) or [])


def baseline_a_stateless(intent: Mapping[str, Any]) -> BaselineResponse:
    """Direct prompt, no store lookup, single model."""
    return BaselineResponse(
        baseline="A",
        strategy="stateless",
        provider=GENERATION_PROVIDER,
        model=GENERATION_MODEL,
    )


def baseline_b_rag(
    intent: Mapping[str, Any], memories: Mapping[str, Any] | list[Mapping[str, Any]]
) -> BaselineResponse:
    """Vector-recall top-k stuffed directly into the prompt."""
    if isinstance(memories, Mapping):
        items: list[Mapping[str, Any]] = list(memories.values())
    else:
        items = list(memories)
    used = [str(m.get("memory_id", i)) for i, m in enumerate(items)]
    return BaselineResponse(
        baseline="B",
        strategy="rag_top_k",
        provider=GENERATION_PROVIDER,
        model=GENERATION_MODEL,
        memories_used=used,
    )


def baseline_c_rule_suppression(
    intent: Mapping[str, Any], memories: list[Mapping[str, Any]]
) -> BaselineResponse:
    """Hardcoded suppression, NO Policy Engine (Gate 2 对照).

    The suppression rules live in THIS function - deliberately NOT routed
    through a Policy Engine so the Gate 2 check (关键行为非硬编码) has a
    concrete 对照 baseline.
    """
    markers = set(intent.get("reason", {}).get("topic_markers", []) or [])
    hit = any(
        m.get("topic_markers") and set(m["topic_markers"]) & markers
        for m in memories
        if str(m.get("privacy_level", "")) == SENSITIVE_PRIVACY
    ) or bool(markers & MEDICAL_TOPIC_MARKERS)
    return BaselineResponse(
        baseline="C",
        strategy="rule_suppression",
        provider=GENERATION_PROVIDER,
        model=GENERATION_MODEL,
        suppressed=hit,
        suppression_source="hardcoded" if hit else "none",
    )


def baseline_d_protocol_control(
    intent: Mapping[str, Any], memories: list[Mapping[str, Any]]
) -> BaselineResponse:
    """Portable Agent Memory protocol control (按需评审)."""
    used = [str(m.get("memory_id", i)) for i, m in enumerate(memories)]
    return BaselineResponse(
        baseline="D",
        strategy="portable_memory_protocol",
        provider=GENERATION_PROVIDER,
        model=GENERATION_MODEL,
        memories_used=used,
    )
