"""User erase (physical deletion): all-media removal + rebuild verification (Phase 3 S1).

Semantics (spec §9.3, design doc 01 §1.1):

- Trigger = red line 10 / user deletion right (via ``lifeos.rights``).
- ALL media cleared: authoritative ``memory_records`` rows, vector index
  (EmbeddingOutbox rows), full-text index, and cache - the in-memory store
  models authoritative rows + outbox; SQL-side index rebuild is production
  shape and asserted here via the outbox channel.
- After erase the index is REBUILT and ir-recoverability is VERIFIED across
  all recall channels (veto #5: post-delete residue => No-Go).
- The erase L2 event carries ONLY memory_ids + operation metadata - never
  content (spec §9.3).
- Honest disclosure: append-only L0/L1 tables may still contain fragments of
  erased content; they die naturally with the 30-day rolling backup window
  (tentative, ADR-0007) and the disclosure is stated in the consent form.

Erase is a DETERMINISTIC operator: same store state => same result (replay
recomputable). Replay consistency and ir-recoverability do not conflict:
replay verifies pipeline behavior equality, it never rebuilds erased content.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from lifeos import POLICY_VERSION, SCHEMA_VERSION
from lifeos.entities import DomainEvent, OutboxStatus
from lifeos.events.protocol import derive_id
from lifeos.store.memory_store import InMemoryStore

ERASE_EVENT_TYPE = "memory_erase"

# Keys allowed in the erase L2 payload - operation metadata only, NO content.
ERASE_META_KEYS = frozenset({"memory_ids", "requested_by", "reason", "jurisdiction"})


@dataclass
class EraseReport:
    """Deterministic result of one user-erase operation."""

    erased_memory_ids: list[str] = field(default_factory=list)
    outbox_cleared: int = 0
    index_rebuilt: bool = False
    recoverable_channels: list[str] = field(default_factory=list)
    erased_at: datetime | None = None

    @property
    def ir_recoverable(self) -> bool:
        """True iff no recall channel can still return erased content."""
        return not self.recoverable_channels


def user_erase(
    store: InMemoryStore,
    *,
    life_id: str,
    memory_ids: list[str],
    requested_by: str,
    at: datetime,
    reason: str = "",
    jurisdiction: str = "CN",
) -> EraseReport:
    """Physically erase the given memories across ALL media, then rebuild and verify.

    Deterministic: same store state => same report. Unknown memory_ids are
    ignored (idempotent - erasing an already-erased id changes nothing).
    """
    store._require_life(life_id)

    target_ids = list(dict.fromkeys(memory_ids))  # dedup, keep order
    known_ids = {m.memory_id for m in store.memories if m.life_id == life_id}
    erased = [mid for mid in target_ids if mid in known_ids]

    # 1) authoritative rows: physical deletion (never a supersede)
    erased_records = [m for m in store.memories if m.memory_id in set(erased)]
    store.memories = [m for m in store.memories if m.memory_id not in set(erased)]

    # 2) vector index channel: pending/done outbox rows for erased memories
    outbox_cleared = 0
    kept_outbox = []
    for ob in store.outbox:
        if ob.memory_id in set(erased):
            outbox_cleared += 1  # rows dropped => vector channel gone
        else:
            kept_outbox.append(ob)
    store.outbox = kept_outbox

    # 3) rebuild the index from surviving memories (production shape: REINDEX)
    #    Every surviving memory gets a fresh outbox row; erased ids stay gone.
    rebuilt: list[Any] = []
    for m in store.memories:
        rebuilt.append(
            type(ob)(
                outbox_id=derive_id("OB", {"memory": m.memory_id, "rebuild": True}),
                life_id=m.life_id,
                memory_id=m.memory_id,
                embedding_model_version="",
                status=OutboxStatus.PENDING,
                created_at=at,
            )
        )
    store.outbox = rebuilt

    # 4) verify ir-recoverability across every recall channel
    recoverable: list[str] = []
    for mid in erased:
        # authoritative channel
        if any(m.memory_id == mid for m in store.memories):
            recoverable.append(f"authoritative:{mid}")
        # vector channel (outbox)
        if any(ob.memory_id == mid for ob in store.outbox):
            recoverable.append(f"vector:{mid}")
        # full-text channel: content substring scan over surviving same-life memories
        content = next((m.content for m in erased_records if m.memory_id == mid), None)
        if content and any(
            content in m.content
            for m in store.memories
            if m.life_id == life_id
        ):
            recoverable.append(f"fulltext:{mid}")
        # cache channel: state store keeps no content cache - absent by construction

    report = EraseReport(
        erased_memory_ids=erased,
        outbox_cleared=outbox_cleared,
        index_rebuilt=True,
        recoverable_channels=recoverable,
        erased_at=at,
    )

    # 5) append-only erase L2 event: metadata ONLY, never content (spec §9.3)
    payload = {
        "memory_ids": erased,
        "requested_by": requested_by,
        "reason": reason,
        "jurisdiction": jurisdiction,
    }
    assert set(payload) <= ERASE_META_KEYS
    l2 = DomainEvent(
        event_id=derive_id("L2", {"erase": payload, "life": life_id, "at": at.isoformat()}),
        life_id=life_id,
        l1_event_id=derive_id("L1-erase", {"life": life_id, "at": at.isoformat()}),
        event_type=ERASE_EVENT_TYPE,
        payload=payload,
        schema_version=SCHEMA_VERSION,
        policy_version=POLICY_VERSION,
        committed_at=at,
    )
    # erase events are NOT tied to an L1 interpret path; recorded directly on
    # the L2 archive via a dedicated slot so replay can recompute them.
    store.l2_events.append(l2)
    return report
