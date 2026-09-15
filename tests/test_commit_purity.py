"""AC-05 foundations: deterministic_commit purity contract (design 01 §4.3)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from lifeos import POLICY_VERSION, RULES_VERSION, SCHEMA_VERSION
from lifeos.events.commit import CommitError, deterministic_commit
from lifeos.events.protocol import canonical_json

T0 = datetime(2026, 9, 1, 9, 0, 0, tzinfo=timezone.utc)

OUTPUT = {
    "event_type": "user_message",
    "state_deltas": {"energy": -0.1},
    "memory_candidates": [
        {
            "type": "semantic",
            "content": "用户小林家里养的猫叫咪咪",
            "slot_key": "user.pet_name",
            "subject_id": "user",
            "confidence": 0.9,
            "importance": 4,
        }
    ],
}


def _commit(**overrides):
    kwargs = dict(
        output_json=OUTPUT,
        life_id="l1",
        l1_event_id="i1",
        raw_event_id="r1",
        occurred_at=T0,
        schema_version=SCHEMA_VERSION,
        policy_version=POLICY_VERSION,
        rules_version=RULES_VERSION,
    )
    kwargs.update(overrides)
    return deterministic_commit(**kwargs)


def test_same_input_byte_identical():
    a = _commit()
    b = _commit()
    assert a.event_id == b.event_id
    assert canonical_json(a.model_dump(mode="json", exclude={"ingested_at"})) == canonical_json(
        b.model_dump(mode="json", exclude={"ingested_at"})
    )


def test_committed_at_is_event_time_not_wall_clock():
    l2 = _commit()
    assert l2.committed_at == T0  # D4-2: semantic time is injected, never minted


def test_different_input_different_id():
    a = _commit()
    b = _commit(output_json={**OUTPUT, "state_deltas": {"energy": -0.2}})
    assert a.event_id != b.event_id


def test_fail_closed_on_out_of_range_delta():
    with pytest.raises(CommitError):
        _commit(output_json={**OUTPUT, "state_deltas": {"energy": 5.0}})


def test_fail_closed_on_unknown_state_key():
    with pytest.raises(CommitError):
        _commit(output_json={**OUTPUT, "state_deltas": {"hunger": 0.1}})


def test_fail_closed_on_smuggled_field():
    with pytest.raises(CommitError):
        _commit(
            output_json={
                **OUTPUT,
                "authoritative_state_write": {"energy": 1.0},
            }
        )
