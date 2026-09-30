"""Vector recall (Memory OS v1): two-channel search with SQL degradation.

Semantics (arch §5.2 / §5.10 / spec §9.3):

- ``vector_search`` ranks the same-life memory read view by cosine similarity
  between the query embedding and each memory's embedding (computed via the
  bound ``Embedder``; the pgvector SQL channel lands in the DB store - the
  in-memory channel models identical semantics for CI/replay);
- **SQL degradation** (arch §5.2): embedder failure or empty vector channel
  falls back to SQL-filter order (recency/importance) - recall NEVER breaks,
  only quality degrades;
- life_id / subject_id predicates are hard filters in BOTH channels (isolation
  unchanged); sensitive privacy is respected by the caller's read view;
- erase-safe: erased memories are physically gone from the read view, so both
  channels return zero residue (veto #5 holds in the vector channel too).
"""

from __future__ import annotations

from typing import Any

from lifeos.memory.embedding import Embedder
from lifeos.store.memory_store import InMemoryStore


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return -1.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5 or 1.0
    nb = sum(x * x for x in b) ** 0.5 or 1.0
    return dot / (na * nb)


def vector_search(
    store: InMemoryStore,
    *,
    life_id: str,
    query: str,
    embedder: Embedder,
    top_k: int = 5,
    subject_id: str | None = None,
) -> dict[str, Any]:
    """Two-channel recall: vector (cosine) with SQL-order degradation.

    Returns {channel, results: [(memory_id, score), ...]} - ``channel`` is
    ``vector`` or ``sql_fallback`` so callers/reports can attribute quality.
    """
    rows = store.query_memories(life_id=life_id, subject_id=subject_id)
    if not rows:
        return {"channel": "vector", "results": []}
    try:
        q = embedder.embed(query)
        scored = []
        for m in rows:
            v = embedder.embed(m.content)
            scored.append((m, _cosine(q, v)))
        scored.sort(key=lambda t: t[1], reverse=True)
        return {
            "channel": "vector",
            "results": [(m.memory_id, round(s, 6)) for m, s in scored[:top_k]],
        }
    except Exception:
        # SQL degradation: deterministic order = importance desc, recency desc
        fallback = sorted(rows, key=lambda m: (m.importance, m.transaction_from), reverse=True)
        return {
            "channel": "sql_fallback",
            "results": [(m.memory_id, 0.0) for m in fallback[:top_k]],
        }
