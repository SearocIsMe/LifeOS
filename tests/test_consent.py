"""Phase 3 S1 acceptance: consent activation (separate sensitive / revocation / minors).

Case map (design doc 02 §2 S1):
- sensitive separate consent -> missing standalone record => processing rejected (PIPL)
- revocation linkage         -> revoked_at => processing stops + auto user erase
- minor exclusion            -> age < 18 rejected (all four jurisdictions)
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from lifeos.consent import (
    ConsentError,
    check_cohort_eligibility,
    has_consent,
    record_consent,
    require_consent,
    revoke_and_erase,
)
from lifeos.entities import ConsentRecord
from lifeos.events.pipeline import EventPipeline
from lifeos.store.memory_store import InMemoryStore

NOW = datetime(2026, 9, 30, 12, 0, 0, tzinfo=timezone.utc)
LIFE = "life-consent"
USER = "ext-user-1"


def _consent(**overrides) -> ConsentRecord:
    base = dict(
        consent_id="c-1",
        external_user_id=USER,
        life_id=LIFE,
        consent_type="standard",
        scope={"chat": True},
        jurisdiction="CN",
        locale="zh-CN",
        document_version="1.0.0",
        granted_at=NOW,
        revoked_at=None,
    )
    base.update(overrides)
    return ConsentRecord(**base)


def _store_with_memories() -> InMemoryStore:
    store = InMemoryStore()
    store.create_instance(
        life_id=LIFE, personality_seed="s1", born_at=NOW, schema_version="0.1.0"
    )
    pipe = EventPipeline(store)
    pipe.ingest(
        {
            "life_id": LIFE,
            "source": "user",
            "payload": {
                "text": "我家猫叫咪咪。",
                "structured": {
                    "memory_candidates": [
                        {
                            "type": "semantic",
                            "content": "用户家里养的猫叫咪咪",
                            "slot_key": "user.pet_name",
                            "subject_id": "user",
                            "confidence": 0.95,
                            "importance": 3,
                        }
                    ]
                },
            },
            "occurred_at": NOW,
        }
    )
    return store


def test_sensitive_requires_separate_consent():
    store = InMemoryStore()
    record_consent(_consent(scope={"chat": True}), store)
    # normal scope granted
    assert has_consent(store, external_user_id=USER, scope="chat")
    # sensitive scope NOT covered by a standard record
    assert not has_consent(store, external_user_id=USER, scope="health")
    with pytest.raises(ConsentError):
        require_consent(store, external_user_id=USER, scope="health")
    # standalone sensitive record unlocks it
    record_consent(_consent(consent_id="c-2", consent_type="sensitive_separate", scope={"health": True}), store)
    assert has_consent(store, external_user_id=USER, scope="health")


def test_revocation_linkage_auto_erase():
    store = _store_with_memories()
    record_consent(_consent(), store)
    assert len(store.query_memories(life_id=LIFE)) == 1

    out = revoke_and_erase(store, external_user_id=USER, consent_id="c-1", at=NOW)
    assert out["revoked"] == "c-1"
    assert LIFE in out["lives_stopped"]
    assert len(out["erased_memory_ids"]) == 1
    # processing stopped (revoked_at written)
    assert not has_consent(store, external_user_id=USER, scope="chat")
    # auto erase happened: zero memories remain
    assert len(store.query_memories(life_id=LIFE)) == 0
    # revoke again fails closed
    with pytest.raises(ConsentError):
        revoke_and_erase(store, external_user_id=USER, consent_id="c-1", at=NOW)


def test_minor_exclusion():
    with pytest.raises(ConsentError):
        check_cohort_eligibility(age=17, is_member_or_family=False, has_consent_signed=True)
    with pytest.raises(ConsentError):
        check_cohort_eligibility(age=25, is_member_or_family=True, has_consent_signed=True)
    with pytest.raises(ConsentError):
        check_cohort_eligibility(age=25, is_member_or_family=False, has_consent_signed=False)
    # all three screens pass -> eligible
    check_cohort_eligibility(age=25, is_member_or_family=False, has_consent_signed=True)
