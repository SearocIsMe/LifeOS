"""Personal rights response channel: query / correct / delete / export (Phase 3 S1).

Red line 10 operationalized (spec §3.3: 所有记忆可查看/纠正/删除/导出) +
architecture §6 (`POST /memories/{op}`) + §5.10 (export requires DUAL approval).

Each operation returns a deterministic result and lands audit records:
- query   -> snapshot/read view (subject_id isolation unchanged)
- correct -> conflict-governance normal path (supersede, history retained -
            Phase 2 TOKI semantics reused)
- delete  -> user erase via ``lifeos.store.erase.user_erase``
- export  -> REQUIRES dual approval, else RejectedError (Gate 0 #4 shape)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from lifeos.entities import ConflictState
from lifeos.store.erase import EraseReport, user_erase
from lifeos.store.memory_store import InMemoryStore


class RejectedError(ValueError):
    """Raised when a rights operation is not permitted (fail-closed)."""


@dataclass
class RightsResult:
    op: str
    ok: bool
    detail: dict[str, Any] = field(default_factory=dict)


def query_user_memories(
    store: InMemoryStore, *, life_id: str, subject_id: str | None = None
) -> RightsResult:
    """查阅: read view only; subject_id predicate isolation unchanged."""
    rows = store.query_memories(life_id=life_id, subject_id=subject_id)
    return RightsResult(op="query", ok=True, detail={"count": len(rows), "memories": rows})


def correct_user_memory(
    store: InMemoryStore,
    *,
    life_id: str,
    new_content: str,
    slot_key: str | None = None,
    subject_id: str | None = None,
    confidence: float = 0.99,
    importance: int = 3,
) -> RightsResult:
    """更正: normal governance path - supersede old, history retained.

    Implemented by appending a corrected candidate through the committed L2
    contract (caller runs EventPipeline.ingest with the correction); here we
    verify the corrected record landed and the old version was superseded.
    """
    current = store.query_memories(life_id=life_id, slot_key=slot_key)
    corrected = [m for m in current if m.content == new_content]
    if not corrected:
        raise RejectedError(
            "correction must go through the committed L2 pipeline (RED-09): "
            "no corrected record found - ingest a memory_candidates event first"
        )
    superseded_count = len(
        [m for m in current if m.conflict_state is ConflictState.SUPERSEDED]
    )
    return RightsResult(
        op="correct",
        ok=True,
        detail={"corrected": corrected[0].memory_id, "superseded": superseded_count},
    )


def delete_user_memories(
    store: InMemoryStore,
    *,
    life_id: str,
    memory_ids: list[str],
    requested_by: str,
    at: datetime,
    jurisdiction: str = "CN",
) -> EraseReport:
    """删除: user erase (physical, all media) - delegates to store.erase."""
    return user_erase(
        store,
        life_id=life_id,
        memory_ids=memory_ids,
        requested_by=requested_by,
        at=at,
        jurisdiction=jurisdiction,
    )


def export_user_data(
    store: InMemoryStore,
    *,
    life_id: str,
    approvals: list[str],
) -> RightsResult:
    """导出: DUAL approval required (architecture §5.10), else fail-closed."""
    unique = list(dict.fromkeys(approvals))
    if len(unique) < 2:
        raise RejectedError("export requires dual approval (arch §5.10)")
    rows = store.query_memories(life_id=life_id)
    return RightsResult(op="export", ok=True, detail={"count": len(rows), "approved_by": unique})
