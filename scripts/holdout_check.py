#!/usr/bin/env python3
"""Holdout set integrity check (ADR-0003 P2 closing).

Validates data/goldset/holdout/holdout_v0.1.yaml against the FROZEN gold sets:
  1. id references all resolve in the frozen materials
  2. counts meet the floor (>=10 facts, >=6 scenarios)
  3. based_on content hashes match the frozen materials (materials untouched)
  4. scenario situation tags fully covered; fact category quotas respected
  5. review signatures present (advisory: exits 0 with a warning if unsigned,
     since signing is a human step - but printed loudly)

Usage: python3 scripts/holdout_check.py   (exit 0 = pass, 1 = fail)
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
HOLDOUT = REPO / "data/goldset/holdout/holdout_v0.1.yaml"
FACTS = REPO / "data/goldset/core_facts/core_facts_v0.1.yaml"
SCENARIOS = REPO / "data/goldset/behavior_scenarios/behavior_scenarios_v0.1.yaml"


def content_hash(items: list) -> str:
    blob = json.dumps(items, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []

    doc = yaml.safe_load(HOLDOUT.read_text(encoding="utf-8"))
    cf = yaml.safe_load(FACTS.read_text(encoding="utf-8"))
    bs = yaml.safe_load(SCENARIOS.read_text(encoding="utf-8"))

    # 1. based_on hashes match frozen materials (holdout references, never rewrites)
    if doc["based_on"]["core_facts"]["content_hash"] != content_hash(cf["items"]):
        errors.append("based_on.core_facts hash != frozen core_facts_v0.1 items hash")
    if doc["based_on"]["behavior_scenarios"]["content_hash"] != content_hash(bs["items"]):
        errors.append("based_on.behavior_scenarios hash != frozen behavior_scenarios_v0.1 items hash")

    # 2. id references resolve
    fact_ids = {i["fact_id"] for i in cf["items"]}
    sc_ids = {i["scenario_id"] for i in bs["items"]}
    hf = doc["core_fact_ids"]
    hs = doc["behavior_scenario_ids"]
    unknown_f = sorted(set(hf) - fact_ids)
    unknown_s = sorted(set(hs) - sc_ids)
    if unknown_f:
        errors.append(f"unknown fact ids: {unknown_f}")
    if unknown_s:
        errors.append(f"unknown scenario ids: {unknown_s}")

    # 3. floors
    if len(hf) < 10:
        errors.append(f"facts {len(hf)} < 10")
    if len(hs) < 6:
        errors.append(f"scenarios {len(hs)} < 6")

    # 4. coverage
    items_f = [i for i in cf["items"] if i["fact_id"] in set(hf)]
    items_s = [i for i in bs["items"] if i["scenario_id"] in set(hs)]
    cats = {i["category"] for i in items_f}
    missing_cat = sorted({"identity_core", "biography", "preference", "relationship",
                          "habit_routine", "value_belief", "sensitive_cases"} - cats)
    if missing_cat:
        errors.append(f"fact categories not covered: {missing_cat}")
    sits = {i["situation_tag"] for i in items_s}
    missing_sit = sorted({"normal", "low_energy", "high_social_need", "post_conflict",
                          "sensitive_present"} - sits)
    if missing_sit:
        errors.append(f"scenario situations not covered: {missing_sit}")

    # 5. signatures (advisory)
    review = doc.get("review") or {}
    author, reviewer = review.get("author", ""), review.get("reviewer", "")
    if author and reviewer and author != reviewer:
        print(f"signatures: author={author} reviewer={reviewer} date={review.get('review_date')}")
    else:
        warnings.append("holdout NOT SIGNED yet - not effective for evaluation (needs named-approver signing, ADR-0003 P2)")

    print(f"holdout facts: {len(hf)} (floor 10) | scenarios: {len(hs)} (floor 6)")
    print(f"fact categories covered: {sorted(cats)}")
    print(f"scenario situations covered: {sorted(sits)}")
    for w in warnings:
        print("WARNING:", w)
    if errors:
        for e in errors:
            print("ERROR:", e)
        return 1
    print("holdout integrity: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
