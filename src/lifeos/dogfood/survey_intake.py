"""Survey intake primitives (方案 A, user-confirmed 2026-10-01).

email 只作单向哈希防重，原文不入库；作答数据匿名化不变（spec §9）：

- ``load_survey``: load one survey instance (``survey/LIFE-BT-XXX.json``)
  with its 24 trials + real-arm texts; fail-closed on unknown ids;
- ``email_hash``: one-way SHA-256 over the normalized email (lowercase,
  stripped) — 原文不可反推, never persisted;
- ``record_hash`` / ``check_duplicate``: the anti-double-submission ledger
  (``submitted_hashes.json``) — SEPARATE from ``responses.jsonl`` (the
  anonymized answer data), managed under the same 30-day backup window
  discipline; a hash seen before => duplicate => submission voided (作废).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[3]
SURVEY_DIR = REPO / "survey"
LEDGER_FILENAME = "submitted_hashes.json"


def load_survey(survey_or_subject_id: str) -> dict[str, Any]:
    """Load one survey instance; fail-closed on unknown ids (no silent fallback)."""
    sid = survey_or_subject_id.strip()
    for name in (f"{sid}.json", f"{sid}.json" if sid.startswith("LIFE-BT") else f"{sid}.json"):
        p = SURVEY_DIR / name
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    # also accept bare seq
    if sid.isdigit():
        p = SURVEY_DIR / f"LIFE-BT-{int(sid):03d}.json"
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    raise FileNotFoundError(f"unknown survey instance: {sid!r} (survey/ has LIFE-BT-000..059)")


def email_hash(email: str) -> str:
    """One-way SHA-256 over the normalized email (lowercase, stripped).

    原文不可反推（one-way）；the email string itself is NEVER returned or
    persisted — only this digest enters the ledger.
    """
    normalized = email.strip().lower()
    if not normalized or "@" not in normalized:
        raise ValueError("valid email required (fail-closed)")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _ledger_path(out_dir: str | Path) -> Path:
    return Path(out_dir) / LEDGER_FILENAME


def check_duplicate(email_hash_value: str, *, out_dir: str | Path) -> bool:
    """True iff this hash has been submitted before (重复 → 视为作废)."""
    p = _ledger_path(out_dir)
    if not p.exists():
        return False
    d = json.loads(p.read_text(encoding="utf-8"))
    return any(e["hash"] == email_hash_value for e in d.get("hashes", []))


def record_hash(email_hash_value: str, *, subject_id: str, out_dir: str | Path, at: datetime | None = None) -> Path:
    """Append one hash to the ledger (idempotent per hash); never the email原文."""
    p = _ledger_path(out_dir)
    d: dict[str, Any] = {"kind": "submitted_hash_ledger", "hashes": []}
    if p.exists():
        d = json.loads(p.read_text(encoding="utf-8"))
    if any(e["hash"] == email_hash_value for e in d["hashes"]):
        return p  # idempotent
    d["hashes"].append(
        {
            "hash": email_hash_value,
            "subject_id": subject_id,
            "recorded_at": (at or datetime.now()).isoformat(),
        }
    )
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    return p
