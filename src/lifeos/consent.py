"""Consent activation: append-only trail -> enforced business link (Phase 3 S1).

The ``ConsentRecord`` entity froze in Phase 0 (schema + isolation validated);
this module activates the ENFORCEMENT chain (design doc 01 §1.3):

- sensitive-item SEPARATE consent: processing a sensitive scope without a
  standalone sensitive consent record => rejected (PIPL口径, spec §9.4);
- revocation linkage: ``revoked_at`` written => all processing for that user
  stops IMMEDIATELY + user erase auto-triggers (spec §9.3 red line 10);
- minor exclusion: age < 18 => cohort entry rejected (all four jurisdictions,
  spec §9.4 未成年人：不纳入 cohort).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from lifeos.entities import ConsentRecord
from lifeos.store.erase import user_erase
from lifeos.store.memory_store import InMemoryStore

MINOR_AGE_LIMIT = 18

# Scopes that require a standalone sensitive-item consent (PIPL: 敏感个人信息单独同意).
SENSITIVE_SCOPES = frozenset({"health", "biometrics", "location_precise", "finances"})


class ConsentError(ValueError):
    """Raised when a consent-gated action is not permitted (fail-closed)."""


def record_consent(record: ConsentRecord, store: InMemoryStore) -> ConsentRecord:
    """Append one consent record (idempotent on consent_id)."""
    if any(c.consent_id == record.consent_id for c in store.consent_records):
        return record  # idempotent
    store.consent_records.append(record)
    return record


def has_consent(store: InMemoryStore, *, external_user_id: str, scope: str) -> bool:
    """True iff a granted, non-revoked consent covers ``scope``.

    Sensitive scopes require a standalone record with that exact scope.
    """
    rows = [
        c
        for c in store.consent_records
        if c.external_user_id == external_user_id and c.revoked_at is None
    ]
    if scope in SENSITIVE_SCOPES:
        return any(c.consent_type == "sensitive_separate" and scope in (c.scope or {}) for c in rows)
    return any(scope in (c.scope or {}) for c in rows)


def require_consent(
    store: InMemoryStore, *, external_user_id: str, scope: str
) -> None:
    """Fail-closed gate: processing a scope without consent raises ConsentError."""
    if not has_consent(store, external_user_id=external_user_id, scope=scope):
        kind = "standalone sensitive-item consent" if scope in SENSITIVE_SCOPES else "consent"
        raise ConsentError(f"processing scope {scope!r} requires {kind} (PIPL §9.4)")


def revoke_consent(
    store: InMemoryStore,
    *,
    external_user_id: str,
    consent_id: str,
    at: datetime,
) -> int:
    """Write ``revoked_at`` (append-only trail keeps the record; status flips).

    Returns the number of live Life Instances that must stop processing for
    this user. Callers then auto-trigger user erase per spec §9.3.
    """
    n = 0
    for c in store.consent_records:
        if c.consent_id == consent_id and c.external_user_id == external_user_id:
            if c.revoked_at is None:
                store.consent_records = [
                    cc.model_copy(update={"revoked_at": at}) if cc.consent_id == consent_id else cc
                    for cc in store.consent_records
                ]
                n += 1
    if n == 0:
        raise ConsentError(f"unknown or already-revoked consent: {consent_id!r}")
    return n


def revoke_and_erase(
    store: InMemoryStore,
    *,
    external_user_id: str,
    consent_id: str,
    at: datetime,
    jurisdiction: str = "CN",
) -> dict[str, Any]:
    """撤回联动: revoke => stop processing + AUTO user erase of that user's memories."""
    revoke_consent(store, external_user_id=external_user_id, consent_id=consent_id, at=at)
    life_ids = sorted(
        {c.life_id for c in store.consent_records if c.external_user_id == external_user_id}
    )
    erased_ids: list[str] = []
    for life_id in life_ids:
        mems = store.query_memories(life_id=life_id)
        if not mems:
            continue
        report = user_erase(
            store,
            life_id=life_id,
            memory_ids=[m.memory_id for m in mems],
            requested_by=external_user_id,
            at=at,
            reason="consent revocation auto-erase (spec §9.3)",
            jurisdiction=jurisdiction,
        )
        erased_ids.extend(report.erased_memory_ids)
    return {"revoked": consent_id, "lives_stopped": life_ids, "erased_memory_ids": erased_ids}


def check_cohort_eligibility(
    *, age: int, is_member_or_family: bool, has_consent_signed: bool
) -> None:
    """入组筛查 (spec §3.3): age / project-member / consent 三筛, fail-closed."""
    if age < MINOR_AGE_LIMIT:
        raise ConsentError(f"minor (age {age}) excluded from cohort (all four jurisdictions)")
    if is_member_or_family:
        raise ConsentError("project members and immediate family excluded (prereg criteria)")
    if not has_consent_signed:
        raise ConsentError("informed consent must be signed before cohort entry")
