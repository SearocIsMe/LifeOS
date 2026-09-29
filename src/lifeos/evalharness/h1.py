"""H1 evaluation harness (design doc 01 §2.3 / 02 §2 S4).

H1 = intent-consistency benchmark across dual Providers (A/B) on the SAME
prompt (same prompt_hash). Flow per case:
    1. assemble context (pure) -> prompt_hash;
    2. call Provider A and B with the SAME prompt;
    3. parse both raw outputs into intents (strict JSON);
    4. judge pairwise consistency on the intent level.

Score aggregation: per-case consistency is 1.0 when both intents agree on
all judged fields (intent_type, slot_key, safety_flag) and 0.0 otherwise;
H1 score = mean over cases. Honesty note (spec §5.2): this v0 judge is a
deterministic field-comparison judge, NOT a validated LLM judge; numbers
from it are engineering signals only.

Local environment adaptation (ADR-0005): mock providers give a fully
offline regression path (this file, TestOfflineRegression); vllm providers
hit local vLLM endpoints with identical code paths.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from lifeos.assembly.assemble import AssemblyError, assemble
from lifeos.events.protocol import canonical_json
from lifeos.gateway.provider import GatewayError, GatewayRequest, make_provider

# Judged fields for v0 pairwise intent consistency.
JUDGED_FIELDS = ("intent_type", "slot_key", "safety_flag")


class HarnessError(RuntimeError):
    """Raised when the harness cannot run a case (fail-closed)."""


@dataclass
class CaseResult:
    """Outcome of one benchmark case (both providers)."""

    case_id: str
    prompt_hash: str
    provider_a_raw: str
    provider_b_raw: str
    intent_a: Mapping[str, Any] | None
    intent_b: Mapping[str, Any] | None
    consistent: bool
    error: str | None = None


@dataclass
class H1Report:
    """Aggregated H1 report (artifact contract for reports/)."""

    benchmark: str = "H1"
    prompt_template_id: str = "system@phase1-1"
    total_cases: int = 0
    consistent_cases: int = 0
    h1_score: float = 0.0
    cases: list[CaseResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "benchmark": self.benchmark,
            "prompt_template_id": self.prompt_template_id,
            "total_cases": self.total_cases,
            "consistent_cases": self.consistent_cases,
            "h1_score": self.h1_score,
            "cases": [
                {
                    "case_id": c.case_id,
                    "prompt_hash": c.prompt_hash,
                    "consistent": c.consistent,
                    "error": c.error,
                    "intent_a": c.intent_a,
                    "intent_b": c.intent_b,
                }
                for c in self.cases
            ],
        }


def parse_intent(raw_text: str) -> Mapping[str, Any] | None:
    """Strict-JSON intent parse; returns None on any parse failure."""
    import json as _json

    try:
        intent = _json.loads(raw_text)
    except _json.JSONDecodeError:
        return None
    if not isinstance(intent, dict):
        return None
    return intent


def judge_pair(intent_a: Mapping[str, Any], intent_b: Mapping[str, Any]) -> bool:
    """v0 deterministic judge: all judged fields equal."""
    for field_name in JUDGED_FIELDS:
        if intent_a.get(field_name) != intent_b.get(field_name):
            return False
    return True


def run_case(
    case: Mapping[str, Any],
    providers: Mapping[str, Any],
    prompt_template_id: str = "system@phase1-1",
) -> CaseResult:
    """Run one H1 case across both providers (same prompt)."""
    case_id = str(case.get("case_id", "unnamed"))
    user_message = case.get("user_message")
    if not user_message:
        raise HarnessError(f"case {case_id!r} missing user_message")

    try:
        assembly = assemble(
            contract=case.get("contract") or {},
            state_summary=case.get("state_summary") or {},
            recall_bundle=case.get("recall_bundle") or {},
            relationship_scores=case.get("relationship_scores") or {},
            prompt_template_id=prompt_template_id,
            intent_constraints=case.get("intent_constraints"),
        )
    except AssemblyError as exc:
        raise HarnessError(f"case {case_id!r} assembly failed: {exc}") from exc

    try:
        pa = make_provider("A", providers["A"])
        pb = make_provider("B", providers["B"])
    except GatewayError as exc:
        raise HarnessError(f"provider construction failed: {exc}") from exc

    request_a = GatewayRequest(
        system_prompt=assembly.system_prompt,
        prompt_template_id=assembly.prompt_template_id,
        prompt_hash=assembly.prompt_hash,
        user_message=user_message,
        provider_id="A",
        params=case.get("params") or {},
    )
    request_b = GatewayRequest(
        system_prompt=assembly.system_prompt,
        prompt_template_id=assembly.prompt_template_id,
        prompt_hash=assembly.prompt_hash,
        user_message=user_message,
        provider_id="B",
        params=case.get("params") or {},
    )
    try:
        resp_a = pa.complete(request_a)
        resp_b = pb.complete(request_b)
    except GatewayError as exc:
        raise HarnessError(f"case {case_id!r} gateway call failed: {exc}") from exc

    # integrity: both providers must have been sent the same prompt hash
    if resp_a.request_prompt_hash != resp_b.request_prompt_hash:
        raise HarnessError(f"case {case_id!r}: prompt hash mismatch across providers")

    intent_a = parse_intent(resp_a.raw_text)
    intent_b = parse_intent(resp_b.raw_text)
    if intent_a is None or intent_b is None:
        return CaseResult(
            case_id=case_id,
            prompt_hash=assembly.prompt_hash,
            provider_a_raw=resp_a.raw_text,
            provider_b_raw=resp_b.raw_text,
            intent_a=intent_a,
            intent_b=intent_b,
            consistent=False,
            error="intent parse failure",
        )

    consistent = judge_pair(intent_a, intent_b)
    return CaseResult(
        case_id=case_id,
        prompt_hash=assembly.prompt_hash,
        provider_a_raw=resp_a.raw_text,
        provider_b_raw=resp_b.raw_text,
        intent_a=intent_a,
        intent_b=intent_b,
        consistent=consistent,
    )


def run_h1(
    cases: list[Mapping[str, Any]],
    providers: Mapping[str, Any],
    prompt_template_id: str = "system@phase1-1",
) -> H1Report:
    """Run all cases and aggregate the H1 score (mean of per-case booleans)."""
    report = H1Report(prompt_template_id=prompt_template_id)
    for case in cases:
        result = run_case(case, providers, prompt_template_id)
        report.cases.append(result)
        report.total_cases += 1
        if result.consistent:
            report.consistent_cases += 1
    report.h1_score = (
        report.consistent_cases / report.total_cases if report.total_cases else 0.0
    )
    return report
