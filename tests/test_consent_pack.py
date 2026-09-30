"""Phase 3 S2 acceptance: consent template pack (jurisdiction x locale).

Case map (design doc 02 §2 S2):
- template jurisdictions complete -> CN/SG/HK/MO x zh, document_version versioned
- two-tier deletion disclosure    -> data_deletion clause states both tiers + 30d window
- signatures empty (discipline)   -> no pre-filled signatures (README discipline)
- clause structure consistent     -> all four packs share the same clause ids
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
PACK_DIR = REPO / "data" / "consent"

REQUIRED_JURISDICTIONS = {"CN", "SG", "HK", "MO"}
REQUIRED_CLAUSES = {
    "purpose",
    "procedures",
    "risks",
    "privacy_levels",
    "data_storage",
    "data_deletion",
    "rights",
    "contact",
}


def _packs() -> dict[str, dict]:
    out = {}
    for p in sorted(PACK_DIR.glob("consent_*_zh.yaml")):
        doc = yaml.safe_load(p.read_text(encoding="utf-8"))
        juris = doc["template"]["jurisdiction"]
        out[juris] = doc
    return out


def test_template_jurisdictions_complete():
    packs = _packs()
    assert set(packs) == REQUIRED_JURISDICTIONS
    for juris, doc in packs.items():
        t = doc["template"]
        assert t["language"] == "zh"
        assert t["document_version"] == "1.0.0"
        # clause ids consistent across all four packs
        ids = {c["id"] for c in doc["clauses"]}
        assert ids == REQUIRED_CLAUSES, f"{juris} clause mismatch: {ids ^ REQUIRED_CLAUSES}"


def test_two_tier_deletion_disclosure():
    packs = _packs()
    for juris, doc in packs.items():
        clause = next(c for c in doc["clauses"] if c["id"] == "data_deletion")
        text = clause["title"] + clause["text"]
        # both tiers named (spec §9.3)
        assert "治理性删除" in text, f"{juris}: governance tier missing"
        assert "用户擦除" in text, f"{juris}: user-erase tier missing"
        assert "全介质" in text, f"{juris}: all-media wording missing"
        assert "不可恢复" in text, f"{juris}: ir-recoverable wording missing"
        # 30-day rolling backup window disclosure (spec §9.3, ADR-0007)
        assert "30 天滚动备份窗口" in text, f"{juris}: backup window disclosure missing"


def test_signatures_empty_discipline():
    packs = _packs()
    for juris, doc in packs.items():
        sig = doc["signatures"]
        assert sig["participant"]["required"] is True
        assert sig["researcher"]["required"] is True
        # no pre-filled names/dates (signed during study period only)
        assert sig["participant"]["name"] == "", f"{juris}: participant name pre-filled"
        assert sig["participant"]["signed_at"] == "", f"{juris}: participant date pre-filled"
        assert sig["researcher"]["name"] == "", f"{juris}: researcher name pre-filled"
        assert sig["researcher"]["signed_at"] == "", f"{juris}: researcher date pre-filled"


def test_jurisdiction_notes_distinct():
    packs = _packs()
    notes = {j: d["jurisdiction_note"] for j, d in packs.items()}
    # each jurisdiction cites its own law (spec §9.4 matrix)
    assert "个人信息保护法" in notes["CN"]
    assert "PDPA" in notes["SG"]
    assert "PDPO" in notes["HK"] or "私隐" in notes["HK"]
    assert "8/2005" in notes["MO"]
    assert len(set(notes.values())) == 4  # four distinct notes
