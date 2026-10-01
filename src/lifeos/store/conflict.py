"""Deterministic same-slot conflict resolution - TOKI operator semantics
(architecture §4/§5.2, roadmap S2, design phases/phase-2/01 §2.1).

When several ``MemoryRecord`` versions share the same ``slot_key`` within one
Life Instance, the adjudication order is FIXED and pure:

1. ``transaction_from`` newer wins (later write overrides);
2. ``valid_from`` newer wins (newest fact);
3. higher ``confidence`` wins (same-instant conflict by confidence);
4. all tied → ``memory_id`` lexicographic order (deterministic tie-break -
   reproducible, challengeable).

Invariants honored here:

- Resolution NEVER deletes history: losers are marked ``conflict_state=SUPERSEDED``
  with ``valid_to`` closed; the transaction history rows stay untouched
  (architecture §4 invariants). Winners keep/restore ``CURRENT``.
- Ambiguous manual queue: if step 1 is tied AND the ``confidence`` gap is
  ≤ 0.05, NO auto resolution is performed - candidates are flagged
  ``AMBIGUOUS`` and routed to the manual queue (``reports/ambiguous_queue.json``)
  for a named owner to resolve one by one.

Determinism: the SAME input records always produce the SAME outcome - no wall
clock, no randomness, no dict iteration order dependence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from lifeos.entities import ConflictState, MemoryRecord

# Confidence gap below which a same-slot tie is NOT auto-resolved (design 01 §2.1:
# 置信差 ≤ 0.05 → 入队列，不自动裁决). AMBIGUOUS_GAP_EPSILON guards the boundary
# against float error (e.g. 0.8 - 0.75 = 0.050000000000000044 > 0.05).
AMBIGUOUS_CONFIDENCE_GAP = 0.05
AMBIGUOUS_GAP_EPSILON = 1e-9


def _coerce(record: "MemoryRecord | dict[str, object]") -> MemoryRecord:
    """Accept dicts or MemoryRecord - coerce dicts via model_validate."""
    if isinstance(record, MemoryRecord):
        return record
    return MemoryRecord.model_validate(record)


@dataclass
class ConflictResolution:
    """Outcome of one same-slot resolution (pure data, no side effects)."""

    slot_key: str
    life_id: str
    winner: "MemoryRecord | dict[str, object] | None" = None
    superseded: list["MemoryRecord | dict[str, object]"] = field(default_factory=list)
    ambiguous: list["MemoryRecord | dict[str, object]"] = field(default_factory=list)

    @property
    def is_ambiguous(self) -> bool:
        return self.winner is None and bool(self.ambiguous)

    @property
    def is_tie(self) -> bool:
        return self.winner is not None and len(self.superseded) > 0

    def to_queue_row(self) -> dict[str, object]:
        """Row for reports/ambiguous_queue.json (manual queue)."""
        return {
            "life_id": self.life_id,
            "slot_key": self.slot_key,
            "conflict_state": ConflictState.AMBIGUOUS.value,
            "memory_ids": [m.memory_id for m in self.ambiguous],
            "confidence_gap": self._confidence_gap(),
            "owner": "lifeos-maintainer",  # named owner - resolve one by one
            "status": "pending",
        }

    def _confidence_gap(self) -> float:
        confs = [m.confidence for m in self.ambiguous]
        return round(max(confs) - min(confs), 6) if confs else 0.0


def _tie_by_id(records: Iterable[MemoryRecord]) -> MemoryRecord:
    """Step 4 tie-break: lexicographically smallest memory_id wins."""
    return min(records, key=lambda r: r.memory_id)


def resolve_slot(records: Iterable["MemoryRecord | dict[str, object]"]) -> ConflictResolution:
    """Resolve one same-slot tie PURELY (same input -> same output).

    Records are grouped by the caller; this function accepts ``MemoryRecord``
    instances or plain dicts (auto-coerced). All records must share one
    (life_id, slot_key). Returns a :class:`ConflictResolution` describing the
    winner, the superseded losers and/or the ambiguous routing.
    """
    records = [_coerce(r) for r in records]
    if not records:
        raise ValueError("resolve_slot requires at least one record")
    life_id, slot = records[0].life_id, records[0].slot_key

    # Step 1: newest transaction_from wins.
    newest_tx = max(r.transaction_from for r in records)
    tx_winners = [r for r in records if r.transaction_from == newest_tx]
    if len(tx_winners) == 1:
        return _as_resolved(life_id, slot, tx_winners[0], records)

    # Step 2: newest valid_from wins.
    newest_valid = max(r.valid_from for r in tx_winners)
    valid_winners = [r for r in tx_winners if r.valid_from == newest_valid]
    if len(valid_winners) == 1:
        return _as_resolved(life_id, slot, valid_winners[0], records)

    # Ambiguous gate: steps 1 AND 2 BOTH tied AND the confidence gap is
    # NEAR-but-not-equal (0 < gap <= 0.05) -> NO auto resolution, route to
    # the manual queue (design 01 §2.1). A perfect tie (gap == 0) is NOT
    # ambiguous - step 3/4 adjudicate it deterministically below.
    if len(valid_winners) > 1:
        confs = [r.confidence for r in valid_winners]
        gap = max(confs) - min(confs)
        if 0 < gap <= AMBIGUOUS_CONFIDENCE_GAP + AMBIGUOUS_GAP_EPSILON:
            return _as_ambiguous(life_id, slot, valid_winners)

    # Step 3: higher confidence wins; step 4: memory_id tie-break.
    best_conf = max(r.confidence for r in valid_winners)
    conf_winners = [r for r in valid_winners if r.confidence == best_conf]
    if len(conf_winners) == 1:
        return _as_resolved(life_id, slot, conf_winners[0], records)
    return _as_resolved(life_id, slot, _tie_by_id(conf_winners), records)


def _as_resolved(
    life_id: str, slot: str, winner: MemoryRecord, records: list[MemoryRecord]
) -> ConflictResolution:
    losers = [r for r in records if r.memory_id != winner.memory_id]
    return ConflictResolution(
        life_id=life_id, slot_key=slot, winner=winner, superseded=losers
    )


def _as_ambiguous(life_id: str, slot: str, candidates: list[MemoryRecord]) -> ConflictResolution:
    return ConflictResolution(life_id=life_id, slot_key=slot, ambiguous=candidates)


def mark_superseded(record: "MemoryRecord | dict[str, object]", valid_to: object) -> MemoryRecord:
    """Mark ONE loser superseded (never delete history, architecture §4)."""
    return _coerce(record).model_copy(
        update={
            "conflict_state": ConflictState.SUPERSEDED,
            "valid_to": valid_to,
        }
    )


def apply_resolution(
    resolution: ConflictResolution, *, at: object = None
) -> tuple[MemoryRecord, list[MemoryRecord]]:
    """Produce the records to persist for one resolution (pure, no store writes).

    Returns ``(winner, superseded_records)``. Winners are restored to CURRENT
    (a re-resolution may resurrect a previously superseded row); losers are
    marked SUPERSEDED with ``valid_to`` closed. Callers then persist these via
    the authoritative write path (commit_effects / db upsert) - this function
    itself never touches a store.
    """
    if resolution.is_ambiguous:
        raise ValueError("ambiguous resolution has no records to persist - manual queue only")
    if resolution.winner is None:
        raise ValueError("resolution has no winner")
    winner = _coerce(resolution.winner).model_copy(update={"conflict_state": ConflictState.CURRENT})
    loser_records = [mark_superseded(r, at) for r in resolution.superseded]
    return winner, loser_records
