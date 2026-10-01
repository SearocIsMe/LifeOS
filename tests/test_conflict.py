"""S2 acceptance cases for deterministic same-slot conflict resolution
(design phases/phase-2/01 §2.1, §33: tests/test_conflict.py).

Red lines under test:

- Adjudication determinism: same input -> same outcome (no wall clock/randomness).
- History preservation: losers are marked SUPERSEDED with valid_to closed,
  transaction history rows never deleted.
- Ambiguous routing: step-1 tie + confidence gap <= 0.05 -> manual queue, no auto winner.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from lifeos.entities import ConflictState, MemoryType
from lifeos.store.conflict import (
    AMBIGUOUS_CONFIDENCE_GAP,
    ConflictResolution,
    apply_resolution,
    mark_superseded,
    resolve_slot,
)

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)
T1 = datetime(2026, 9, 2, tzinfo=timezone.utc)


def _rec(rid, *, tx=T0, valid=T0, conf=0.9, slot="user.note", life="life-a"):
    return {
        "memory_id": rid,
        "life_id": life,
        "subject_id": "user",
        "type": MemoryType.SEMANTIC,
        "content": f"备忘 {rid}",
        "slot_key": slot,
        "valid_from": valid,
        "transaction_from": tx,
        "confidence": conf,
        "importance": 2,
    }


# --------------------------------------------------------------------- #
# adjudication determinism
# --------------------------------------------------------------------- #


def test_step1_later_transaction_overrides():
    res = resolve_slot([_rec("BI-old", tx=T0), _rec("BI-new", tx=T1)])
    assert res.winner.memory_id == "BI-new"
    assert [m.memory_id for m in res.superseded] == ["BI-old"]
    assert not res.is_ambiguous


def test_step2_newest_valid_from_wins_when_tx_tied():
    res = resolve_slot([_rec("BI-a", tx=T1, valid=T0), _rec("BI-b", tx=T1, valid=T1)])
    assert res.winner.memory_id == "BI-b"


def test_step3_higher_confidence_wins_when_same_instant():
    res = resolve_slot([_rec("BI-a", tx=T1, valid=T1, conf=0.7), _rec("BI-b", tx=T1, valid=T1, conf=0.9)])
    assert res.winner.memory_id == "BI-b"


def test_step4_memory_id_lexicographic_tie_break():
    res = resolve_slot([_rec("BI-b", tx=T1, valid=T1, conf=0.8), _rec("BI-a", tx=T1, valid=T1, conf=0.8)])
    assert res.winner.memory_id == "BI-a"


def test_same_input_same_outcome():
    records = [_rec("BI-a", tx=T1, valid=T1, conf=0.8), _rec("BI-b", tx=T1, valid=T1, conf=0.8)]
    first = resolve_slot(list(records))
    again = resolve_slot(reversed(records))
    assert first.winner.memory_id == again.winner.memory_id
    assert sorted(m.memory_id for m in first.superseded) == sorted(m.memory_id for m in again.superseded)


# --------------------------------------------------------------------- #
# history preservation
# --------------------------------------------------------------------- #


def test_resolution_never_drops_candidates():
    records = [_rec("BI-old", tx=T0), _rec("BI-new", tx=T1)]
    res = resolve_slot(list(records))
    winner, losers = apply_resolution(res, at=T1)
    persisted = [winner] + losers
    assert {r.memory_id for r in persisted} == {"BI-old", "BI-new"}


def test_loser_marked_superseded_with_valid_to_closed():
    res = resolve_slot([_rec("BI-old", tx=T0), _rec("BI-new", tx=T1)])
    _, losers = apply_resolution(res, at=T1)
    assert len(losers) == 1
    assert losers[0].conflict_state == ConflictState.SUPERSEDED
    assert losers[0].valid_to == T1


def test_mark_superseded_keeps_history_row_identity():
    loser = mark_superseded(_rec("BI-old", tx=T0), T1)
    assert loser.memory_id == "BI-old"
    assert loser.transaction_from == T0  # history untouched


def test_winner_restored_to_current():
    res = resolve_slot([_rec("BI-old", tx=T0), _rec("BI-new", tx=T1)])
    winner, _ = apply_resolution(res, at=T1)
    assert winner.conflict_state == ConflictState.CURRENT


def test_ambiguous_resolution_rejects_persist():
    res = resolve_slot([_rec("BI-a", tx=T1, conf=0.70), _rec("BI-b", tx=T1, conf=0.72)])
    assert res.is_ambiguous
    with pytest.raises(ValueError):
        apply_resolution(res, at=T1)


# --------------------------------------------------------------------- #
# ambiguous manual queue
# --------------------------------------------------------------------- #


def test_step1_tie_with_small_confidence_gap_routes_to_ambiguous():
    assert 0.72 - 0.70 <= AMBIGUOUS_CONFIDENCE_GAP
    res = resolve_slot([_rec("BI-a", tx=T1, conf=0.70), _rec("BI-b", tx=T1, conf=0.72)])
    assert res.is_ambiguous
    assert res.winner is None
    assert sorted(m.memory_id for m in res.ambiguous) == ["BI-a", "BI-b"]


def test_large_confidence_gap_still_auto_resolves():
    assert 0.9 - 0.6 > AMBIGUOUS_CONFIDENCE_GAP
    res = resolve_slot([_rec("BI-a", tx=T1, conf=0.6), _rec("BI-b", tx=T1, conf=0.9)])
    assert not res.is_ambiguous
    assert res.winner.memory_id == "BI-b"


def test_queue_row_shape_for_ambiguous_queue_json():
    res = resolve_slot([_rec("BI-a", tx=T1, conf=0.70), _rec("BI-b", tx=T1, conf=0.72)])
    row = res.to_queue_row()
    assert row["slot_key"] == "user.note"
    assert row["conflict_state"] == "ambiguous"
    assert row["status"] == "pending"
    assert row["owner"] == "lifeos-maintainer"
    assert isinstance(row, dict)
    assert row["memory_ids"] == ["BI-a", "BI-b"]


def test_conflict_resolution_is_tie_property():
    res = resolve_slot([_record := _rec("BI-old", tx=T0), _rec("BI-new", tx=T1)])
    assert isinstance(res, ConflictResolution)
    assert res.is_tie
    assert not resolve_slot([_record]).is_tie  # single candidate - no tie


def test_boundary_gap_0_05_float_error_routes_to_ambiguous():
    # Float boundary regression: 0.8 - 0.75 = 0.050000000000000044 which is
    # technically > 0.05 - must STILL route to the ambiguous band (design 01
    # §2.1: 置信差 ≤ 0.05 → 入队列，不自动裁决).
    delta = 0.8 - 0.75
    assert delta > AMBIGUOUS_CONFIDENCE_GAP  # confirm the float error exists
    res = resolve_slot([_rec("BI-a", tx=T1, valid=T1, conf=0.75), _rec("BI-b", tx=T1, valid=T1, conf=0.8)])
    assert res.is_ambiguous
    assert res.winner is None
