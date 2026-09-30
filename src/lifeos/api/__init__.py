"""LifeOS minimal API service layer (Phase 3 S2, architecture §6 subset).

Dogfood-required subset of the frozen interface contract, with Bearer-token
auth on EVERY endpoint (arch §5.10: 决策门前不暴露公网) and OpenAPI
auto-generation whose schema mirrors ``lifeos.entities``.

Multi-instance concurrency model unchanged (arch §7): per-life FIFO serial
queues; no cross-instance shared mutable state; ``life_id`` predicates
everywhere.
"""

from lifeos.api.app import TOKEN_HEADER, create_app

__all__ = ["create_app", "TOKEN_HEADER"]
