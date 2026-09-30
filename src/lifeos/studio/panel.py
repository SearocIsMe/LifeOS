"""Life Studio panel: FastAPI sub-app over the existing API app (arch §5.8).

No new dependencies, no duplicate logic - every view reads the SAME
InMemoryStore the API app holds. The HTML console renders three views
(status / intents / replay) client-side from the JSON endpoints below.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException

from lifeos.memory.worker import outbox_stats
from lifeos.store.memory_store import InMemoryStore
from lifeos.store.memory_store import IsolationError as StoreIsolationError

_PANEL_HTML = """<!doctype html>
<html lang="zh"><head><meta charset="utf-8"><title>LifeOS Studio</title>
<style>
body{font-family:system-ui,sans-serif;margin:2rem;background:#0f172a;color:#e2e8f0}
h1{font-size:1.3rem} h2{font-size:1.05rem;margin-top:1.5rem}
input,button{padding:.4rem .6rem;border-radius:6px;border:1px solid #334155;background:#1e293b;color:#e2e8f0}
button{cursor:pointer} pre{background:#1e293b;padding:.8rem;border-radius:8px;overflow:auto}
table{border-collapse:collapse;width:100%} td,th{border:1px solid #334155;padding:.4rem;text-align:left}
</style></head><body>
<h1>LifeOS Studio 调试台</h1>
<p>life_id: <input id="life" value="life-demo"> <button onclick="loadAll()">加载</button></p>
<h2>状态快照</h2><pre id="state">-</pre>
<h2>意图流（reason 证据链）</h2><pre id="intents">-</pre>
<h2>回放取证</h2><pre id="replay">-</pre>
<h2>Embedding Outbox</h2><pre id="outbox">-</pre>
<script>
async function jget(u){const r=await fetch(u);if(!r.ok){return 'HTTP '+r.status}return r.json()}
async function loadAll(){
  const life=document.getElementById('life').value||'life-demo';
  const q='?life_id='+encodeURIComponent(life);
  document.getElementById('state').textContent=JSON.stringify(await jget('/studio/state'+q),null,2);
  document.getElementById('intents').textContent=JSON.stringify(await jget('/studio/intents'+q),null,2);
  document.getElementById('replay').textContent=JSON.stringify(await jget('/studio/replay'+q),null,2);
  document.getElementById('outbox').textContent=JSON.stringify(await jget('/studio/outbox'),null,2);
}
</script></body></html>"""


def create_studio(store: InMemoryStore) -> FastAPI:
    """Build the Studio sub-app; ``store`` is the API app's authoritative store."""
    app = FastAPI(title="LifeOS Studio", version="0.1.0")

    def _require(life_id: str) -> None:
        try:
            store._require_life(life_id)
        except StoreIsolationError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/studio")
    def panel() -> Any:
        from fastapi.responses import HTMLResponse

        return HTMLResponse(_PANEL_HTML)

    @app.get("/studio/state")
    def state(life_id: str) -> Any:
        _require(life_id)
        inst = store.instances[life_id]
        mems = store.query_memories(life_id=life_id)
        # kernel states via the store's public read view (get_state injects
        # default 0.5 for never-materialized keys - the console shows raw)
        kernel = {
            key: store.get_state(life_id=life_id, state_key=key)
            for key in store.kernel_state_keys()
        }
        return {
            "life_id": life_id,
            "status": inst.status.value,
            "active_provider": inst.active_provider,
            "kernel_states": kernel,
            "memory_count": len(mems),
            "memories": [
                {"memory_id": m.memory_id, "type": m.type.value, "slot_key": m.slot_key,
                 "content": m.content, "importance": m.importance,
                 "privacy_level": m.privacy_level.value, "conflict_state": m.conflict_state.value}
                for m in mems
            ],
        }

    @app.get("/studio/intents")
    def intents(life_id: str, limit: int = 20) -> Any:
        _require(life_id)
        rows = [
            {"intent_id": i.intent_id, "intent_type": i.intent_type, "modality": i.modality.value,
             "status": i.status.value, "created_at": i.created_at.isoformat(), "reason": i.reason}
            for i in store.intents if i.life_id == life_id
        ][-limit:]
        decisions = [
            {"decision_id": d.decision_id, "intent_id": d.intent_id, "result": d.result.value,
             "reason": d.reason, "decided_at": d.decided_at.isoformat()}
            for d in store.decisions
        ]
        return {"intents": rows, "decisions": decisions}

    @app.get("/studio/replay")
    def replay(life_id: str) -> Any:
        _require(life_id)
        l1s = store.range_l1(life_id=life_id)
        return {
            "life_id": life_id,
            "l0_events": sum(1 for r in store.raw_events if r.life_id == life_id),
            "l1_events": len(l1s),
            "l2_events": len(store.l2_events),
            "provenance_complete": all(
                l.input_hash and l.output_json and l.extractor_version and l.interpreted_at
                for l in l1s
            ),
        }

    @app.get("/studio/outbox")
    def outbox() -> Any:
        return outbox_stats(store)

    return app
