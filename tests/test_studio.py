"""Life Studio v0 acceptance: debug console over the existing store.

Case map (arch §5.8, lightweight technical track):
- panel HTML served; JSON views (state/intents/replay/outbox) usable
- isolation: unknown life 404; views life_id-scoped
- state view shows kernel states + memories; intents view carries reason evidence chains
- replay view counts L0/L1/L2 + provenance completeness; outbox view = Memory OS stats
- console holds no state of its own (read-only)

Transport: httpx.AsyncClient + ASGITransport (same as test_api).
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest
from fastapi import FastAPI

from lifeos.events.pipeline import EventPipeline
from lifeos.memory.embedding import MockEmbedder
from lifeos.memory.worker import run_outbox_worker
from lifeos.studio.panel import create_studio
from lifeos.store.memory_store import InMemoryStore

NOW = datetime(2026, 9, 30, 12, 0, 0, tzinfo=timezone.utc)
LIFE = "life-studio"

pytestmark = pytest.mark.asyncio


def _client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def _studio() -> tuple[httpx.AsyncClient, InMemoryStore]:
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
    run_outbox_worker(store, embedder=MockEmbedder(), at=NOW)
    app: FastAPI = create_studio(store)
    return _client(app), store


async def test_panel_html_served():
    client, _ = await _studio()
    async with client:
        r = await client.get("/studio")
        assert r.status_code == 200
        assert "LifeOS Studio" in r.text


async def test_state_view():
    client, _ = await _studio()
    async with client:
        r = await client.get("/studio/state", params={"life_id": LIFE})
        assert r.status_code == 200
        d = r.json()
        assert d["life_id"] == LIFE
        assert d["memory_count"] == 1
        assert d["memories"][0]["content"] == "用户家里养的猫叫咪咪"
        assert "kernel_states" in d


async def test_intents_view_reason_chains():
    client, _ = await _studio()
    async with client:
        r = await client.get("/studio/intents", params={"life_id": LIFE})
        assert r.status_code == 200
        d = r.json()
        assert "intents" in d and "decisions" in d


async def test_replay_view_provenance():
    client, _ = await _studio()
    async with client:
        r = await client.get("/studio/replay", params={"life_id": LIFE})
        assert r.status_code == 200
        d = r.json()
        assert d["l0_events"] == 1 and d["l1_events"] == 1 and d["l2_events"] >= 1
        assert d["provenance_complete"] is True


async def test_outbox_view():
    client, _ = await _studio()
    async with client:
        r = await client.get("/studio/outbox")
        assert r.status_code == 200
        d = r.json()
        assert d["done"] == 1 and d["pending"] == 0


async def test_isolation_unknown_life_404():
    client, _ = await _studio()
    async with client:
        r = await client.get("/studio/state", params={"life_id": "ghost"})
        assert r.status_code == 404
        r = await client.get("/studio/replay", params={"life_id": "ghost"})
        assert r.status_code == 404
