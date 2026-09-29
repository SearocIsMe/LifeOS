"""Context Assembly pure function (design doc 01 §2.1).

Architecture §5.7 benchmark differentiation: pure function + versioned
template + SAME SNAPSHOT => SAME PROMPT. This is the precondition for
cross-model intent-consistency measurement: prompt_hash is SHA-256 over
canonical JSON of ALL inputs plus the template id, so identical inputs
across Provider A/B are bit-comparable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from lifeos.assembly.templates import get_template
from lifeos.events.protocol import canonical_json, sha256_hex


class AssemblyError(ValueError):
    """Raised for invalid assembly inputs (fail-closed)."""


@dataclass(frozen=True)
class ContextAssemblyResult:
    """Output of one assembly (pure; no side effects)."""

    system_prompt: str
    prompt_template_id: str
    prompt_hash: str


def _fmt_relationships(scores: Mapping[str, Any]) -> str:
    if not scores:
        return "（暂无）"
    parts = []
    for subject_id, s in sorted(scores.items()):
        parts.append(
            f"{subject_id}: 熟悉={s['familiarity']:.2f}, "
            f"信任={s['trust']:.2f}, 依恋={s['attachment']:.2f}"
        )
    return "；".join(parts)


def _fmt_memories(bundle: Mapping[str, Any]) -> str:
    memories = bundle.get("memories") or []
    if not memories:
        return "（暂无）"
    parts = []
    for m in memories:
        slot = f"[{m['slot_key']}]" if m.get("slot_key") else ""
        parts.append(f"{slot}{m['content']}")
    return "；".join(parts)


def assemble(
    contract: Mapping[str, Any],
    state_summary: Mapping[str, float],
    recall_bundle: Mapping[str, Any],
    relationship_scores: Mapping[str, Any],
    prompt_template_id: str,
    intent_constraints: Mapping[str, Any] | None = None,
) -> ContextAssemblyResult:
    """Build the system prompt from a frozen read view (pure function).

    Every input must be JSON-serializable; the hash covers all inputs and
    the template id. Any input change => different hash (design doc 02
    §2 S2 acceptance).
    """
    template = get_template(prompt_template_id)  # fail-closed on unknown id

    required_states = ("energy", "social_need", "security", "valence", "arousal")
    missing = [k for k in required_states if k not in state_summary]
    if missing:
        raise AssemblyError(f"state_summary missing keys: {missing}")

    personality_summary = contract.get("summary") or contract.get("personality_seed") or "（冻结）"

    try:
        system_prompt = template.format(
            energy=state_summary["energy"],
            social_need=state_summary["social_need"],
            security=state_summary["security"],
            valence=state_summary["valence"],
            arousal=state_summary["arousal"],
            personality_summary=personality_summary,
            relationships=_fmt_relationships(relationship_scores),
            memories=_fmt_memories(recall_bundle),
        )
    except (KeyError, ValueError, TypeError) as exc:
        raise AssemblyError(f"template render failed: {exc}") from exc

    hash_payload = {
        "contract": dict(contract),
        "state_summary": dict(state_summary),
        "recall_bundle": {
            "memories": list(recall_bundle.get("memories") or ()),
            "summary": recall_bundle.get("summary", ""),
        },
        "relationship_scores": {k: dict(v) for k, v in relationship_scores.items()},
        "intent_constraints": dict(intent_constraints) if intent_constraints else None,
        "prompt_template_id": prompt_template_id,
    }
    prompt_hash = sha256_hex(canonical_json(hash_payload))
    return ContextAssemblyResult(
        system_prompt=system_prompt,
        prompt_template_id=prompt_template_id,
        prompt_hash=prompt_hash,
    )
