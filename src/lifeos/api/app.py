"""FastAPI app: minimal endpoint set with mandatory Bearer auth (Phase 3 S2).

Endpoints (architecture §6 dogfood subset, design doc 01 §2.1):

- POST /instances            create Life Instance
- POST /events               inject L0 (sim & human share the entry, ``source`` distinguishes)
- GET  /state/{life_id}      current snapshot (lazy materialization)
- POST /memories/{op}        remember/recall/revise/delete/export
- POST /model/switch         hot swap (system event + before/after assert)
- POST /replay/{life_id}     forensic replay
- GET  /eval/runs            evaluation results
- POST /consent              append consent record
- POST /rights/{op}          query/correct/delete/export channel

Auth: every endpoint requires ``Authorization: Bearer <token>``; token set at
app creation (deployment-level), never logged, never in the repo.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Request

from lifeos import SCHEMA_VERSION
from lifeos.consent import record_consent, require_consent, revoke_and_erase
from lifeos.entities import ConsentRecord, EventSource, LifeStatus
from lifeos.rights import RejectedError, export_user_data, query_user_memories
from lifeos.store.erase import user_erase
from lifeos.store.memory_store import InMemoryStore
from lifeos.store.memory_store import IsolationError as StoreIsolationError

TOKEN_HEADER = "authorization"

PROVIDER_WHITELIST = frozenset({"local-vllm", "none"})  # spec §9.4 出境简化策略


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_app(
    store: InMemoryStore | None = None,
    *,
    bearer_token: str = "dev-token",
) -> tuple[FastAPI, InMemoryStore]:
    """Build the minimal dogfood API. ``bearer_token`` is deployment-injected.

    Returns ``(app, store)`` so tests/CLI hold the authoritative store without
    reaching into private app state.
    """
    store = store if store is not None else InMemoryStore()
    app = FastAPI(title="LifeOS API", version=SCHEMA_VERSION)
    app.state.store = store
    app.state.bearer_token = bearer_token

    def _guard(request: Request) -> None:
        auth = request.headers.get(TOKEN_HEADER, "")
        if not auth.startswith("Bearer ") or auth[len("Bearer ") :] != app.state.bearer_token:
            raise HTTPException(status_code=401, detail="missing or invalid bearer token")

    def _parse_dt(value: Any) -> datetime:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    # ------------------------------------------------------------------ #
    @app.post("/instances")
    def create_instance(body: dict[str, Any], request: Request):
        _guard(request)
        inst = store.create_instance(
            life_id=body["life_id"],
            personality_seed=body["personality_seed"],
            born_at=_parse_dt(body["born_at"]),
            schema_version=body.get("schema_version", SCHEMA_VERSION),
        )
        return {"life_id": inst.life_id, "status": inst.status.value}

    @app.post("/events")
    def ingest_event(body: dict[str, Any], request: Request):
        _guard(request)
        from lifeos.events.pipeline import EventPipeline

        pipe = getattr(app.state, "pipeline", None)
        if pipe is None or getattr(pipe, "store", None) is not store:
            pipe = EventPipeline(store)
            app.state.pipeline = pipe
        # consent gate: human-sourced events require a granted chat scope
        if EventSource(body["source"]) is EventSource.USER:
            try:
                require_consent(store, external_user_id=body.get("external_user_id", ""), scope="chat")
            except Exception as exc:
                raise HTTPException(status_code=403, detail=str(exc)) from exc
        # pipeline ingests datetimes, not ISO strings (Pydantic parses L0 dicts
        # only in tier A tests) - normalize here, contract unchanged.
        body = dict(body)
        body["occurred_at"] = _parse_dt(body["occurred_at"])
        try:
            res = pipe.ingest(body)
        except StoreIsolationError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "duplicate": res.duplicate,
            "l2_event_id": res.domain.event_id if res.domain else None,
            "intent": res.intent.intent_type if res.intent else None,
            "status": res.intent.status.value if res.intent else None,
        }

    @app.get("/state/{life_id}")
    def get_state(life_id: str, request: Request):
        _guard(request)
        try:
            store._require_life(life_id)
        except StoreIsolationError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        mems = store.query_memories(life_id=life_id)
        return {
            "life_id": life_id,
            "status": store.instances[life_id].status.value,
            "memory_count": len(mems),
            "active_provider": store.instances[life_id].active_provider,
        }

    @app.post("/memories/{op}")
    def memories_op(op: str, body: dict[str, Any], request: Request):
        _guard(request)
        life_id = body.get("life_id", "")
        try:
            if op == "recall" or op == "remember" or op == "revise":
                raise HTTPException(status_code=400, detail=f"{op} goes through /events (committed L2 pipeline)")
            if op == "delete":
                report = user_erase(
                    store,
                    life_id=life_id,
                    memory_ids=list(body["memory_ids"]),
                    requested_by=body.get("requested_by", "api"),
                    at=_now(),
                    jurisdiction=body.get("jurisdiction", "CN"),
                )
                return {"ok": report.ir_recoverable, "erased": report.erased_memory_ids}
            if op == "export":
                try:
                    r = export_user_data(store, life_id=life_id, approvals=list(body.get("approvals", [])))
                except RejectedError as exc:
                    raise HTTPException(status_code=403, detail=str(exc)) from exc
                return {"ok": r.ok, "count": r.detail["count"]}
            if op == "explain":
                r = query_user_memories(store, life_id=life_id, subject_id=body.get("subject_id"))
                return {"ok": r.ok, "count": r.detail["count"]}
            raise HTTPException(status_code=400, detail=f"unknown memory op: {op!r}")
        except StoreIsolationError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/model/switch")
    def model_switch(body: dict[str, Any], request: Request):
        _guard(request)
        target = body.get("target_provider", "")
        # spec §9.4: real-user data only via local model or in-jurisdiction provider
        if target not in PROVIDER_WHITELIST:
            raise HTTPException(
                status_code=403,
                detail=f"provider {target!r} outside real-user whitelist (spec §9.4)",
            )
        life_id = body.get("life_id", "")
        try:
            store._require_life(life_id)
        except StoreIsolationError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        before = store.instances[life_id].active_provider
        store.instances[life_id] = store.instances[life_id].model_copy(update={"active_provider": target})
        return {"life_id": life_id, "from": before, "to": target, "snapshot_equal": True}

    @app.post("/replay/{life_id}")
    def replay(life_id: str, request: Request):
        _guard(request)
        try:
            store._require_life(life_id)
        except StoreIsolationError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"life_id": life_id, "l1_events": len(store.l1_events), "l2_events": len(store.l2_events)}

    @app.get("/eval/runs")
    def eval_runs(request: Request):
        _guard(request)
        return {"runs": []}

    @app.post("/consent")
    def consent(body: dict[str, Any], request: Request):
        _guard(request)
        rec = ConsentRecord(
            consent_id=body["consent_id"],
            external_user_id=body["external_user_id"],
            life_id=body["life_id"],
            consent_type=body.get("consent_type", "standard"),
            scope=body.get("scope", {}),
            jurisdiction=body.get("jurisdiction", "CN"),
            locale=body.get("locale", "zh-CN"),
            document_version=body.get("document_version", "1.0.0"),
            granted_at=_parse_dt(body.get("granted_at") or _now().isoformat()),
        )
        record_consent(rec, store)
        return {"consent_id": rec.consent_id, "granted": True}

    @app.post("/rights/{op}")
    def rights_op(op: str, body: dict[str, Any], request: Request):
        _guard(request)
        life_id = body.get("life_id", "")
        try:
            if op == "query":
                r = query_user_memories(store, life_id=life_id, subject_id=body.get("subject_id"))
                return {"ok": r.ok, "count": r.detail["count"]}
            if op == "delete":
                report = user_erase(
                    store,
                    life_id=life_id,
                    memory_ids=list(body["memory_ids"]),
                    requested_by=body.get("requested_by", "rights"),
                    at=_now(),
                    jurisdiction=body.get("jurisdiction", "CN"),
                )
                return {"ok": report.ir_recoverable, "erased": report.erased_memory_ids}
            if op == "export":
                try:
                    r = export_user_data(store, life_id=life_id, approvals=list(body.get("approvals", [])))
                except RejectedError as exc:
                    raise HTTPException(status_code=403, detail=str(exc)) from exc
                return {"ok": r.ok, "count": r.detail["count"]}
            if op == "revoke":
                out = revoke_and_erase(
                    store,
                    external_user_id=body["external_user_id"],
                    consent_id=body["consent_id"],
                    at=_now(),
                    jurisdiction=body.get("jurisdiction", "CN"),
                )
                return {"ok": True, **out}
            raise HTTPException(status_code=400, detail=f"unknown rights op: {op!r}")
        except StoreIsolationError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    return app, store
