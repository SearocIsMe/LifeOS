"""EmbeddingOutbox worker (Memory OS v1): claim -> embed -> status/retry.

Semantics (arch §5.2 + design discipline):

- claims PENDING rows, embeds via an ``Embedder``, writes status/retry_count/
  embedded_at - the ONLY updatable outbox fields (entities note);
- retry: embed failure => retry_count += 1, status stays PENDING; a row that
  exceeds ``max_retries`` flips FAILED;
- idempotent: DONE rows are never re-claimed; re-running the worker over
  embedded content re-derives identical vectors (mock is pure);
- embedding failure NEVER blocks authoritative facts (arch §5.2): the worker
  catches, records, continues - recall degrades to SQL filtering via
  ``vector_search(..., fallback=True)``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from lifeos.entities import OutboxStatus
from lifeos.memory.embedding import Embedder
from lifeos.store.memory_store import InMemoryStore

DEFAULT_MAX_RETRIES = 3


@dataclass
class WorkerResult:
    claimed: int
    embedded: int
    retried: int
    failed: int
    model_version: str


def run_outbox_worker(
    store: InMemoryStore,
    *,
    embedder: Embedder,
    at: datetime,
    batch_size: int = 100,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> WorkerResult:
    """One worker pass over the outbox: claim PENDING, embed, update status.

    Deterministic given (outbox contents, embedder): same state => same result.
    """
    pending = [ob for ob in store.outbox if ob.status is OutboxStatus.PENDING][
        :batch_size
    ]
    embedded = retried = failed = 0
    for ob in pending:
        mem = next(
            (m for m in store.memories if m.memory_id == ob.memory_id), None
        )
        try:
            if mem is None:
                # authoritative row gone (erased): outbox row is stale -> FAILED
                raise RuntimeError(f"authoritative memory missing: {ob.memory_id}")
            _ = embedder.embed(mem.content)  # vector store write lands with SQL channel
        except Exception:
            new_retry = ob.retry_count + 1
            new_status = (
                OutboxStatus.FAILED if new_retry > max_retries else OutboxStatus.PENDING
            )
            store.outbox = [
                o.model_copy(
                    update={
                        "retry_count": new_retry,
                        "status": new_status,
                    }
                )
                if o.outbox_id == ob.outbox_id
                else o
                for o in store.outbox
            ]
            if new_status is OutboxStatus.FAILED:
                failed += 1
            else:
                retried += 1
            continue
        store.outbox = [
            o.model_copy(
                update={
                    "status": OutboxStatus.DONE,
                    "embedding_model_version": embedder.model_version,
                    "embedded_at": at,
                }
            )
            if o.outbox_id == ob.outbox_id
            else o
            for o in store.outbox
        ]
        embedded += 1
    return WorkerResult(
        claimed=len(pending),
        embedded=embedded,
        retried=retried,
        failed=failed,
        model_version=embedder.model_version,
    )


def outbox_stats(store: InMemoryStore) -> dict[str, Any]:
    """Outbox status counts (Studio/trend view)."""
    return {
        "pending": sum(1 for o in store.outbox if o.status is OutboxStatus.PENDING),
        "done": sum(1 for o in store.outbox if o.status is OutboxStatus.DONE),
        "failed": sum(1 for o in store.outbox if o.status is OutboxStatus.FAILED),
    }
