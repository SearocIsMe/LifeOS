"""Engine-native episode → L0 event mapping for the academic near-neighbors.

Adapters map each engine's episode/trace dicts into L0-schema events:

- ``source = sim`` (arch §5.11: sim events distinguishable in ``RawEvent.source``);
- engine-native text → ``payload.text`` + ``payload.structured`` (the same
  shape the interpreter consumes; engine-specific metadata goes under
  ``payload.sim_meta`` - the committed contract's ``extra="forbid"`` only
  guards ``structured``, so provenance lives OUTSIDE it);
- engine timestamp → ``occurred_at`` (ISO 8601); the system never mints
  semantic time - callers inject it;
- mapping is a PURE function: same episode → same L0 dict (replay discipline).

Engine shapes covered (documented sample adapters, not full integrations):
- Concordia: ``{episode_type, agent_name, utterance, time}``
- AgentSociety: ``{event_type, actor, content, timestamp}``
- GenerativeAgents: ``{step, subject, statement, created}``
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Protocol

from lifeos.events.protocol import canonical_json

ADAPTER_SOURCE = "sim"


def _parse_time(value: Any) -> datetime:
    """Normalize engine timestamps to tz-aware datetimes (fail-closed on garbage).

    The committed pipeline ingests datetimes (not ISO strings) - adapters
    emit datetime directly so the L0 dict is pipeline-ready.
    """
    if isinstance(value, datetime):
        dt = value
    else:
        s = str(value).strip()
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


class EngineAdapter(Protocol):
    """One adapter per engine: episodes → L0 dicts (pure)."""

    engine: str

    def to_l0(self, episode: dict[str, Any], *, life_id: str) -> dict[str, Any]: ...


class ConcordiaAdapter:
    """Concordia (DeepMind): act/component episodes → L0."""

    engine = "concordia"

    def to_l0(self, episode: dict[str, Any], *, life_id: str) -> dict[str, Any]:
        text = episode.get("utterance") or episode.get("statement") or ""
        return {
            "life_id": life_id,
            "source": ADAPTER_SOURCE,
            "modality": "text",
            "payload": {
                "text": str(text),
                "structured": {},
                "sim_meta": {"engine": self.engine, "episode_type": episode.get("episode_type", ""), "agent_name": episode.get("agent_name", "")},
            },
            "occurred_at": _parse_time(episode.get("time") or episode.get("timestamp")),
        }


class AgentSocietyAdapter:
    """AgentSociety: event traces → L0."""

    engine = "agentsociety"

    def to_l0(self, episode: dict[str, Any], *, life_id: str) -> dict[str, Any]:
        text = episode.get("content") or episode.get("utterance") or ""
        return {
            "life_id": life_id,
            "source": ADAPTER_SOURCE,
            "modality": "text",
            "payload": {
                "text": str(text),
                "structured": {},
                "sim_meta": {"engine": self.engine, "event_type": episode.get("event_type", ""), "actor": episode.get("actor", "")},
            },
            "occurred_at": _parse_time(episode.get("timestamp") or episode.get("time")),
        }


class GenerativeAgentsAdapter:
    """Generative Agents (Stanford): memory-stream rows → L0."""

    engine = "generative_agents"

    def to_l0(self, episode: dict[str, Any], *, life_id: str) -> dict[str, Any]:
        text = episode.get("statement") or episode.get("utterance") or ""
        return {
            "life_id": life_id,
            "source": ADAPTER_SOURCE,
            "modality": "text",
            "payload": {
                "text": str(text),
                "structured": {},
                "sim_meta": {"engine": self.engine, "step": episode.get("step", ""), "subject": episode.get("subject", "")},
            },
            "occurred_at": _parse_time(episode.get("created") or episode.get("timestamp")),
        }


ADAPTERS: dict[str, EngineAdapter] = {
    "concordia": ConcordiaAdapter(),
    "agentsociety": AgentSocietyAdapter(),
    "generative_agents": GenerativeAgentsAdapter(),
}


def get_adapter(engine: str) -> EngineAdapter:
    """Fail-closed: unknown engines raise (no silent passthrough)."""
    adapter = ADAPTERS.get(engine)
    if adapter is None:
        raise ValueError(f"unknown engine adapter: {engine!r} (known: {sorted(ADAPTERS)})")
    return adapter


def episode_fingerprint(engine: str, episode: dict[str, Any]) -> str:
    """Deterministic episode identity (canonical_json, replay-safe)."""
    return canonical_json({"engine": engine, "episode": episode})
