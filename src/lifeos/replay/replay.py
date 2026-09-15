"""Replay forensics (architecture §3.3, design doc 01 §9).

Recompute L2 from the ARCHIVED L1 via the SAME ``deterministic_commit`` and
compare against the stored L2 with canonical-JSON full-text equality (strongest
assertion, no field-compare assumptions). Wall-clock ``ingested_at`` is
non-semantic and excluded.

The report supports a tamper negative-control: a one-character change in an
archived ``output_json`` must be detected and localized (AC-05).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from lifeos.events.commit import deterministic_commit
from lifeos.events.protocol import canonical_json
from lifeos.store.memory_store import InMemoryStore


@dataclass
class ReplayReport:
    life_id: str
    from_seq: int
    to_seq: int | None
    total: int
    matched: int
    mismatched: list[dict[str, Any]] = field(default_factory=list)

    @property
    def consistency_rate(self) -> float:
        return self.matched / self.total if self.total else 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "life_id": self.life_id,
            "from_seq": self.from_seq,
            "to_seq": self.to_seq,
            "total": self.total,
            "matched": self.matched,
            "mismatched": self.mismatched,
            "consistency_rate": self.consistency_rate,
            "pass": self.total > 0 and self.matched == self.total,
        }


def _field_diff(a: dict[str, Any], b: dict[str, Any]) -> list[dict[str, Any]]:
    diffs = []
    for key in sorted(set(a) | set(b)):
        if canonical_json(a.get(key)) != canonical_json(b.get(key)):
            diffs.append(
                {"field": key, "stored": a.get(key), "recomputed": b.get(key)}
            )
    return diffs


def replay(
    store: InMemoryStore, *, life_id: str, from_seq: int = 0, to_seq: int | None = None
) -> ReplayReport:
    """Replay the L1 archive of one life and compare L2s (same commit function)."""
    l1s = store.range_l1(life_id=life_id, from_seq=from_seq, to_seq=to_seq)
    matched = 0
    mismatched: list[dict[str, Any]] = []

    for seq, l1 in enumerate(l1s, start=from_seq):
        stored = store.get_l2_by_l1(l1.event_id)
        if stored is None:
            mismatched.append(
                {"seq": seq, "l1_event_id": l1.event_id, "reason": "missing_l2"}
            )
            continue
        raw = store.get_raw(l1.raw_event_id)
        if raw is None:
            mismatched.append(
                {"seq": seq, "l1_event_id": l1.event_id, "reason": "missing_raw"}
            )
            continue

        recomputed = deterministic_commit(
            l1.output_json,  # from the archive - the LLM is NOT re-called
            life_id=stored.life_id,
            l1_event_id=l1.event_id,
            raw_event_id=l1.raw_event_id,
            occurred_at=raw.occurred_at,  # semantic time from the archived L0
            schema_version=stored.schema_version,
            policy_version=stored.policy_version,
            rules_version=stored.rules_version,
        )

        stored_canon = canonical_json(
            stored.model_dump(mode="json", exclude={"ingested_at"})
        )
        recomputed_canon = canonical_json(
            recomputed.model_dump(mode="json", exclude={"ingested_at"})
        )
        if stored_canon == recomputed_canon and stored.event_id == recomputed.event_id:
            matched += 1
        else:
            mismatched.append(
                {
                    "seq": seq,
                    "l1_event_id": l1.event_id,
                    "reason": "payload_mismatch",
                    "field_diff": _field_diff(
                        stored.model_dump(mode="json", exclude={"ingested_at"}),
                        recomputed.model_dump(mode="json", exclude={"ingested_at"}),
                    ),
                    "stored_hash": stored_canon,
                    "recomputed_hash": recomputed_canon,
                }
            )

    return ReplayReport(
        life_id=life_id,
        from_seq=from_seq,
        to_seq=to_seq,
        total=len(l1s),
        matched=matched,
        mismatched=mismatched,
    )
