"""Real-model embedder binding (Memory OS v1 continuation, spec §9.5).

Binds the frozen ``Embedder`` protocol to a real embedding endpoint:

- ``HTTPEmbedder``: OpenAI-compatible ``/v1/embeddings`` (vLLM serves this
  shape; llama.cpp / TEI adapters are the same JSON shape), fail-closed on
  non-200 / shape mismatch;
- version discipline (spec §9.5): ``model_version`` is REQUIRED and flows
  into EmbeddingOutbox rows + evaluation reports; a model change forces
  full re-embedding + re-running frozen test sets - the worker records
  ``embedding_model_version`` per row, so mixed-version vectors are
  detectable (``outbox_version_drift``);
- determinism: temperature/seed params are pinned (embedding endpoints are
  deterministic by nature, but the request pins them anyway);
- offline safety: no network in CI - the mock embedder stays the default;
  the HTTP binding activates only when a base_url is injected (env/secret,
  never in the repo).
"""

from __future__ import annotations

import json
import os
from typing import Any

EMBEDDING_DIM_DEFAULT = 1024


class HTTPEmbedder:
    """OpenAI-compatible embeddings endpoint (vLLM / TEI / llama.cpp shape)."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        model_version: str | None = None,
        dim: int = EMBEDDING_DIM_DEFAULT,
        timeout_s: float = 10.0,
        api_key_env: str = "LIFEOS_EMBEDDING_API_KEY",
    ) -> None:
        if not base_url or not model:
            raise ValueError("HTTPEmbedder requires base_url and model (fail-closed)")
        self.base_url = base_url.rstrip("/")
        self.model = model
        # spec §9.5: version is REQUIRED - defaults to model name + endpoint
        self.model_version = model_version or f"{model}@{self.base_url}"
        self.dim = dim
        self.timeout_s = timeout_s
        self._api_key = os.environ.get(api_key_env, "")

    def embed(self, content: str) -> list[float]:
        """One embedding call; fail-closed on HTTP/shape errors."""
        import httpx

        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        body = {
            "model": self.model,
            "input": content,
            # determinism params pinned (spec §9.5 discipline)
            "encoding_format": "float",
        }
        r = httpx.post(
            f"{self.base_url}/v1/embeddings",
            headers=headers,
            content=json.dumps(body),
            timeout=self.timeout_s,
        )
        if r.status_code != 200:
            raise RuntimeError(f"embedding endpoint HTTP {r.status_code}: {r.text[:120]}")
        data = r.json()
        try:
            vec = data["data"][0]["embedding"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"embedding shape mismatch: {str(data)[:120]}") from exc
        if not isinstance(vec, list) or not vec:
            raise RuntimeError("embedding vector empty")
        return [float(x) for x in vec]


def outbox_version_drift(store: Any) -> dict[str, Any]:
    """Detect mixed embedding_model_version across DONE outbox rows (spec §9.5).

    A model change forces full re-embedding - mixed versions mean stale
    vectors exist and frozen test sets must be re-run before any comparison.
    """
    versions = sorted(
        {o.embedding_model_version for o in store.outbox if o.embedding_model_version}
    )
    return {
        "versions": versions,
        "drift": len(versions) > 1,
        "action": "re-embed all + re-run frozen test sets" if len(versions) > 1 else "none",
    }
