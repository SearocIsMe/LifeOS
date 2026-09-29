"""LifeOS Model Gateway (Phase 1, S2): Provider A/B behind one contract.

Import-discipline anchor; see provider.py for the environment adaptation
(both providers on local vLLM endpoints, ADR-0005).
"""

from lifeos.gateway.provider import (
    GatewayError,
    GatewayRequest,
    GatewayResponse,
    MockProvider,
    Provider,
    VLLMProvider,
    make_provider,
)

__all__ = [
    "GatewayError",
    "GatewayRequest",
    "GatewayResponse",
    "MockProvider",
    "Provider",
    "VLLMProvider",
    "make_provider",
]
