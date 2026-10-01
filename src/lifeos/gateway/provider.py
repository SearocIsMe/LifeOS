"""Model Gateway: Provider A / Provider B behind one interface.

Design doc 01 §2.2. Both providers share the same contract so the
intent-consistency judge can compare intents pairwise. Local environment
adaptation (ADR-0005): both providers point at LOCAL vLLM OpenAI-compatible
endpoints (aiohttp/urllib-free, streaming-capable); the A/B distinction is
endpoint + served model name only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from lifeos.events.protocol import canonical_json, sha256_hex


class GatewayError(RuntimeError):
    """Raised when a provider call fails (fail-closed)."""


# Interpretation contract (design doc 01 §2.2): all judged fields enforced
# by guided decoding. Kept here (not evalharness) to avoid circular imports.
INTENT_SCHEMA: Mapping[str, Any] = {
    "type": "object",
    "properties": {
        "intent_type": {"type": "string", "enum": [
            "greet", "reflect_state", "recall_shared", "inquire_user",
            "comfort", "stay_quiet", "chat"]},
        "slot_key": {"type": ["string", "null"]},
        "safety_flag": {"type": "string", "enum": [
            "none", "sensitive", "restricted"]},
        "confidence": {"type": "number"},
    },
    "required": ["intent_type", "slot_key", "safety_flag"],
}


@dataclass(frozen=True)
class GatewayRequest:
    """One benchmark call: versioned prompt + hash + provider tag."""

    system_prompt: str
    prompt_template_id: str
    prompt_hash: str
    user_message: str
    provider_id: str
    params: Mapping[str, Any]


@dataclass(frozen=True)
class GatewayResponse:
    """Raw model output plus integrity fields (no interpretation here)."""

    provider_id: str
    raw_text: str
    request_prompt_hash: str  # echo of the prompt actually sent
    latency_ms: int


class Provider(Protocol):
    """Shared provider contract (A and B implement this identically)."""

    provider_id: str

    def complete(self, request: GatewayRequest) -> GatewayResponse: ...


class VLLMProvider:
    """OpenAI-compatible chat-completions client for a local vLLM server.

    Uses only the stdlib to avoid extra dependencies in the sandbox.
    Local endpoints require an API key (Bearer auth, from K8s Secret) and
    deterministic intents require thinking disabled (enable_thinking=false).
    """

    def __init__(
        self,
        provider_id: str,
        base_url: str,
        model: str,
        timeout_s: int = 60,
        api_key: str | None = None,
        enable_thinking: bool = False,
        force_json: bool = False,
        schema: Mapping[str, Any] | None = None,
    ):
        self.provider_id = provider_id
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_s = timeout_s
        self.api_key = api_key
        self.enable_thinking = enable_thinking
        self.force_json = force_json
        self.schema = schema

    def complete_with_json_schema(self, request: GatewayRequest, schema: Mapping[str, Any]) -> GatewayResponse:
        """Guided decoding with a JSON schema (vLLM structured output).

        Forces the output to conform to the schema (enum shapes enforced).
        Sampling param only - prompt/prompt_hash unchanged.
        """
        import json as _json
        import time
        import urllib.request

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_message},
            ],
            "temperature": request.params.get("temperature", 0.0),
            "max_tokens": request.params.get("max_tokens", 256),
            "stream": False,
            "response_format": {"type": "json_schema", "json_schema": {"name": "intent", "schema": schema}},
        }
        if not self.enable_thinking:
            payload["chat_template_kwargs"] = {"enable_thinking": False}
        url = f"{self.base_url}/chat/completions"
        body = _json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = urllib.request.Request(
            url,
            data=body,
            headers=headers,
            method="POST",
        )
        start = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as r:
                data = _json.loads(r.read().decode("utf-8"))
        except Exception as exc:
            raise GatewayError(f"{self.provider_id} call failed: {exc}") from exc
        latency_ms = int((time.monotonic() - start) * 1000)
        try:
            raw_text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise GatewayError(f"{self.provider_id} malformed response: {exc}") from exc
        return GatewayResponse(
            provider_id=self.provider_id,
            raw_text=raw_text,
            request_prompt_hash=request.prompt_hash,
            latency_ms=latency_ms,
        )

    def complete(self, request: GatewayRequest) -> GatewayResponse:
        import json as _json
        import time
        import urllib.request

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_message},
            ],
            "temperature": request.params.get("temperature", 0.0),
            "max_tokens": request.params.get("max_tokens", 256),
            "stream": False,
        }
        if not self.enable_thinking:
            payload["chat_template_kwargs"] = {"enable_thinking": False}
        if self.schema is not None:
            # Guided decoding (vLLM structured output): enum shapes enforced,
            # prompt echo impossible. Sampling param - prompt_hash unchanged.
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "intent", "schema": dict(self.schema)},
            }
        elif self.force_json:
            # Fallback: force the first char to '{' only.
            payload["response_format"] = {"type": "json_object"}
        url = f"{self.base_url}/chat/completions"
        body = _json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = urllib.request.Request(
            url,
            data=body,
            headers=headers,
            method="POST",
        )
        start = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                data = _json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # fail-closed: any transport error surfaces
            raise GatewayError(f"{self.provider_id} call failed: {exc}") from exc
        latency_ms = int((time.monotonic() - start) * 1000)
        try:
            raw_text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise GatewayError(f"{self.provider_id} malformed response: {exc}") from exc
        return GatewayResponse(
            provider_id=self.provider_id,
            raw_text=raw_text,
            request_prompt_hash=request.prompt_hash,
            latency_ms=latency_ms,
        )


class MockProvider:
    """Deterministic offline provider: same prompt_hash => same raw_text.

    hash = SHA-256 over canonical_json of the request; used for offline
    regression of the H1 harness (S4) without any network access.
    """

    def __init__(self, provider_id: str):
        self.provider_id = provider_id

    def complete(self, request: GatewayRequest) -> GatewayResponse:
        raw_text = (
            '{"intent_type": "chat", "slot_key": null, "safety_flag": "none", '
            '"confidence": 0.5, "echo_hash": "' + sha256_hex(canonical_json({
                "system_prompt": request.system_prompt,
                "user_message": request.user_message,
            }))[:16] + '"}'
        )
        return GatewayResponse(
            provider_id=self.provider_id,
            raw_text=raw_text,
            request_prompt_hash=request.prompt_hash,
            latency_ms=0,
        )


def make_provider(provider_id: str, config: Mapping[str, Any]) -> Provider:
    """Factory: {'kind': 'vllm'|'mock', 'base_url': ..., 'model': ..., 'api_key': ...}."""
    kind = config.get("kind", "mock")
    if kind == "vllm":
        return VLLMProvider(
            provider_id=provider_id,
            base_url=config["base_url"],
            model=config["model"],
            timeout_s=int(config.get("timeout_s", 60)),
            api_key=config.get("api_key"),
            enable_thinking=bool(config.get("enable_thinking", False)),
            force_json=bool(config.get("force_json", False)),
            schema=config.get("schema"),
        )
    if kind == "mock":
        return MockProvider(provider_id)
    raise GatewayError(f"unknown provider kind: {kind!r}")
