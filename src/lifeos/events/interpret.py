"""Phase 0 rule interpreter (L0 -> L1).

HONEST DECLARATION (design doc 01 §4.2): Phase 0 does NOT interpret free text.
This is a deterministic, rule-based placeholder that consumes only the
``structured`` cues inside the L0 payload. Natural-language extraction is the
LLM interpreter's job starting Phase 1. All provenance fields required by
architecture §3.2 are produced here ("缺一不入库").
"""

from __future__ import annotations

from typing import Any

from lifeos.entities import InterpreterType, InterpretedEvent, RawEvent
from lifeos.events.protocol import derive_id, sha256_hex

RULE_TEMPLATE_ID = "rule/phase0/v0"
RULE_PROMPT_HASH_SEED = {"interpreter": "phase0-rule-v0"}

_ALLOWED_CANDIDATE_KEYS = {
    "type",
    "content",
    "slot_key",
    "subject_id",
    "confidence",
    "importance",
    "privacy_level",
    "emotion",
}


def rule_interpret(raw: RawEvent, *, extractor_version: str) -> InterpretedEvent:
    """Deterministically map structured cues to an L1 record.

    Free text (``payload.text``) is archived but NOT interpreted in Phase 0.
    Unknown keys inside ``structured`` are dropped here? - No: they are passed
    through to the output contract, where ``extra="forbid"`` fails closed. The
    interpreter must not silently rewrite the world.
    """
    structured = raw.payload.get("structured")
    structured = structured if isinstance(structured, dict) else {}

    output: dict[str, Any] = {"event_type": "user_message"}

    if "emotion" in structured:
        output["emotion"] = structured["emotion"]
    if "state_deltas" in structured:
        output["state_deltas"] = structured["state_deltas"]
    if "memory_candidates" in structured:
        # pass-through; the commit contract validates shape and ranges
        cleaned = []
        for cand in structured["memory_candidates"]:
            if not isinstance(cand, dict):
                raise ValueError("memory_candidates entries must be objects")
            unknown = set(cand) - _ALLOWED_CANDIDATE_KEYS
            if unknown:
                raise ValueError(f"unknown memory candidate keys: {sorted(unknown)}")
            cleaned.append(cand)
        output["memory_candidates"] = cleaned
    if "relationship_delta" in structured:
        output["relationship_delta"] = structured["relationship_delta"]
    if "proposed_intent" in structured:
        output["proposed_intent"] = structured["proposed_intent"]

    event_id = derive_id("L1", {"raw_event_id": raw.event_id, "output_json": output})

    return InterpretedEvent(
        event_id=event_id,
        life_id=raw.life_id,
        raw_event_id=raw.event_id,
        output_json=output,
        interpreter_type=InterpreterType.RULE,
        model_provider=None,  # rule interpreter: no model involved (Phase 0)
        model_name=None,
        model_version=None,
        prompt_template_id=RULE_TEMPLATE_ID,
        prompt_hash=sha256_hex(RULE_PROMPT_HASH_SEED),
        input_hash=sha256_hex(raw.payload),
        sampling_params={},
        extractor_version=extractor_version,
        interpreted_at=raw.occurred_at,  # deterministic; wall clock adds no value here
    )
