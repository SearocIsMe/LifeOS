"""continuity-sim deterministic simulator (roadmap S3, architecture §5.11).

Benchmarks AgentSociety (social simulation) / Concordia (game-engine sim).
Differentiating constraints: deterministic event skeleton + LLM dialogue fill +
injection operator, fully seeded - the same seed MUST yield the same event
sequence.

Public surface:
- ``generate_skeleton``  - deterministic event sequence (append-only JSONL rows)
- ``fill_dialogue``      - temperature=0 / mock fill with Invocation provenance
- ``build_bundle``       - memory records derived from filled events
- ``write_bundle``       - bundle file for the inject operator
- ``inject_bundle``      - inject synthetic memories into a store (injected = truth)
- ``ramp``               - 1k->10k memory ramp with weekly continuity reports
"""

from __future__ import annotations

from lifeos.sim.simulator import (
    SIM_SCHEMA_VERSION,
    SIM_DEFAULT_SEED,
    build_bundle,
    generate_skeleton,
    inject_bundle,
    ramp,
    write_bundle,
)

__all__ = [
    "SIM_SCHEMA_VERSION",
    "SIM_DEFAULT_SEED",
    "generate_skeleton",
    "build_bundle",
    "write_bundle",
    "inject_bundle",
    "ramp",
]
