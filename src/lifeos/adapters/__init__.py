"""Third-party engine adapters (roadmap §4.6 optional item, non-blocking).

The adapter surface IS the L0 event protocol (arch §5.11): any external
simulator able to emit L0-schema events drives LifeOS through
``import_events``. Sample adapters for the academic near-neighbors:

- ``ConcordiaAdapter``: Google DeepMind agent-society episodes
- ``AgentSocietyAdapter``: open-source LLM society simulation traces
- ``GenerativeAgentsAdapter``: Stanford memory-stream episodes (arXiv 2304.03442)

Each adapter maps engine-native episode dicts → L0 events (``source=sim``,
provenance in payload); ``import_events`` runs the committed pipeline and
``roundtrip_check`` verifies adapter equality (same episodes → same L1/L2
sequence on re-run - replay discipline).
"""
