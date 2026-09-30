"""Phase 3 S3 acceptance: cohort state machine determinism + standby + screening.

Case map (design doc 02 §2 S3):
- state machine determinism  -> same input twice => same cohort state
- standby 1.5x               -> capacity = target * 1.5 asserted; full fails closed
- screening completeness     -> age/member/consent three screens; any failure rejects
- withdraw determinism       -> withdraw only from enrolled; unknown fails closed
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from lifeos.dogfood.cohort import Cohort, CohortError

NOW = datetime(2026, 9, 30, 12, 0, 0, tzinfo=timezone.utc)


def _enroll(c: Cohort, uid: str, **kw):
    return c.screen_and_enroll(
        external_user_id=uid,
        age=kw.get("age", 25),
        jurisdiction=kw.get("jurisdiction", "CN"),
        is_member_or_family=kw.get("is_member_or_family", False),
        has_consent_signed=kw.get("has_consent_signed", True),
        at=NOW,
    )


def test_state_machine_deterministic():
    c1 = Cohort(name="pilot", target_size=10)
    c2 = Cohort(name="pilot", target_size=10)
    r1 = _enroll(c1, "u1")
    r2 = _enroll(c2, "u1")
    assert r1.status == r2.status == "enrolled"
    # a rejected case is deterministic too
    j1 = _enroll(c1, "minor", age=16)
    j2 = _enroll(c2, "minor", age=16)
    assert j1.status == j2.status == "rejected"
    assert j1.reject_reason == j2.reject_reason
    assert c1.summary() == c2.summary()


def test_standby_1_5x_capacity():
    c = Cohort(name="pilot", target_size=10)
    assert c.standby_capacity == 15  # 1.5x target
    for i in range(15):
        _enroll(c, f"u{i}")
    assert len(c.enrolled) == 15
    with pytest.raises(CohortError):
        _enroll(c, "overflow")
    # summary consistent
    s = c.summary()
    assert s["enrolled"] == 15 and s["standby_capacity"] == 15


def test_screening_completeness():
    c = Cohort(name="pilot", target_size=10)
    # all three screens pass -> enrolled
    assert _enroll(c, "ok").status == "enrolled"
    # age screen
    assert _enroll(c, "young", age=17).status == "rejected"
    # member screen
    assert _enroll(c, "member", is_member_or_family=True).status == "rejected"
    # consent screen
    assert _enroll(c, "noconsent", has_consent_signed=False).status == "rejected"
    # multi-jurisdiction recruiting: CN/SG/HK/MO all enrollable with same Chinese materials
    for j in ("CN", "SG", "HK", "MO"):
        assert _enroll(c, f"u-{j}", jurisdiction=j).status == "enrolled"
    assert c.summary()["enrolled"] == 5
    assert c.summary()["rejected"] == 3
    # duplicate id fails closed
    with pytest.raises(CohortError):
        _enroll(c, "ok")


def test_withdraw_determinism():
    c = Cohort(name="pilot", target_size=10)
    _enroll(c, "w1")
    p = c.withdraw(external_user_id="w1", at=NOW)
    assert p.status == "withdrawn" and p.withdrawn_at == NOW
    assert len(c.enrolled) == 0 and len(c.withdrawn) == 1
    # double withdraw fails closed
    with pytest.raises(CohortError):
        c.withdraw(external_user_id="w1", at=NOW)
    # unknown fails closed
    with pytest.raises(CohortError):
        c.withdraw(external_user_id="ghost", at=NOW)
