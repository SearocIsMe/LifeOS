"""Real-arm generation client (four-baseline comparison, spec §4.4).

One protocol, two implementations:

- ``VLLMChatClient``: OpenAI-compatible ``/v1/chat/completions`` (vLLM shape,
  same as the H1 real-arm client); temperature=0 + seed pinned in EVERY
  request (determinism discipline, spec §9.5); fail-closed on non-200 /
  missing choices;
- ``MockChatClient``: deterministic echo (CI/offline default, no network) -
  same prompt => same output; any prompt change flips the output.

Offline safety: the mock stays the CI default; the HTTP binding activates
only when a base_url is injected (env/secret, never in the repo).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Protocol

GEN_TEMPERATURE = 0.0


class ChatClient(Protocol):
    model: str

    def build_request(self, messages: list[dict[str, str]]) -> dict[str, Any]: ...
    def complete(self, messages: list[dict[str, str]]) -> "ChatResponse": ...


@dataclass
class ChatResponse:
    model: str
    content: str
    usage: dict[str, Any]
    latency_ms: float


class VLLMChatClient:
    """OpenAI-compatible chat client (vLLM / TEI / llama.cpp shape)."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        seed: int = 20260930,
        timeout_s: float = 30.0,
        api_key_env: str = "LIFEOS_GEN_API_KEY",
    ) -> None:
        if not base_url or not model:
            raise ValueError("VLLMChatClient requires base_url and model (fail-closed)")
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.seed = seed
        self.timeout_s = timeout_s
        self._api_key = os.environ.get(api_key_env, "")

    def build_request(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        """OpenAI-compatible request body; determinism params pinned."""
        return {
            "model": self.model,
            "messages": messages,
            "temperature": GEN_TEMPERATURE,
            "seed": self.seed,
            "stream": False,
        }

    def resolve_model(self) -> str:
        """Resolve the endpoint's actual model id from /v1/models (spec §9.5).

        vLLM serves official-prefixed ids (e.g. ``Qwen/Qwen3.6-35B-A3B-FP8``)
        that may differ from the short name in reports; a wrong id is a
        NotFound 404. Fail-closed: no models / ambiguous id raises.
        """
        import httpx

        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        r = httpx.get(f"{self.base_url}/models", headers=headers, timeout=self.timeout_s)
        if r.status_code != 200:
            raise RuntimeError(f"models endpoint HTTP {r.status_code}")
        data = r.json()
        ids = [m["id"] for m in data.get("data", []) if m.get("id")]
        if not ids:
            raise RuntimeError("models endpoint returned no ids")
        if len(ids) == 1:
            return ids[0]
        # multiple: prefer the id containing the short model name, else fail
        matches = [i for i in ids if self.model.split("/")[-1] in i]
        if len(matches) != 1:
            raise RuntimeError(f"ambiguous model ids {ids}; pass the exact id")
        return matches[0]

    def complete(self, messages: list[dict[str, str]]) -> ChatResponse:
        """One chat call; fail-closed on HTTP/shape errors.

        The model id is resolved from /v1/models on first use (vLLM serves
        official-prefixed ids); the resolved id is cached and recorded.
        """
        import time

        import httpx

        if getattr(self, "_resolved_model", None) is None:
            self._resolved_model = self.resolve_model()
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        body = self.build_request(messages)
        body["model"] = self._resolved_model  # endpoint's actual id (404 guard)
        start = time.perf_counter()
        r = httpx.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            content=json.dumps(body),
            timeout=self.timeout_s,
        )
        latency_ms = (time.perf_counter() - start) * 1000.0
        if r.status_code != 200:
            raise RuntimeError(f"chat endpoint HTTP {r.status_code}: {r.text[:120]}")
        data = r.json()
        try:
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"chat shape mismatch: {str(data)[:120]}") from exc
        return ChatResponse(
            model=self.model,
            content=content,
            usage=usage,
            latency_ms=round(latency_ms, 3),
        )


class MockChatClient:
    """Deterministic echo client (CI/offline default): same prompt => same output."""

    def __init__(self, model: str = "mock-gen", seed: int = 20260930) -> None:
        if not model:
            raise ValueError("MockChatClient requires model (fail-closed)")
        self.model = model
        self.seed = seed

    def build_request(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        return {
            "model": self.model,
            "messages": messages,
            "temperature": GEN_TEMPERATURE,
            "seed": self.seed,
            "stream": False,
        }

    def complete(self, messages: list[dict[str, str]]) -> ChatResponse:
        from lifeos.events.protocol import sha256_hex

        digest = sha256_hex(messages)
        content = f"[mock-gen seed={self.seed} hash={digest[:16]}] {json.dumps(messages, ensure_ascii=False)}"
        return ChatResponse(
            model=self.model,
            content=content,
            usage={"prompt_tokens": sum(len(m["content"]) for m in messages), "completion_tokens": len(content)},
            latency_ms=0.0,
        )
