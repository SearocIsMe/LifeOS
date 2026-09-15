"""Canonical JSON, hashing and deterministic ID derivation.

These primitives are the basis of replay equality: the same logical content
must always produce the same bytes regardless of dict insertion order.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(obj: Any) -> str:
    """Stable serialization: sorted keys, no whitespace, UTF-8, CJK preserved."""
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_hex(obj: Any) -> str:
    """SHA-256 over canonical_json(obj)."""
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


def derive_id(prefix: str, obj: Any) -> str:
    """Deterministic content-addressed ID: ``<prefix>-<first 24 hex chars>``."""
    return f"{prefix}-{sha256_hex(obj)[:24]}"
