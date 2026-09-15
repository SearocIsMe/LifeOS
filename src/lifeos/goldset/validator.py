"""Structural validation for human-authored gold sets (design doc 03 §5.1).

HONEST BOUNDARY (03 doc §1.2/§5): a validator checks STRUCTURE, quotas,
uniqueness, lengths and CJK ratio - it CANNOT verify that text was written by
a human, nor semantic quality (atomicity, answer uniqueness). Those belong to
the dual-review process. The validator supports the process; it does not
replace it, and review signatures are enforced only at registration time.
"""

from __future__ import annotations

import re
import string
import unicodedata
from typing import Any

# Quotas are engineering floors (roadmap §1.2 source class (b)), calibratable
# via ADR; the validator enforces them so coverage regressions are visible.
CORE_FACT_TOTAL = 50
CORE_FACT_QUOTAS: dict[str, int] = {
    "identity_core": 8,
    "biography": 10,
    "preference": 10,
    "relationship": 8,
    "habit_routine": 7,
    "value_belief": 4,
    "sensitive_cases": 3,
}
CORE_FACT_CATEGORIES = set(CORE_FACT_QUOTAS)
SENSITIVE_RANGE = (3, 5)
EPISODIC_RANGE = (10, 15)

SCENARIO_TOTAL = 30
SITUATION_TAGS = ("normal", "low_energy", "high_social_need", "post_conflict", "sensitive_present")
SCENARIO_TAG_QUOTAS = {"low_energy": 3, "high_social_need": 3, "post_conflict": 3, "sensitive_present": 2}

INTENT_REGISTRY = (
    # Phase-1 provisional 6-intent registry (roadmap §1.2); changes via ADR.
    "greet",
    "comfort",
    "play_invite",
    "share_observation",
    "respect_space",
    "reconnect",
)

_FACT_ID_RE = re.compile(r"^CF-\d{3}$")
_SCENARIO_ID_RE = re.compile(r"^BS-\d{3}$")
_SLOT_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")


def _cjk_ratio(text: str) -> float:
    chars = [c for c in text if not c.isspace()]
    if not chars:
        return 0.0
    cjk = sum(1 for c in chars if "\u3400" <= c <= "\u9fff")
    return cjk / len(chars)


_PUNCT = set(string.punctuation + string.whitespace + "。，、；：？！「」『』（）《》—…·")


def _normalize(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKC", text.lower()) if c not in _PUNCT)


def _bigrams(text: str) -> set[str]:
    norm = _normalize(text)
    return {norm[i : i + 2] for i in range(len(norm) - 1)}


def _overlap_ratio(a: str, b: str) -> float:
    ga, gb = _bigrams(a), _bigrams(b)
    if not ga or not gb:
        return 0.0
    return len(ga & gb) / min(len(ga), len(gb))


def _require(condition: bool, errors: list[str], message: str) -> None:
    if not condition:
        errors.append(message)


def validate_core_facts(data: dict[str, Any], *, expect_count: int = CORE_FACT_TOTAL) -> dict[str, Any]:
    """Validate a core-facts gold set document (design doc 03 §3)."""
    errors: list[str] = []
    warnings: list[str] = []

    items = data.get("items")
    _require(isinstance(items, list), errors, "`items` must be a list")
    if not isinstance(items, list):
        return {"kind": "core_facts", "valid": False, "errors": errors, "warnings": warnings, "stats": {}}

    _require(
        data.get("kind") == "core_facts", errors, "`kind` must be 'core_facts'"
    )
    _require(
        data.get("language") == "zh", errors, "`language` must be 'zh' (Chinese-locked, spec §9.6)"
    )
    _require(
        data.get("fictional") is True,
        errors,
        "`fictional: true` required - materials must be persona-fiction (03 doc §2.3)",
    )
    _require(len(items) == expect_count, errors, f"expected exactly {expect_count} items, got {len(items)}")

    seen_ids: set[str] = set()
    seen_content: dict[str, str] = {}
    seen_qa: dict[str, str] = {}
    seen_slots: set[tuple[str, str]] = set()
    cat_counts: dict[str, int] = {}
    sensitive_count = 0
    episodic_count = 0

    for idx, item in enumerate(items, start=1):
        tag = f"item#{idx}"
        fact_id = item.get("fact_id", "")
        _require(bool(_FACT_ID_RE.match(fact_id)), errors, f"{tag}: bad fact_id {fact_id!r} (CF-###)")
        if fact_id in seen_ids:
            errors.append(f"{tag}: duplicate fact_id {fact_id}")
        seen_ids.add(fact_id)

        category = item.get("category", "")
        _require(
            category in CORE_FACT_CATEGORIES or category == "sensitive_cases",
            errors,
            f"{fact_id}: unknown category {category!r}",
        )
        cat_counts[category] = cat_counts.get(category, 0) + 1

        mtype = item.get("type", "")
        _require(mtype in ("semantic", "episodic"), errors, f"{fact_id}: bad type {mtype!r}")
        if mtype == "episodic":
            episodic_count += 1
        if category == "sensitive_cases":
            sensitive_count += 1

        subject = item.get("subject_id", "")
        _require(bool(subject) and re.fullmatch(r"[a-z][a-z0-9_]*", subject), errors, f"{fact_id}: bad subject_id")

        slot = item.get("slot_key")
        if mtype == "semantic":
            _require(bool(slot) and bool(_SLOT_RE.match(slot or "")), errors, f"{fact_id}: semantic needs slot_key like 'user.pet_name'")
        else:
            _require(slot in (None, ""), errors, f"{fact_id}: episodic must not carry slot_key")
        if slot:
            key = (subject, slot)
            _require(key not in seen_slots, errors, f"{fact_id}: duplicate (subject_id, slot_key) {key}")
            seen_slots.add(key)

        content = item.get("content", "")
        _require(8 <= len(content) <= 50, errors, f"{fact_id}: content length must be 8..50 chars, got {len(content)}")
        ratio = _cjk_ratio(content)
        _require(ratio > 0.6, errors, f"{fact_id}: content Chinese ratio {ratio:.2f} <= 0.6")
        norm = _normalize(content)
        if norm in seen_content:
            errors.append(f"{fact_id}: duplicate content of {seen_content[norm]}")
        seen_content[norm] = fact_id

        probes = item.get("qa_probe")
        _require(isinstance(probes, list) and 1 <= len(probes) <= 2, errors, f"{fact_id}: qa_probe must be a list of 1..2")
        if isinstance(probes, list):
            for probe in probes:
                _require(5 <= len(probe) <= 30, errors, f"{fact_id}: qa_probe length must be 5..30 chars")
                _require(_cjk_ratio(probe) > 0.6, errors, f"{fact_id}: qa_probe not Chinese enough")
                pnorm = _normalize(probe)
                if pnorm in seen_qa:
                    errors.append(f"{fact_id}: duplicate qa_probe of {seen_qa[pnorm]}")
                seen_qa[pnorm] = fact_id
                ov = _overlap_ratio(content, probe)
                if ov >= 0.5:
                    warnings.append(f"{fact_id}: probe/content bigram overlap {ov:.2f} >= 0.5 (rephrase; 03 doc §3.4-4)")

        privacy = item.get("privacy_level", "")
        _require(
            privacy in ("public", "normal", "personal", "sensitive"),
            errors,
            f"{fact_id}: bad privacy_level {privacy!r}",
        )
        importance = item.get("importance")
        _require(isinstance(importance, int) and 1 <= importance <= 5, errors, f"{fact_id}: importance must be int 1..5")

    # Set-level quotas are enforced only for the real 50-item set; templates
    # validated with a different expect_count keep all per-item checks but skip
    # the quota math (they are format demos, not the measured material).
    if expect_count == CORE_FACT_TOTAL:
        for category, quota in CORE_FACT_QUOTAS.items():
            got = cat_counts.get(category, 0)
            _require(got == quota, errors, f"category quota {category}: expected {quota}, got {got}")
        _require(
            SENSITIVE_RANGE[0] <= sensitive_count <= SENSITIVE_RANGE[1],
            errors,
            f"sensitive_cases count must be {SENSITIVE_RANGE[0]}..{SENSITIVE_RANGE[1]}, got {sensitive_count}",
        )
        _require(
            EPISODIC_RANGE[0] <= episodic_count <= EPISODIC_RANGE[1],
            errors,
            f"episodic count must be {EPISODIC_RANGE[0]}..{EPISODIC_RANGE[1]}, got {episodic_count}",
        )

    review = data.get("review") or {}
    author, reviewer = review.get("author", ""), review.get("reviewer", "")
    if not author or not reviewer:
        warnings.append("review signatures missing (required at registration; 03 doc §5.1-9)")
    elif author == reviewer:
        errors.append("review.author must differ from review.reviewer (dual-review)")

    stats = {
        "total": len(items),
        "categories": cat_counts,
        "sensitive": sensitive_count,
        "episodic": episodic_count,
        "unique_contents": len(seen_content),
        "unique_probes": len(seen_qa),
    }
    return {"kind": "core_facts", "valid": not errors, "errors": errors, "warnings": warnings, "stats": stats}


def validate_behavior_scenarios(data: dict[str, Any], *, expect_count: int = SCENARIO_TOTAL) -> dict[str, Any]:
    """Validate a behavior-scenario gold set document (design doc 03 §4)."""
    errors: list[str] = []
    warnings: list[str] = []

    items = data.get("items")
    _require(isinstance(items, list), errors, "`items` must be a list")
    if not isinstance(items, list):
        return {"kind": "behavior_scenario", "valid": False, "errors": errors, "warnings": warnings, "stats": {}}

    _require(data.get("kind") == "behavior_scenario", errors, "`kind` must be 'behavior_scenario'")
    _require(data.get("language") == "zh", errors, "`language` must be 'zh'")
    _require(data.get("fictional") is True, errors, "`fictional: true` required")
    _require(len(items) == expect_count, errors, f"expected exactly {expect_count} items, got {len(items)}")

    seen_ids: set[str] = set()
    intent_counts: dict[str, int] = {}
    tag_counts: dict[str, int] = {}

    for idx, item in enumerate(items, start=1):
        tag = f"item#{idx}"
        sid = item.get("scenario_id", "")
        _require(bool(_SCENARIO_ID_RE.match(sid)), errors, f"{tag}: bad scenario_id {sid!r}")
        if sid in seen_ids:
            errors.append(f"{tag}: duplicate scenario_id {sid}")
        seen_ids.add(sid)

        intent = item.get("intent_target", "")
        _require(intent in INTENT_REGISTRY, errors, f"{sid}: intent_target {intent!r} not in registry")
        intent_counts[intent] = intent_counts.get(intent, 0) + 1

        preset = item.get("state_preset") or {}
        for key, value in preset.items():
            _require(
                key in ("energy", "social_need", "security", "curiosity", "playfulness"),
                errors,
                f"{sid}: unknown state key {key!r}",
            )
            _require(
                isinstance(value, (int, float)) and 0.0 <= float(value) <= 1.0,
                errors,
                f"{sid}: state_preset {key} must be in [0,1]",
            )

        situation = item.get("situation_tag", "normal")
        _require(situation in SITUATION_TAGS, errors, f"{sid}: situation_tag {situation!r} invalid")
        tag_counts[situation] = tag_counts.get(situation, 0) + 1

        utterance = item.get("utterance", "")
        _require(5 <= len(utterance) <= 40, errors, f"{sid}: utterance length must be 5..40 chars, got {len(utterance)}")
        _require(_cjk_ratio(utterance) > 0.6, errors, f"{sid}: utterance not Chinese enough")

        _require(item.get("repeats") == 3, errors, f"{sid}: repeats must be 3 (per-scenario measurement protocol)")

    if expect_count == SCENARIO_TOTAL:
        for intent in INTENT_REGISTRY:
            got = intent_counts.get(intent, 0)
            _require(got >= 3, errors, f"intent coverage {intent}: need >=3 scenarios, got {got}")
        for situation, quota in SCENARIO_TAG_QUOTAS.items():
            got = tag_counts.get(situation, 0)
            _require(got >= quota, errors, f"situation coverage {situation}: need >={quota}, got {got}")

    review = data.get("review") or {}
    author, reviewer = review.get("author", ""), review.get("reviewer", "")
    if not author or not reviewer:
        warnings.append("review signatures missing (required at registration)")
    elif author == reviewer:
        errors.append("review.author must differ from review.reviewer (dual-review)")

    stats = {"total": len(items), "intents": intent_counts, "situations": tag_counts}
    return {"kind": "behavior_scenario", "valid": not errors, "errors": errors, "warnings": warnings, "stats": stats}


def validate_document(kind: str, data: dict[str, Any], *, expect_count: int | None = None) -> dict[str, Any]:
    if kind == "core_facts":
        return validate_core_facts(data, expect_count=expect_count or CORE_FACT_TOTAL)
    if kind == "behavior_scenario":
        return validate_behavior_scenarios(data, expect_count=expect_count or SCENARIO_TOTAL)
    raise ValueError(f"unsupported gold set kind: {kind!r}")
