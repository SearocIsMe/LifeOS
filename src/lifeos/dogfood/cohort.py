"""Cohort management state machine (Phase 3 S3, design doc 01 §3.1).

Deterministic: same recruit input => same cohort state (testable, replay
recomputable). Flow: recruit -> screen (age / member / consent) -> enroll ->
withdraw. Standby capacity = 1.5x target (roadmap §5).

States: ``screening`` -> ``enrolled`` -> ``withdrawn``; any screen failure ->
``rejected`` (fail-closed, reason recorded).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from lifeos.consent import ConsentError, check_cohort_eligibility

STANDBY_RATIO = 1.5


class CohortError(ValueError):
    """Raised on invalid cohort transitions (fail-closed)."""


@dataclass
class Participant:
    external_user_id: str
    age: int
    jurisdiction: str
    is_member_or_family: bool
    has_consent_signed: bool
    status: str = "screening"
    enrolled_at: datetime | None = None
    withdrawn_at: datetime | None = None
    reject_reason: str = ""


@dataclass
class Cohort:
    """Deterministic cohort state machine (Pilot + formal share this shape)."""

    name: str
    target_size: int
    participants: dict[str, Participant] = field(default_factory=dict)

    @property
    def standby_capacity(self) -> int:
        return int(self.target_size * STANDBY_RATIO)

    # ------------------------------------------------------------------ #
    def screen_and_enroll(
        self,
        *,
        external_user_id: str,
        age: int,
        jurisdiction: str,
        is_member_or_family: bool,
        has_consent_signed: bool,
        at: datetime,
    ) -> Participant:
        """One deterministic transition: screen -> enroll / reject (fail-closed)."""
        if external_user_id in self.participants:
            raise CohortError(f"participant already exists: {external_user_id!r}")
        if len(self.enrolled) >= self.standby_capacity:
            raise CohortError(
                f"cohort full (standby capacity {self.standby_capacity} = {STANDBY_RATIO}x target)"
            )
        p = Participant(
            external_user_id=external_user_id,
            age=age,
            jurisdiction=jurisdiction,
            is_member_or_family=is_member_or_family,
            has_consent_signed=has_consent_signed,
        )
        try:
            check_cohort_eligibility(
                age=age,
                is_member_or_family=is_member_or_family,
                has_consent_signed=has_consent_signed,
            )
        except ConsentError as exc:
            p.status = "rejected"
            p.reject_reason = str(exc)
            self.participants[external_user_id] = p
            return p
        p.status = "enrolled"
        p.enrolled_at = at
        self.participants[external_user_id] = p
        return p

    def withdraw(self, *, external_user_id: str, at: datetime) -> Participant:
        """Deterministic withdrawal; caller then triggers user erase (spec §9.3)."""
        p = self.participants.get(external_user_id)
        if p is None:
            raise CohortError(f"unknown participant: {external_user_id!r}")
        if p.status != "enrolled":
            raise CohortError(f"participant not enrolled: {external_user_id} status={p.status}")
        p.status = "withdrawn"
        p.withdrawn_at = at
        return p

    # ------------------------------------------------------------------ #
    @property
    def enrolled(self) -> list[Participant]:
        return [p for p in self.participants.values() if p.status == "enrolled"]

    @property
    def rejected(self) -> list[Participant]:
        return [p for p in self.participants.values() if p.status == "rejected"]

    @property
    def withdrawn(self) -> list[Participant]:
        return [p for p in self.participants.values() if p.status == "withdrawn"]

    def summary(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "target_size": self.target_size,
            "standby_capacity": self.standby_capacity,
            "enrolled": len(self.enrolled),
            "rejected": len(self.rejected),
            "withdrawn": len(self.withdrawn),
        }
