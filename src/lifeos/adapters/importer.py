"""Event import: adapter → committed pipeline (roadmap §4.6 optional item).

``import_events`` runs the SAME committed pipeline as native events (import
discipline: no bypass, no special sim path in the core). ``roundtrip_check``
verifies adapter equality: importing the same episodes twice (fresh stores)
produces identical L1/L2 sequences (deterministic commit + provenance) -
the round-trip validation suite required by the roadmap for adapter
introduction (登记 ADR，不阻塞 Gate).
"""

from __future__ import annotations

from typing import Any

from lifeos.adapters.engines import get_adapter
from lifeos.events.pipeline import EventPipeline
from lifeos.store.memory_store import InMemoryStore


def import_events(
    *,
    engine: str,
    episodes: list[dict[str, Any]],
    life_id: str,
    store: InMemoryStore,
    pipeline: EventPipeline | None = None,
) -> list[Any]:
    """Import engine episodes through the committed pipeline (sim source).

    Same pipeline, same locks, same provenance - sim events differ ONLY in
    ``RawEvent.source = sim`` (arch §5.11). Unknown engine fails closed.
    """
    adapter = get_adapter(engine)
    pipe = pipeline if pipeline is not None else EventPipeline(store)
    # the sim instance must exist (mandatory life_id predicate)
    if life_id not in store.instances:
        store.create_instance(
            life_id=life_id,
            personality_seed=f"sim:{engine}",
            born_at=store.instances.get(life_id) or __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            schema_version=pipe.schema_version,
        )
    results = []
    for ep in episodes:
        l0 = adapter.to_l0(ep, life_id=life_id)
        results.append(pipe.ingest(l0))
    return results


def roundtrip_check(
    *,
    engine: str,
    episodes: list[dict[str, Any]],
    life_id: str,
) -> dict[str, Any]:
    """Adapter round-trip validation suite (required for adapter introduction).

    Import the same episodes into two fresh stores; compare the L1/L2
    sequences field by field (event_id, output_json, provenance). Identical
    => adapter equality holds (deterministic commit; replay discipline).
    """
    s1, s2 = InMemoryStore(), InMemoryStore()
    r1 = import_events(engine=engine, episodes=episodes, life_id=life_id, store=s1)
    r2 = import_events(engine=engine, episodes=episodes, life_id=life_id, store=s2)

    mismatches: list[str] = []
    if len(r1) != len(r2):
        mismatches.append(f"result count differs: {len(r1)} vs {len(r2)}")
    for i, (a, b) in enumerate(zip(r1, r2)):
        if (a.raw_event is None) != (b.raw_event is None):
            mismatches.append(f"ep {i}: raw presence differs")
            continue
        if a.raw_event is None:
            continue  # both duplicates (identical idempotency)
        if a.raw_event.event_id != b.raw_event.event_id:
            mismatches.append(f"ep {i}: L0 event_id differs")
        if (a.interpreted is None) != (b.interpreted is None):
            mismatches.append(f"ep {i}: L1 presence differs")
        elif a.interpreted is not None and b.interpreted is not None:
            if a.interpreted.event_id != b.interpreted.event_id:
                mismatches.append(f"ep {i}: L1 event_id differs")
            if a.interpreted.output_json != b.interpreted.output_json:
                mismatches.append(f"ep {i}: L1 output_json differs")
            if a.interpreted.input_hash != b.interpreted.input_hash:
                mismatches.append(f"ep {i}: L1 input_hash differs")
        if (a.domain is None) != (b.domain is None):
            mismatches.append(f"ep {i}: L2 presence differs")
        elif a.domain is not None and b.domain is not None:
            if a.domain.event_id != b.domain.event_id:
                mismatches.append(f"ep {i}: L2 event_id differs")
            if a.domain.payload != b.domain.payload:
                mismatches.append(f"ep {i}: L2 payload differs")

    return {
        "engine": engine,
        "episodes": len(episodes),
        "equal": not mismatches,
        "mismatches": mismatches,
    }
