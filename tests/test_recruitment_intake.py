"""B4.1 acceptance: recruitment intake processor (registration -> screening -> enrollment).

Case map (design 01 §3.1 + §三A four-question spec):
- screening determinism -> same entry => same classification (prereg rules)
- subject_id issuance   -> LIFE-BT-<seq:03d> by standby order (登记表第四部分)
- monitor counters      -> enrolled/screened_out/target/standby/complete/degraded
- exclusions audit      -> prereg rule原文 recorded, NO silent rejection
- idempotent re-run     -> same entries twice => no change
- degraded flag         -> intake pace < 30 with target unmet => degraded=true (不静默)
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from recruitment_intake import classify, process_entries, subject_id_for

NOW = datetime(2026, 9, 30, 12, 0, 0, tzinfo=timezone.utc)


def _entry(seq: int, **kw) -> dict:
    base = {"subject_seq": seq, "age": 25, "is_member_or_family": False,
            "jurisdiction": "CN", "consent_signed": True}
    base.update(kw)
    return base


def test_screening_determinism():
    assert classify(_entry(0)) == ("enrolled", "")
    assert classify(_entry(1, age=17)) == ("excluded", "未成年人不纳入（<18）")
    assert classify(_entry(2, is_member_or_family=True)) == ("excluded", "项目组成员及其直系亲属排除")
    assert classify(_entry(3, consent_signed=False)) == ("excluded", "未签署知情同意不得作答")
    # same entry twice => same classification
    assert classify(_entry(4)) == classify(_entry(4))


def test_subject_id_issuance():
    assert subject_id_for(0) == "LIFE-BT-000"
    assert subject_id_for(12) == "LIFE-BT-012"
    assert subject_id_for(123) == "LIFE-BT-123"


def test_monitor_counters_and_capacity(tmp_path):
    entries = [_entry(i) for i in range(5)]
    m = process_entries(entries, collected_at=NOW)
    assert m["enrolled"] == 5
    assert m["screened_out"] == 0
    assert m["target_n"] == 50
    assert m["standby_capacity"] == 75  # 1.5x
    assert m["complete"] is False  # 5 < 50
    assert m["effective_n"] == 5
    # subject ids issued in standby order
    assert [p["subject_id"] for p in m["enrolled_log"]] == [f"LIFE-BT-{i:03d}" for i in range(5)]


def test_exclusions_audit_no_silent_rejection(tmp_path):
    entries = [
        _entry(0),
        _entry(1, age=17),
        _entry(2, is_member_or_family=True),
        _entry(3, consent_signed=False),
    ]
    m = process_entries(entries, collected_at=NOW)
    assert m["enrolled"] == 1
    assert m["screened_out"] == 3
    # exclusion rules recorded with prereg原文 + evidence (no silent rejection)
    from recruitment_intake import _iter_new_exclusions

    excl = _iter_new_exclusions(entries)
    assert len(excl) == 3
    rules = {e["rule"] for e in excl}
    assert rules == {"未成年人不纳入（<18）", "项目组成员及其直系亲属排除", "未签署知情同意不得作答"}
    for e in excl:
        assert e["evidence"]  # the original entry recorded


def test_idempotent_rerun(tmp_path):
    entries = [_entry(i) for i in range(3)]
    m1 = process_entries(entries, collected_at=NOW)
    assert m1["enrolled"] == 3
    # re-running the SAME forms: monitor counters unchanged (idempotent)
    m2 = process_entries(entries, collected_at=NOW)
    assert m2["enrolled"] == m1["enrolled"]
    assert m2["screened_out"] == m1["screened_out"]
    assert len(m2["enrolled_log"]) == len(m1["enrolled_log"])


def test_degraded_flag_not_silent(tmp_path):
    # pace 2 < 30 weekly minimum, target unmet => degraded=true + reason
    m = process_entries([_entry(0), _entry(1)], collected_at=NOW)
    assert m["degraded"] is True
    assert m["degradation_reason"]
    assert "30" in m["degradation_reason"]
    # at/above the pace threshold => not degraded
    many = [_entry(i) for i in range(30)]
    m2 = process_entries(many, collected_at=NOW)
    assert m2["degraded"] is False
    # target met => complete + not degraded
    all50 = [_entry(i) for i in range(50)]
    m3 = process_entries(all50, collected_at=NOW)
    assert m3["complete"] is True and m3["degraded"] is False
