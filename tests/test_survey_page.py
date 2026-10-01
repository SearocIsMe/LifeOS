"""T1 single-case contract tests (test-first): survey-loaded blind-test page + email-hash dedup.

方案 A（用户已确认）: email 只作单向哈希防重，原文不入库；作答数据匿名化不变。
Single case first（用户指定：先测试单个用例，再做正式上线开发）— this file
pins the LIFE-BT-002 instance flow; the full-suite expansion lands in T4.

Contract:
- survey load      -> /blindtest?survey=LIFE-BT-002 serves that instance's
                      24 trials with real-arm texts (no mock stubs)
- email hash dedup -> first submission passes; duplicate email => 409 +
                      submission voided (作废); email原文 never persisted
- hash ledger      -> submitted_hashes.json separate from responses.jsonl;
                      hash is one-way (原文不可反推)
- backend chain    -> submit => attention rule + persist_responses +
                      recruitment_monitor.json counter update
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

NOW = datetime(2026, 9, 30, 12, 0, 0, tzinfo=timezone.utc)


# --------------------------------------------------------------------------- #
# survey instance loading (single case: LIFE-BT-002)
# --------------------------------------------------------------------------- #

def test_load_survey_instance_life_bt_002():
    from lifeos.dogfood.blindtest_page import load_survey

    s = load_survey("LIFE-BT-002")
    assert s["subject_id"] == "LIFE-BT-002"
    assert s["approval_number"] == "2026-ETH-00001"
    assert len(s["trials"]) == 24
    # real-arm texts present in every trial (no mock stubs)
    for t in s["trials"]:
        assert t["left_text"] and t["right_text"]
        assert not t["left_text"].startswith("[mock-gen")


def test_load_unknown_survey_fails_closed():
    from lifeos.dogfood.blindtest_page import load_survey

    with pytest.raises(Exception):
        load_survey("LIFE-BT-999")


# --------------------------------------------------------------------------- #
# email hash dedup (方案 A: 原文不入库)
# --------------------------------------------------------------------------- #

def test_email_hash_one_way(tmp_path):
    from lifeos.dogfood.blindtest_page import email_hash, record_hash

    h = email_hash("subject@example.com")
    assert h != "subject@example.com"  # one-way: hash != 原文
    assert email_hash("subject@example.com") == h  # deterministic
    assert email_hash("other@example.com") != h
    # ledger records the hash, never the email原文
    ledger = record_hash(h, subject_id="LIFE-BT-002", out_dir=tmp_path)
    d = json.loads(ledger.read_text(encoding="utf-8"))
    assert d["hashes"][0]["hash"] == h
    assert "subject@example.com" not in json.dumps(d)


def test_duplicate_email_voids_submission(tmp_path):
    from lifeos.dogfood.blindtest_page import check_duplicate, email_hash, record_hash

    h = email_hash("subject@example.com")
    # first submission: not a duplicate
    assert check_duplicate(h, out_dir=tmp_path) is False
    # record it, then a second submission with the same email is a duplicate
    record_hash(h, subject_id="LIFE-BT-002", out_dir=tmp_path)
    assert check_duplicate(h, out_dir=tmp_path) is True  # 重复 → 视为作废
