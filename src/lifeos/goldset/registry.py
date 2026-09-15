"""Gold set registration (design doc 01 §11, 03 doc §6).

Registration freezes a validated set: content hash over canonical JSON of the
items, item count, kind and version go into ``GoldSetRegistry``. Evaluation
code must reference ``gold_set_id + version`` - never import YAML directly.

Registration REQUIRES complete dual-review signatures (03 doc §5.1-9) - the
validator may warn, but registration fails closed without them.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from lifeos.goldset.validator import validate_document


def content_hash(items: list[dict[str, Any]]) -> str:
    """SHA-256 over canonical JSON of the item list (order-sensitive by design:
    the frozen file order is part of the material identity)."""
    blob = json.dumps(items, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def build_manifest(
    kind: str,
    version: str,
    document: dict[str, Any],
    *,
    notes: str = "",
    frozen_at: datetime | None = None,
    expect_count: int | None = None,
) -> dict[str, Any]:
    """Validate + hash a gold set document into a registration manifest.

    ``expect_count=None`` enforces the real set sizes (50 facts / 30 scenarios).
    A non-default count is ONLY meaningful for format templates in tests - the
    CLI registration path never passes it, so real sets are always strict.
    """
    report = (
        validate_document(kind, document, expect_count=expect_count)
        if expect_count is not None
        else validate_document(kind, document)
    )
    if not report["valid"]:
        raise ValueError(
            f"gold set failed validation ({len(report['errors'])} errors); "
            "fix materials - never loosen the validator. First errors: "
            + "; ".join(report["errors"][:5])
        )
    review = document.get("review") or {}
    author, reviewer = review.get("author", ""), review.get("reviewer", "")
    if not author or not reviewer or author == reviewer:
        raise ValueError(
            "registration requires complete dual-review signatures "
            "(author != reviewer) - see phases/phase-0/03 doc §2.2"
        )

    return {
        "gold_set_id": kind,  # one registry row per kind+version
        "kind": kind,
        "version": version,
        "item_count": len(document["items"]),
        "content_hash": content_hash(document["items"]),
        "frozen_at": (frozen_at or datetime.now(timezone.utc)).isoformat(),
        "review": {
            "author": author,
            "reviewer": reviewer,
            "arbitrator": review.get("arbitrator", ""),
            "review_date": review.get("review_date", ""),
            "conflicts_resolved": review.get("conflicts_resolved", 0),
            "notes": review.get("notes", ""),
        },
        "notes": notes,
        "validation_report": report,
    }


def persist(engine: Any, manifest: dict[str, Any]) -> None:
    """Write the manifest into gold_set_registry (reject duplicate version)."""
    from sqlalchemy import text

    with engine.begin() as conn:
        existing = conn.execute(
            text(
                "SELECT 1 FROM gold_set_registry WHERE gold_set_id = :gid AND version = :ver"
            ),
            {"gid": manifest["gold_set_id"], "ver": manifest["version"]},
        ).first()
        if existing:
            raise ValueError(
                f"gold set {manifest['gold_set_id']} v{manifest['version']} already registered "
                "- frozen materials are immutable; register a NEW version instead"
            )
        conn.execute(
            text(
                """
                INSERT INTO gold_set_registry
                  (gold_set_id, kind, version, item_count, content_hash, frozen_at, notes)
                VALUES (:gid, :kind, :ver, :count, :chash, :frozen, :notes)
                """
            ),
            {
                "gid": manifest["gold_set_id"],
                "kind": manifest["kind"],
                "ver": manifest["version"],
                "count": manifest["item_count"],
                "chash": manifest["content_hash"],
                "frozen": datetime.fromisoformat(manifest["frozen_at"]),
                "notes": manifest["notes"],
            },
        )
