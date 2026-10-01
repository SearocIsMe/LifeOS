"""Life Studio v0 debug console (arch §5.8, lightweight technical track).

Gradio-free equivalent: a FastAPI sub-app serving an HTML panel + JSON
endpoints over the EXISTING API app (no new deps, no duplicate logic).

Endpoints:
- GET /studio            single-page HTML console (status/intent/replay views)
- GET /studio/state      snapshot of one life (kernel_states + memory + provider)
- GET /studio/intents    recent intents with policy decisions (reason evidence chains)
- GET /studio/replay     replay forensic summary (L0/L1/L2 counts + consistency)
- GET /studio/outbox     embedding outbox stats (Memory OS v1 trend view)

Isolation unchanged: every read is life_id-scoped; the console holds no
state of its own.
"""
