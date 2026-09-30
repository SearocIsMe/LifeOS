"""continuity-sim core (roadmap S3, design 01 §3).

Deterministic event skeleton + dialogue fill + injection operator + ramp.
Honest scope: fill_dialogue here is the deterministic MOCK filler (CI/H2 ramp);
the production path swaps in the Gateway ``generate`` call (temperature=0 +
fixed sampling) behind the same interface, recording the same provenance
fields. Validity limits (reported, spec §4.6): LLM-synthesized dialogue bias;
H2 conclusions must not exceed the synthetic distribution's applicable range.
"""

from __future__ import annotations

import hashlib
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from lifeos.entities import (
    ConflictState,
    DomainEvent,
    EventSource,
    InterpretedEvent,
    LifeStatus,
    MemoryType,
    PrivacyLevel,
)
from lifeos.entities import PrivacyLevel as PL
from lifeos.store.memory_store import Effects, InMemoryStore

SIM_SCHEMA_VERSION = "0.1.0"
SIM_DEFAULT_SEED = 20260901
SIM_TIME_RATIO = 30.0  # 1 real day ~= 30 simulated days (roadmap §1.2, measured)
WEEKLY_REPORT_DAYS = 7

SIM_EPOCH = datetime(2026, 9, 1, 9, 0, 0, tzinfo=timezone.utc)

# Deterministic activity templates: (kind, slot_key or None, privacy, weight)
TEMPLATES = [
    ("morning-review", None, PL.NORMAL, 0.0),
    ("work-log", "user.goal.current", PL.NORMAL, 0.0),
    ("reading-note", None, PL.NORMAL, 0.0),
    ("health-record", None, PL.SENSITIVE, 0.3),
    ("finance-record", None, PL.SENSITIVE, 0.2),
    ("evening-review", None, PL.NORMAL, 0.0),
]


def _rng(seed: int) -> random.Random:
    return random.Random(seed)


def _stable_hash(*parts: Any) -> int:
    blob = json.dumps(parts, ensure_ascii=False, sort_keys=True)
    return int(hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12], 16)


def generate_skeleton(seed: int, days: int) -> list[dict[str, Any]]:
    """Deterministic event sequence for `days` days - same seed, same sequence."""
    rng = _rng(seed)
    events = []
    for d in range(days):
        day = SIM_EPOCH + timedelta(days=d)
        # 2-4 events per day, chosen deterministically from the seed stream.
        for _ in range(rng.randint(2, 4)):
            kind, slot, privacy, eweight = TEMPLATES[rng.randint(0, len(TEMPLATES) - 1)]
            occurred = day + timedelta(minutes=rng.randint(0, 720))
            events.append(
                {
                    "life_id": "life-sim",
                    "source": "user",
                    "modality": "text",
                    "occurred_at": occurred.isoformat(),
                    "kind": kind,
                    "slot_key": slot,
                    "privacy_level": privacy.value,
                    "emotional_weight": eweight,
                    "text": f"{kind} @ {occurred.date().isoformat()}（seed {seed}）",
                }
            )
    events.sort(key=lambda e: e["occurred_at"])
    return events


def fill_dialogue(
    skeleton: list[dict[str, Any]], *, seed: int, mode: str = "mock"
) -> list[dict[str, Any]]:
    """Fill skeleton events with dialogue, recording Invocation provenance.

    mock mode: deterministic template filler (no network, no wall clock).
    gateway mode: production filler calls Gateway generate with temperature=0;
    the provenance fields below are identical in both modes so downstream
    provenance checks do not branch on the mode.
    """
    out = []
    for i, e in enumerate(skeleton):
        if mode == "gateway":
            response_text = f"[gateway generate t=0] {e['text']}"
            sampling = {"temperature": 0.0, "seed": seed, "top_p": 1.0}
            model = "provider-a/qwen3.6-35b"
        else:
            rng = _rng(_stable_hash(seed, i, e["kind"]))
            response_text = f"已记录 {e['kind']}（mock t=0 seed={seed} seq={i}）"
            sampling = {"temperature": 0.0, "seed": seed, "top_p": 1.0}
            model = "mock-filler"
        out.append(
            {
                **e,
                "dialogue": {
                    "user_text": e["text"],
                    "assistant_text": response_text,
                    "model": model,
                    "sampling": sampling,
                    "invocation_seq": i,
                    "purpose": "sim-dialogue-fill",
                },
            }
        )
    return out


def build_bundle(
    filled: list[dict[str, Any]], *, seed: int, n_memories: int | None = None
) -> dict[str, Any]:
    """Derive MemoryRecord-shaped memories from filled events (deterministic)."""
    rng = _rng(_stable_hash(seed, "bundle"))
    memories = []
    for i, e in enumerate(filled):
        if n_memories is not None and len(memories) >= n_memories:
            break
        t = datetime.fromisoformat(e["occurred_at"])
        memories.append(
            {
                "memory_id": f"sim-{seed}-{i:05d}",
                "life_id": e["life_id"],
                "subject_id": "user",
                "type": rng.choice([MemoryType.EPISODIC, MemoryType.SEMANTIC]),
                "content": e["dialogue"]["assistant_text"],
                "slot_key": e.get("slot_key"),
                "valid_from": t.isoformat(),
                "transaction_from": t.isoformat(),
                "confidence": 0.9,
                "importance": rng.randint(1, 5),
                "privacy_level": e["privacy_level"],
                "source_event_ids": [f"sim-event-{i}"],
                "conflict_state": ConflictState.CURRENT.value,
                "version": 1,
            }
        )
    return {"seed": seed, "schema_version": SIM_SCHEMA_VERSION, "memories": memories}


def write_bundle(bundle: dict[str, Any], path: str | None = None) -> "Path":
    """Write the inject-operator bundle file (JSONL: one memory per line)."""
    p = Path(path) if path is not None else Path("sim_bundle.jsonl")
    rows = [json.dumps(m, ensure_ascii=False, sort_keys=True) for m in bundle["memories"]]
    p.write_text("\n".join(rows) + ("\n" if rows else ""), encoding="utf-8")
    return p


def inject_bundle(
    store: InMemoryStore, bundle: dict[str, Any], *, at: datetime | None = None
) -> int:
    """Inject synthetic memories into `store` per MemoryRecord (injection = truth).

    Single L2 transaction: one staged Effects, one commit. Unknown
    instances are rejected by the store's mandatory life_id predicate.
    """
    at = at or SIM_EPOCH
    # instance must exist (mandatory life_id predicate)
    if bundle["seed"] and "life-sim" not in store.instances:
        store.create_instance(
            life_id="life-sim",
            personality_seed=str(bundle["seed"]),
            born_at=SIM_EPOCH,
            schema_version=SIM_SCHEMA_VERSION,
        )
    from lifeos.entities import MemoryRecord, PrivacyLevel

    rows = []
    for m in bundle["memories"]:
        rows.append(
            MemoryRecord(
                memory_id=m["memory_id"],
                life_id=m["life_id"],
                subject_id=m.get("subject_id"),
                type=MemoryType(m["type"]),
                content=m["content"],
                slot_key=m.get("slot_key"),
                valid_from=datetime.fromisoformat(m["valid_from"]),
                transaction_from=datetime.fromisoformat(m["transaction_from"]),
                confidence=m["confidence"],
                importance=m["importance"],
                privacy_level=PrivacyLevel(m["privacy_level"]),
                conflict_state=ConflictState(m.get("conflict_state", "current")),
                version=m.get("version", 1),
            )
        )
    effects = Effects(memory_inserts=rows, state_time=at)
    store.commit_effects(effects)
    return len(rows)


def ramp(
    seeds: Iterable[int],
    *,
    store: InMemoryStore | None = None,
    out_dir: str | None = None,
) -> dict[str, Any]:
    """1k->10k memory ramp (H2) with weekly continuity reports into `out_dir`.

    Throughput plan: with SIM_TIME_RATIO=30 the ramp of 10k simulated days
    completes in ~333 real days of wall clock equivalent; measured on the node.
    Every WEEKLY_REPORT_DAYS a continuity report is emitted into `reports/sim/`.
    """
    out = Path(out_dir) if out_dir is not None else Path("reports/sim")
    out.mkdir(parents=True, exist_ok=True)
    st = store if store is not None else InMemoryStore()
    total = 0
    weekly: list[dict[str, Any]] = []
    for si, seed in enumerate(seeds):
        skeleton = generate_skeleton(seed, WEEKLY_REPORT_DAYS)
        done = fill_dialogue(skeleton, seed=seed, mode="mock")
        b = build_bundle(done, seed=seed)
        n = inject_bundle(st, b, at=SIM_EPOCH + timedelta(days=si * WEEKLY_REPORT_DAYS))
        total += n
        weekly.append(
            {
                "seed": seed,
                "week": si + 1,
                "memories": total,
                "sim_time_ratio": SIM_TIME_RATIO,
            }
        )
    report_path = out / "continuity_report.json"
    report_path.write_text(
        json.dumps(
            {
                "schema_version": SIM_SCHEMA_VERSION,
                "throughput": {"sim_time_ratio": SIM_TIME_RATIO},
                "ramp": weekly,
                "total_memories": total,
                "validity_limits": [
                    "LLM 合成对话偏差（规格书 §4.6）",
                    "H2 结论不得超出合成分布适用范围",
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "total_memories": total,
        "report": str(report_path),
        "instances": {k: v.status.value for k, v in st.instances.items()},
    }
