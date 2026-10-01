"""B3 acceptance: blind-test administration tooling (latin square / pairing / exclusions).

Case map:
- latin square balance -> n subjects: each arm in each position exactly once
- paired trials        -> same fragment, order[0] baseline vs every other arm
- exclusion fail-closed-> member/family/minor/no-consent sessions rejected
- attention void       -> failed check voids all trials (prereg fail_rule)
- effective_n          -> only attention-passed + answered subjects count
- no fabricated answers-> sessions are structures; chose stays None until real answers
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from lifeos.dogfood.blindtest import (
    ARMS,
    build_session,
    effective_n,
    latin_square_order,
    void_on_attention_check,
)

NOW = datetime(2026, 9, 30, 12, 0, 0, tzinfo=timezone.utc)
FRAGMENTS = ["BS-026", "BS-027", "BS-028", "BS-029", "BS-030", "BS-009", "BS-021", "BS-022"]


def test_latin_square_balance():
    """Over n subjects, each arm appears in each position exactly once."""
    orders = [latin_square_order(i) for i in range(4)]
    # each position: all four arms appear exactly once
    for pos in range(4):
        col = {order[pos] for order in orders}
        assert col == set(ARMS)
    # each subject sees all four arms
    for order in orders:
        assert sorted(order) == sorted(ARMS)


def test_paired_trials_same_fragment():
    s = build_session(
        external_user_id="u1", subject_seq=0, fragments=FRAGMENTS,
        age=25, is_member_or_family=False, consent_signed=True, at=NOW,
    )
    # 8 fragments x 3 pairs = 24 trials (judgment units per subject)
    assert len(s.trials) == 24
    assert s.summary()["trials"] == 24
    # every trial's left arm = subject's baseline (order[0]), right = the others
    for t in s.trials:
        assert t.arm_left == s.arm_order[0]
        assert t.arm_right in s.arm_order[1:]
    # same fragment appears once per pair
    for frag in FRAGMENTS:
        trials = [t for t in s.trials if t.fragment_id == frag]
        assert len(trials) == 3
        assert {t.arm_right for t in trials} == set(s.arm_order[1:])
    # no fabricated answers: chose stays None until real subjects answer
    assert all(t.chose is None for t in s.trials)


def test_exclusion_fail_closed():
    with pytest.raises(Exception):
        build_session(external_user_id="m", subject_seq=0, fragments=FRAGMENTS,
                      age=25, is_member_or_family=True, consent_signed=True, at=NOW)
    with pytest.raises(Exception):
        build_session(external_user_id="minor", subject_seq=0, fragments=FRAGMENTS,
                      age=17, is_member_or_family=False, consent_signed=True, at=NOW)
    with pytest.raises(Exception):
        build_session(external_user_id="nc", subject_seq=0, fragments=FRAGMENTS,
                      age=25, is_member_or_family=False, consent_signed=False, at=NOW)
    # eligible -> session built with consent recorded
    s = build_session(external_user_id="ok", subject_seq=1, fragments=FRAGMENTS,
                      age=25, is_member_or_family=False, consent_signed=True, at=NOW)
    assert s.consent_signed is True


def test_attention_void_rule():
    s = build_session(external_user_id="u2", subject_seq=2, fragments=FRAGMENTS[:2],
                      age=25, is_member_or_family=False, consent_signed=True, at=NOW)
    # simulate REAL answers arriving (B4), then a failed attention check
    for t in s.trials:
        t.chose = t.arm_right  # placeholder for the answer channel, not fabrication of results
    n = void_on_attention_check(s, passed=False)
    assert n == len(s.trials) == 6
    assert all(t.voided and t.void_reason for t in s.trials)
    # effective_n excludes this subject entirely
    assert effective_n([s]) == 0
    # passed check voids nothing
    s2 = build_session(external_user_id="u3", subject_seq=3, fragments=FRAGMENTS[:2],
                       age=25, is_member_or_family=False, consent_signed=True, at=NOW)
    assert void_on_attention_check(s2, passed=True) == 0
    for t in s2.trials:
        t.chose = t.arm_left
    assert effective_n([s2]) == 1


def test_effective_n_counts_only_valid():
    sessions = []
    for i in range(4):
        s = build_session(external_user_id=f"u{i}", subject_seq=i, fragments=FRAGMENTS[:2],
                          age=25, is_member_or_family=False, consent_signed=True, at=NOW)
        # 施测流程：注意力检查通过标记（流程状态，非作答结果）
        void_on_attention_check(s, passed=True)
        for t in s.trials:
            t.chose = t.arm_left
        sessions.append(s)
    # all four valid -> n=4
    assert effective_n(sessions) == 4
    # one fails attention -> n=3
    void_on_attention_check(sessions[0], passed=False)
    assert effective_n(sessions) == 3
    # one never answered -> n=2
    for t in sessions[1].trials:
        t.chose = None
    assert effective_n(sessions) == 2
