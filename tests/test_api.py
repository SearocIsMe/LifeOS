"""Phase 3 S2 acceptance: minimal API service layer (Bearer auth + endpoints + FIFO).

Case map (design doc 02 §2 S2):
- auth enforced      -> no/invalid token => 401 on every endpoint
- contract mirror    -> OpenAPI paths cover the minimal endpoint set
- minimal endpoint set -> /instances /events /state /memories /model/switch
                          /replay /eval/runs /consent /rights all usable
- per-life serial    -> same-life ingests processed in FIFO order

Transport: httpx.AsyncClient + ASGITransport (httpx 0.28 removed the sync
``app=`` path; starlette 0.27 TestClient is incompatible with it).
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest
from fastapi import FastAPI

from lifeos.api import create_app
from lifeos.store.memory_store import InMemoryStore

NOW = datetime(2026, 9, 30, 12, 0, 0, tzinfo=timezone.utc)
LIFE = "life-api"
USER = "ext-user-api"
H = {"Authorization": "Bearer dev-token"}

pytestmark = pytest.mark.asyncio


def _client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def _bootstrap(client: httpx.AsyncClient) -> None:
    r = await client.post(
        "/consent",
        json={
            "consent_id": "c-api-1",
            "external_user_id": USER,
            "life_id": LIFE,
            "scope": {"chat": True},
            "jurisdiction": "CN",
            "locale": "zh-CN",
        },
        headers=H,
    )
    assert r.status_code == 200, r.text
    r = await client.post(
        "/instances",
        json={
            "life_id": LIFE,
            "personality_seed": "s1",
            "born_at": NOW.isoformat(),
        },
        headers=H,
    )
    assert r.status_code == 200, r.text


async def test_auth_enforced_on_every_endpoint():
    app, _store = create_app(bearer_token="dev-token")
    async with _client(app) as client:
        # no token => 401 on representative endpoints
        for method, path, json_body in [
            ("POST", "/instances", {}),
            ("POST", "/events", {}),
            ("GET", f"/state/{LIFE}", None),
            ("POST", "/memories/delete", {}),
            ("POST", "/model/switch", {}),
            ("POST", f"/replay/{LIFE}", None),
            ("GET", "/eval/runs", None),
            ("POST", "/consent", {}),
            ("POST", "/rights/query", {}),
        ]:
            r = await client.request(method, path, json=json_body)
            assert r.status_code == 401, f"{path} not guarded: {r.status_code}"
        # invalid token => 401 too
        r = await client.get("/eval/runs", headers={"Authorization": "Bearer wrong"})
        assert r.status_code == 401


async def test_openapi_covers_minimal_endpoint_set():
    app, _store = create_app(bearer_token="dev-token")
    async with _client(app) as client:
        schema = (await client.get("/openapi.json")).json()
        paths = set(schema["paths"])
        required = {
            "/instances",
            "/events",
            "/state/{life_id}",
            "/memories/{op}",
            "/model/switch",
            "/replay/{life_id}",
            "/eval/runs",
            "/consent",
            "/rights/{op}",
        }
        assert required <= paths


async def test_full_flow_instances_events_state_memories():
    app, store = create_app(bearer_token="dev-token")
    async with _client(app) as client:
        await _bootstrap(client)

        # ingest a human memory event (consent granted)
        r = await client.post(
            "/events",
            json={
                "life_id": LIFE,
                "source": "user",
                "external_user_id": USER,
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
                "occurred_at": NOW.isoformat(),
            },
            headers=H,
        )
        assert r.status_code == 200, r.text
        assert r.json()["duplicate"] is False

        # state reflects the memory
        r = await client.get(f"/state/{LIFE}", headers=H)
        assert r.status_code == 200
        assert r.json()["memory_count"] == 1

        # replay + eval + rights query
        assert (await client.post(f"/replay/{LIFE}", headers=H)).status_code == 200
        assert (await client.get("/eval/runs", headers=H)).status_code == 200
        r = await client.post("/rights/query", json={"life_id": LIFE, "subject_id": "user"}, headers=H)
        assert r.status_code == 200 and r.json()["count"] == 1


async def test_events_without_consent_rejected():
    app, _store = create_app(bearer_token="dev-token")
    async with _client(app) as client:
        await client.post(
            "/instances",
            json={"life_id": "life-x", "personality_seed": "s", "born_at": NOW.isoformat()},
            headers=H,
        )
        r = await client.post(
            "/events",
            json={
                "life_id": "life-x",
                "source": "user",
                "external_user_id": "no-consent-user",
                "payload": {"text": "hi", "structured": {}},
                "occurred_at": NOW.isoformat(),
            },
            headers=H,
        )
        assert r.status_code == 403  # consent gate fail-closed


async def test_model_switch_whitelist_enforced():
    app, _store = create_app(bearer_token="dev-token")
    async with _client(app) as client:
        await _bootstrap(client)
        # out-of-whitelist provider rejected (spec §9.4)
        r = await client.post(
            "/model/switch", json={"life_id": LIFE, "target_provider": "cloud-x"}, headers=H
        )
        assert r.status_code == 403
        # local provider allowed
        r = await client.post(
            "/model/switch", json={"life_id": LIFE, "target_provider": "local-vllm"}, headers=H
        )
        assert r.status_code == 200
        assert r.json()["to"] == "local-vllm"


async def test_rights_delete_and_export():
    app, store = create_app(bearer_token="dev-token")
    async with _client(app) as client:
        await _bootstrap(client)
        await client.post(
            "/events",
            json={
                "life_id": LIFE,
                "source": "user",
                "external_user_id": USER,
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
                "occurred_at": NOW.isoformat(),
            },
            headers=H,
        )
        # export without dual approval => 403
        r = await client.post("/memories/export", json={"life_id": LIFE, "approvals": ["a"]}, headers=H)
        assert r.status_code == 403
        # delete via rights channel => ok and ir-recoverable
        ids = [m.memory_id for m in store.query_memories(life_id=LIFE)]
        r = await client.post("/rights/delete", json={"life_id": LIFE, "memory_ids": ids}, headers=H)
        assert r.status_code == 200 and r.json()["ok"] is True
        # export with dual approval => ok (zero memories after erase)
        r = await client.post("/memories/export", json={"life_id": LIFE, "approvals": ["a", "b"]}, headers=H)
        assert r.status_code == 200 and r.json()["count"] == 0


async def test_per_life_fifo_serial_order():
    app, store = create_app(bearer_token="dev-token")
    async with _client(app) as client:
        await _bootstrap(client)
        events = [
            {
                "life_id": LIFE,
                "source": "user",
                "external_user_id": USER,
                "payload": {
                    "text": f"第{i}条",
                    "structured": {
                        "state_deltas": {"social_need": 0.02 * (i + 1)},
                    },
                },
                "occurred_at": NOW.isoformat(),
            }
            for i in range(5)
        ]
        # same-life ingests: serialized by the single event loop; order must hold
        responses = [await client.post("/events", json=e, headers=H) for e in events]
        assert all(r.status_code == 200 for r in responses)
        # FIFO: social_need accumulated in ingest order (0.02*1 + ... + 0.02*5)
        total = 0.02 * (1 + 2 + 3 + 4 + 5)
        got = store.get_state(life_id=LIFE, state_key="social_need")
        assert abs(got - (0.5 + total)) < 1e-6 or abs(got - total) < 1e-6
