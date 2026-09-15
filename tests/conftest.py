"""Shared fixtures: repo root path & DB availability probe."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


def _db_available() -> bool:
    try:
        from lifeos.store.db import get_engine, wait_for_db

        return wait_for_db(get_engine(), timeout_s=3)
    except Exception:
        return False


DB_AVAILABLE = _db_available()
