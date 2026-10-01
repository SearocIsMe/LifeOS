"""T-A contract tests (test-first): blind-test administration page.

施测页 = 被试实际操作的工具 (design: 同意页 + 配对判断页 + 拉丁方出题 + 落库)。
Each case pins ONE DoD item; implementation lands only to turn these green.

Contract:
- consent fail-closed -> 未签署同意不得出题/作答 (403)
- 拉丁方出题          -> per-subject balanced order (order_seq recorded)
- 配对判断            -> same fragment, arm_left/arm_right from the frozen pool
- attention check     -> enforced in the trial stream; failure voids responses
- 落库匿名化          -> responses.jsonl lines carry ONLY pseudonymous fields
                         (no direct identifiers; spec §9)
- forced choice       -> chose must be arm_left or arm_right (no abstain)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

NOW = datetime(2026, 9, 30, 12, 0, 0, tzinfo=timezone.utc)
FRAGMENTS = ["BS-026", "BS-027", "BS-028"]


# --------------------------------------------------------------------------- #
# consent gate (fail-closed)
# --------------------------------------------------------------------------- #

def test_no_consent_no_session():
    from lifeos.dogfood.blindtest_page import start_session

    with pytest.raises(Exception):
        start_session(external_user_id="u1", subject_seq=0, fragments=FRAGMENTS,
                      age=25, is_member_or_family=False, consent_signed=False, at=NOW)


def test_consent_recorded_on_start():
    from lifeos.dogfood.blindtest_page import start_session

    s = start_session(external_user_id="u1", subject_seq=0, fragments=FRAGMENTS,
                      age=25, is_member_or_family=False, consent_signed=True, at=NOW)
    assert s["consent_signed"] is True
    assert s["created_at"] == NOW.isoformat()


# --------------------------------------------------------------------------- #
# latin-square presentation + paired trials
# --------------------------------------------------------------------------- #

def test_trial_sequence_is_latin_balanced():
    from lifeos.dogfood.blindtest_page import build_trial_sequence

    seq0 = build_trial_sequence(subject_seq=0, fragments=FRAGMENTS)
    seq1 = build_trial_sequence(subject_seq=1, fragments=FRAGMENTS)
    # each subject sees all 4 arms across trials; orders differ between subjects
    arms0 = {t["arm_left"] for t in seq0} | {t["arm_right"] for t in seq0}
    assert arms0 == {"A", "B", "C", "LifeOS"}
    assert seq0[0]["arm_left"] != seq1[0]["arm_left"]  # balanced across subjects
    # order_seq recorded per trial
    assert [t["order_seq"] for t in seq0] == list(range(len(seq0)))


def test_paired_trials_same_fragment():
    from lifeos.dogfood.blindtest_page import build_trial_sequence

    seq = build_trial_sequence(subject_seq=0, fragments=FRAGMENTS)
    # 3 fragments x 3 pairs = 9 trials
    assert len(seq) == 9
    for frag in FRAGMENTS:
        trials = [t for t in seq if t["fragment_id"] == frag]
        assert len(trials) == 3
        # left arm is the subject's baseline; rights are the other three
        assert {t["arm_right"] for t in trials} == {"A", "B", "C", "LifeOS"} - {trials[0]["arm_left"]}


# --------------------------------------------------------------------------- #
# forced choice + attention check
# --------------------------------------------------------------------------- #

def test_forced_choice_validation():
    from lifeos.dogfood.blindtest_page import UNANSWERABLE, build_trial_sequence, record_response

    seq = build_trial_sequence(subject_seq=0, fragments=FRAGMENTS)
    t = seq[0]
    # valid: left or right or 无法回答 (Q2 三选一)
    assert record_response(t, chose=t["arm_left"], reason_text="风格一致", at=NOW)["ok"] is True
    assert record_response(t, chose=t["arm_right"], reason_text="r", at=NOW)["ok"] is True
    assert record_response(t, chose=UNANSWERABLE, reason_text="看不出差别", at=NOW)["ok"] is True
    # abstain / foreign choice rejected
    with pytest.raises(Exception):
        record_response(t, chose="中间", reason_text="", at=NOW)
    with pytest.raises(Exception):
        record_response(t, chose="D", reason_text="", at=NOW)
    with pytest.raises(Exception):
        record_response(t, chose="", reason_text="", at=NOW)  # 空串拒绝（Q1 防回归）


def test_attention_check_enforced():
    from lifeos.dogfood.blindtest_page import build_trial_sequence, apply_attention_rule

    seq = build_trial_sequence(subject_seq=0, fragments=FRAGMENTS)
    # attention check present in the stream (one trial flagged)
    assert any(t.get("is_attention_check") for t in seq)
    # failed -> ALL responses voided
    voided = apply_attention_rule(seq, passed=False)
    assert voided == len(seq)
    assert all(t["voided"] for t in seq)
    # passed -> nothing voided
    seq2 = build_trial_sequence(subject_seq=0, fragments=FRAGMENTS)
    assert apply_attention_rule(seq2, passed=True) == 0


# --------------------------------------------------------------------------- #
# persistence (responses.jsonl) + anonymization
# --------------------------------------------------------------------------- #

def test_persist_jsonl_anonymized(tmp_path):
    from lifeos.dogfood.blindtest_page import build_trial_sequence, persist_responses

    seq = build_trial_sequence(subject_seq=0, fragments=FRAGMENTS[:1])
    for t in seq:
        t["chose"] = t["arm_right"]
        t["reason_text"] = "理由"
        t["attention_check_passed"] = True
        t["submitted_at"] = NOW.isoformat()
    out = persist_responses(seq, subject_id="LIFE-BT-000", out_dir=tmp_path)
    lines = out.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 3
    row = json.loads(lines[0])
    # anonymized: pseudonymous subject_id only, NO direct identifiers
    assert row["subject_id"] == "LIFE-BT-000"
    for forbidden in ("name", "phone", "email", "id_card", "ip", "contact"):
        assert forbidden not in row
    assert row["chose"] in (row["arm_left"], row["arm_right"])
    assert row["submitted_at"]


def test_persist_idempotent_per_subject(tmp_path):
    from lifeos.dogfood.blindtest_page import build_trial_sequence, persist_responses

    seq = build_trial_sequence(subject_seq=0, fragments=FRAGMENTS[:1])
    for t in seq:
        t["chose"] = t["arm_left"]
        t["attention_check_passed"] = True
    persist_responses(seq, subject_id="LIFE-BT-000", out_dir=tmp_path)
    out = persist_responses(seq, subject_id="LIFE-BT-000", out_dir=tmp_path)
    lines = out.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 3  # same subject+trials rewritten, not duplicated
