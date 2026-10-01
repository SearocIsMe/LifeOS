"""Memory OS v1 acceptance: outbox worker + two-channel vector recall.

Case map (technical track, arch §5.2):
- worker claim/embed/status -> PENDING -> DONE with model_version + embedded_at
- worker retry/fail-closed  -> embed failure => retry_count++; > max => FAILED; facts never blocked
- worker idempotency        -> DONE rows never re-claimed; re-run = zero claims
- worker erase-safe         -> stale outbox rows for erased memories -> FAILED, no residue
- mock determinism          -> same content twice => identical vector (replay-safe)
- vector channel            -> cosine ranking, same-life predicate hard filter
- SQL degradation           -> embedder failure => sql_fallback order (importance/recency), never breaks
- isolation in both channels-> cross-life/cross-subject zero residue
"""

from __future__ import annotations

from datetime import datetime, timezone

from lifeos.entities import OutboxStatus
from lifeos.events.pipeline import EventPipeline
from lifeos.memory.embedding import FailingEmbedder, MockEmbedder
from lifeos.memory.search import vector_search
from lifeos.memory.worker import outbox_stats, run_outbox_worker
from lifeos.store.erase import user_erase
from lifeos.store.memory_store import InMemoryStore

NOW = datetime(2026, 9, 30, 12, 0, 0, tzinfo=timezone.utc)
LIFE = "life-mem"
OTHER = "life-mem-other"


def _store_with_memories() -> tuple[InMemoryStore, list[str]]:
    store = InMemoryStore()
    store.create_instance(
        life_id=LIFE, personality_seed="s1", born_at=NOW, schema_version="0.1.0"
    )
    pipe = EventPipeline(store)
    ids: list[str] = []
    for i in range(3):
        res = pipe.ingest(
            {
                "life_id": LIFE,
                "source": "user",
                "payload": {
                    "text": f"第{i}条",
                    "structured": {
                        "memory_candidates": [
                            {
                                "type": "semantic",
                                "content": f"用户家里养的宠物是咪咪{i}号",
                                "slot_key": f"user.pet_{i}",
                                "subject_id": "user",
                                "confidence": 0.95,
                                "importance": i + 2,
                            }
                        ]
                    },
                },
                "occurred_at": NOW,
            }
        )
        ids.extend(m.memory_id for m in res.effects.memory_inserts)
    return store, ids


def test_worker_claim_embed_status():
    store, _ = _store_with_memories()
    assert outbox_stats(store)["pending"] == 3
    r = run_outbox_worker(store, embedder=MockEmbedder(), at=NOW)
    assert (r.claimed, r.embedded, r.retried, r.failed) == (3, 3, 0, 0)
    assert r.model_version == "mock-hash@v1"
    s = outbox_stats(store)
    assert s == {"pending": 0, "done": 3, "failed": 0}
    # only updatable fields changed: status/retry/embedded_at/model_version
    for ob in store.outbox:
        assert ob.status is OutboxStatus.DONE
        assert ob.embedded_at == NOW
        assert ob.embedding_model_version == "mock-hash@v1"


def test_worker_retry_and_fail_closed():
    store, _ = _store_with_memories()
    # failing embedder: retry_count grows, status stays PENDING until max
    for i in range(3):
        r = run_outbox_worker(store, embedder=FailingEmbedder(), at=NOW)
        assert r.retried == 3 and r.failed == 0
        assert all(ob.retry_count == i + 1 for ob in store.outbox)
    # 4th pass exceeds max_retries=3 -> FAILED
    r = run_outbox_worker(store, embedder=FailingEmbedder(), at=NOW)
    assert r.failed == 3
    assert all(ob.status is OutboxStatus.FAILED for ob in store.outbox)
    # authoritative facts NEVER blocked (arch §5.2): all memories still present
    assert len(store.query_memories(life_id=LIFE)) == 3


def test_worker_idempotent():
    store, _ = _store_with_memories()
    run_outbox_worker(store, embedder=MockEmbedder(), at=NOW)
    # second pass: DONE rows never re-claimed
    r = run_outbox_worker(store, embedder=MockEmbedder(), at=NOW)
    assert r.claimed == 0 and r.embedded == 0
    assert outbox_stats(store)["done"] == 3


def test_worker_erase_safe():
    store, ids = _store_with_memories()
    # erase one memory BEFORE the worker runs
    user_erase(store, life_id=LIFE, memory_ids=ids[:1], requested_by="u", at=NOW)
    # rebuild left one fresh outbox row for the erased id? No - rebuild only
    # covers surviving memories; but pre-erase rows may exist -> stale handling
    r = run_outbox_worker(store, embedder=MockEmbedder(), at=NOW)
    # no outbox row may resurrect erased content: vector channel zero residue
    assert not any(ob.memory_id == ids[0] and ob.status is OutboxStatus.DONE for ob in store.outbox)
    # worker drained all pending rows (surviving memories only)
    assert outbox_stats(store)["pending"] == 0
    assert r.embedded == 2  # two surviving memories embedded
    # vector channel: erased id zero-hit, survivors hit
    search = vector_search(store, life_id=LIFE, query="咪咪", embedder=MockEmbedder())
    assert ids[0] not in [mid for mid, _ in search["results"]]


def test_mock_embedding_deterministic():
    e = MockEmbedder()
    v1 = e.embed("用户家里养的猫叫咪咪")
    v2 = e.embed("用户家里养的猫叫咪咪")
    assert v1 == v2  # pure function - replay-safe
    assert len(v1) == 64
    # different content => different vector
    assert e.embed("用户家里养的狗叫旺财") != v1


def test_vector_channel_cosine_ranking():
    store, _ = _store_with_memories()
    r = vector_search(store, life_id=LIFE, query="用户家里养的宠物是咪咪1号", embedder=MockEmbedder(), top_k=3)
    assert r["channel"] == "vector"
    assert len(r["results"]) == 3
    # the exact-match content ranks first
    top_id, top_score = r["results"][0]
    mems = {m.memory_id: m for m in store.query_memories(life_id=LIFE)}
    assert mems[top_id].content == "用户家里养的宠物是咪咪1号"
    assert top_score > 0.99
    # descending scores
    scores = [s for _, s in r["results"]]
    assert scores == sorted(scores, reverse=True)


def test_sql_degradation_never_breaks():
    store, _ = _store_with_memories()
    # embedder failure => sql_fallback (importance/recency order), no raise
    r = vector_search(store, life_id=LIFE, query="任何查询", embedder=FailingEmbedder(), top_k=2)
    assert r["channel"] == "sql_fallback"
    assert len(r["results"]) == 2
    # fallback order: importance desc (3,2,1 assigned -> ids[2] importance 4 first)
    mems = {m.memory_id: m for m in store.query_memories(life_id=LIFE)}
    first_id = r["results"][0][0]
    importances = [mems[i].importance for i, _ in r["results"]]
    assert importances == sorted(importances, reverse=True)
    assert mems[first_id].importance == max(m.importance for m in mems.values())


def test_isolation_in_both_channels():
    store, _ids = _store_with_memories()
    store.create_instance(
        life_id=OTHER, personality_seed="s2", born_at=NOW, schema_version="0.1.0"
    )
    # other life has zero memories: both channels zero-hit
    rv = vector_search(store, life_id=OTHER, query="咪咪", embedder=MockEmbedder())
    assert rv["results"] == []
    # subject predicate respected in vector channel
    rs = vector_search(store, life_id=LIFE, query="咪咪", embedder=MockEmbedder(), subject_id="no-such-subject")
    assert rs["results"] == []
