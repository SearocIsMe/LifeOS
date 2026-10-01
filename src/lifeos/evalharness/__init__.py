"""LifeOS Eval Harness (Phase 1, S4): H1 intent-consistency benchmark.

Import-discipline anchor; see h1.py.
"""

from lifeos.evalharness.h1 import (
    JUDGED_FIELDS,
    CaseResult,
    H1Report,
    HarnessError,
    judge_pair,
    parse_intent,
    run_case,
    run_h1,
)

__all__ = [
    "JUDGED_FIELDS",
    "CaseResult",
    "H1Report",
    "HarnessError",
    "judge_pair",
    "parse_intent",
    "run_case",
    "run_h1",
]
