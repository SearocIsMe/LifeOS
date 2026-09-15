"""Tier-A acceptance cases (AC-03..AC-08) via the same checks the CLI exposes.

Keeping one implementation of each assertion (in ``lifeos.cli``) means the
documented acceptance commands and the pytest suite can never disagree.
"""

from __future__ import annotations

import pytest

from lifeos.cli import (
    verify_boundary,
    verify_isolation,
    verify_policy,
    verify_replay,
    verify_roundtrip,
    verify_schema,
)


@pytest.mark.parametrize(
    "check,case",
    [
        (verify_schema, "AC-03 schema round-trip"),
        (verify_roundtrip, "AC-04 pipeline round-trip"),
        (verify_replay, "AC-05 replay 100% consistency"),
        (verify_policy, "AC-07 policy rejection zero side effects"),
        (verify_boundary, "AC-06 LLM output cannot write authoritative tables"),
        (verify_isolation, "AC-08 multi-instance isolation"),
    ],
)
def test_acceptance(check, case):
    result = check()
    assert result["status"] == "pass", f"{case} failed: {result['detail']}"
