"""S1 acceptance cases: relationship engine (design doc 02 §2 S1 table)."""

import pytest

from lifeos.kernel.relationship import (
    RELATIONSHIP_DECAY_LAMBDA,
    RelationshipError,
    apply_relationship_event,
    personality_modulation,
)

CURRENT_ROW = {
    "familiarity": 0.5,
    "trust": 0.5,
    "attachment": 0.5,
    "version": 3,
}


class TestUpdateRule:
    def test_positive_confidence_raises(self):
        upd = apply_relationship_event(
            CURRENT_ROW, subject_id="alice", weight_key="positive_interaction", confidence=0.8
        )
        assert upd.familiarity > 0.5 and upd.trust > 0.5 and upd.attachment > 0.5

    def test_zero_confidence_decays(self):
        upd = apply_relationship_event(
            CURRENT_ROW, subject_id="alice", weight_key="positive_interaction", confidence=0.0,
            dt_hours=10.0,
        )
        assert upd.familiarity < 0.5  # decay term dominates

    def test_clip_bounds(self):
        high = apply_relationship_event(
            {"familiarity": 0.99, "trust": 0.99, "attachment": 0.99, "version": 1},
            subject_id="alice", weight_key="positive_interaction", confidence=1.0,
        )
        assert high.familiarity <= 1.0 and high.trust <= 1.0 and high.attachment <= 1.0
        low = apply_relationship_event(
            {"familiarity": 0.01, "trust": 0.01, "attachment": 0.01, "version": 1},
            subject_id="alice", weight_key="conflict", confidence=1.0,
        )
        assert low.familiarity >= 0.0 and low.trust >= 0.0 and low.attachment >= 0.0

    def test_dt_decay_term(self):
        without = apply_relationship_event(
            CURRENT_ROW, subject_id="alice", weight_key="positive_interaction", confidence=0.5
        )
        with_decay = apply_relationship_event(
            CURRENT_ROW, subject_id="alice", weight_key="positive_interaction", confidence=0.5,
            dt_hours=100.0,
        )
        expected_gap = RELATIONSHIP_DECAY_LAMBDA * 100.0
        assert (without.familiarity - with_decay.familiarity) == pytest.approx(
            expected_gap, abs=1e-9
        )


class TestVersioning:
    def test_version_increments(self):
        upd = apply_relationship_event(
            CURRENT_ROW, subject_id="alice", weight_key="positive_interaction", confidence=0.5
        )
        assert upd.version == 4

    def test_fresh_row_version_one(self):
        upd = apply_relationship_event(
            None, subject_id="bob", weight_key="positive_interaction", confidence=0.5
        )
        assert upd.version == 1 and upd.familiarity > 0.2

    def test_reason_carries_evidence_chain(self):
        upd = apply_relationship_event(
            CURRENT_ROW, subject_id="alice", weight_key="positive_interaction", confidence=0.7,
            dt_hours=2.0,
        )
        assert upd.reason["weight_key"] == "positive_interaction"
        assert upd.reason["confidence"] == 0.7
        assert upd.reason["decay"] == pytest.approx(RELATIONSHIP_DECAY_LAMBDA * 2.0)
        assert "previous" in upd.reason


class TestPersonalityModulation:
    def test_same_seed_same_coefficient(self):
        assert personality_modulation("seed-x") == personality_modulation("seed-x")

    def test_phase1_default(self):
        assert personality_modulation(None) == 1.0
        assert personality_modulation("any") == 1.0  # stubbed in Phase 1


class TestFailClosed:
    def test_unknown_weight_key(self):
        with pytest.raises(RelationshipError):
            apply_relationship_event(
                CURRENT_ROW, subject_id="alice", weight_key="nonexistent", confidence=0.5
            )

    def test_confidence_out_of_range(self):
        with pytest.raises(RelationshipError):
            apply_relationship_event(
                CURRENT_ROW, subject_id="alice", weight_key="positive_interaction", confidence=1.5
            )

    def test_negative_dt(self):
        with pytest.raises(RelationshipError):
            apply_relationship_event(
                CURRENT_ROW, subject_id="alice", weight_key="positive_interaction",
                confidence=0.5, dt_hours=-1.0,
            )
