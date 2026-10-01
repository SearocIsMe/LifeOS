"""Embedding providers (Memory OS v1): deterministic mock + pgvector-ready shape.

Two implementations of one protocol (``Embedder``):

- ``MockEmbedder``: deterministic hashing embedding - same content => same
  vector (CI/offline path, replay-safe, no network dependency);
- ``PgVectorEmbedder`` shape lands with the SQL channel (``vector_search``);
  the real model (spec §9.5: embedding model frozen per §9.5, version recorded
  in EmbeddingOutbox + evaluation reports) binds later without changing the
  protocol.

Determinism invariant (replay discipline): the mock is a PURE function of the
content string - re-running the worker re-derives identical vectors, so
replayed pipelines never produce embedding drift.
"""

from __future__ import annotations

import hashlib
import math
from typing import Protocol

EMBEDDING_MODEL_VERSION = "mock-hash@v1"
EMBEDDING_DIM = 64


class Embedder(Protocol):
    model_version: str
    dim: int

    def embed(self, content: str) -> list[float]: ...


class MockEmbedder:
    """Deterministic hash embedding: pure function of content (replay-safe)."""

    def __init__(self, dim: int = EMBEDDING_DIM) -> None:
        self.dim = dim
        self.model_version = EMBEDDING_MODEL_VERSION

    def embed(self, content: str) -> list[float]:
        out: list[float] = []
        seed = hashlib.sha256(content.encode("utf-8")).digest()
        # derive dim floats deterministically: sha256 chains per block
        block = seed
        while len(out) < self.dim:
            for b in block:
                out.append((b / 255.0) * 2.0 - 1.0)  # normalize to [-1, 1]
                if len(out) >= self.dim:
                    break
            block = hashlib.sha256(block).digest()
        # L2-normalize so cosine == dot product
        norm = math.sqrt(sum(x * x for x in out)) or 1.0
        return [x / norm for x in out]


class FailingEmbedder:
    """Test double: always raises (worker retry/SQL-degradation path)."""

    def __init__(self, model_version: str = "failing@test") -> None:
        self.model_version = model_version
        self.dim = EMBEDDING_DIM

    def embed(self, content: str) -> list[float]:
        raise RuntimeError("injected embedding failure (worker retry test)")
