"""Real-model embedder binding acceptance (spec §9.5 freeze discipline).

Case map:
- version REQUIRED     -> model_version flows into worker rows (spec §9.5)
- fail-closed HTTP     -> non-200 / shape mismatch raise (no silent passthrough)
- version drift detect -> mixed versions across DONE rows => drift + re-embed action
- fail-closed ctor     -> missing base_url/model raises
- offline safety       -> mock stays the CI default; HTTP only with injected base_url
"""

from __future__ import annotations

import pytest

from lifeos.memory.real_embedder import HTTPEmbedder, outbox_version_drift


def test_ctor_requires_base_url_and_model():
    with pytest.raises(ValueError):
        HTTPEmbedder(base_url="", model="bge-m3")
    with pytest.raises(ValueError):
        HTTPEmbedder(base_url="http://x", model="")


def test_model_version_defaults_and_recorded():
    e = HTTPEmbedder(base_url="http://localhost:8001", model="bge-m3")
    assert e.model_version == "bge-m3@http://localhost:8001"  # spec §9.5 REQUIRED
    e2 = HTTPEmbedder(base_url="http://localhost:8001", model="bge-m3", model_version="bge-m3@v1.0")
    assert e2.model_version == "bge-m3@v1.0"  # explicit version wins


def test_embed_fail_closed_on_http_error():
    e = HTTPEmbedder(base_url="http://localhost:59999", model="bge-m3", timeout_s=1.0)
    with pytest.raises(Exception):
        e.embed("用户家里养的猫叫咪咪")  # connection refused / HTTP error -> raise


def test_version_drift_detection():
    class FakeStore:
        pass

    s = FakeStore()
    from lifeos.entities import EmbeddingOutbox, OutboxStatus
    from datetime import datetime, timezone

    NOW = datetime(2026, 9, 30, tzinfo=timezone.utc)

    def ob(vid: str) -> EmbeddingOutbox:
        return EmbeddingOutbox(
            outbox_id=f"o-{vid}", life_id="l", memory_id=f"m-{vid}",
            embedding_model_version=vid, status=OutboxStatus.DONE, created_at=NOW,
        )

    s.outbox = [ob("bge-m3@v1"), ob("bge-m3@v1")]
    d = outbox_version_drift(s)
    assert d["drift"] is False and d["action"] == "none"
    s.outbox = [ob("bge-m3@v1"), ob("bge-m3@v2")]
    d = outbox_version_drift(s)
    assert d["drift"] is True
    assert d["action"] == "re-embed all + re-run frozen test sets"  # spec §9.5
    assert d["versions"] == ["bge-m3@v1", "bge-m3@v2"]


def test_offline_safety_mock_is_default():
    """CI/offline path: the mock embedder stays the no-network default."""
    from lifeos.memory.embedding import EMBEDDING_MODEL_VERSION, MockEmbedder

    e = MockEmbedder()
    assert e.model_version == EMBEDDING_MODEL_VERSION
    assert e.embed("x") == e.embed("x")  # deterministic, no network
