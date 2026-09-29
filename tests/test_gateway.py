"""S2 acceptance cases: Model Gateway dual Provider (design doc 02 §2 S2)."""

import pytest

from lifeos.gateway import (
    GatewayError,
    GatewayRequest,
    MockProvider,
    make_provider,
)

REQUEST = GatewayRequest(
    system_prompt="你是 LifeOS 内核。",
    prompt_template_id="system@phase1-1",
    prompt_hash="a" * 64,
    user_message="今天有点累。",
    provider_id="A",
    params={"temperature": 0.0, "max_tokens": 128},
)


class TestDualProviderContract:
    def test_mock_deterministic_same_hash(self):
        pa = make_provider("A", {"kind": "mock"})
        pb = make_provider("B", {"kind": "mock"})
        ra = pa.complete(REQUEST)
        rb = pb.complete(REQUEST)
        assert ra.request_prompt_hash == rb.request_prompt_hash == ("a" * 64)
        # same inputs: both providers echo the prompt hash they were given
        assert ra.provider_id == "A" and rb.provider_id == "B"

    def test_mock_replayable(self):
        pa = MockProvider("A")
        r1 = pa.complete(REQUEST)
        r2 = pa.complete(REQUEST)
        assert r1.raw_text == r2.raw_text  # deterministic for offline harness

    def test_factory_rejects_unknown_kind(self):
        with pytest.raises(GatewayError):
            make_provider("C", {"kind": "claude"})

    def test_factory_builds_vllm_without_network(self):
        # constructing must not touch the network
        p = make_provider("A", {"kind": "vllm", "base_url": "http://127.0.0.1:8000/v1", "model": "m"})
        assert p.provider_id == "A"
