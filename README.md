# LifeOS

**A runtime for long-term digital characters and digital life — keeping an AI character recognizably "the same one" across interruptions, model swaps, and years of memory.**

LifeOS is a runtime platform for maintaining **long-term AI character continuity**. It is not a chat system and not an agent framework. Its job is to ensure that the same AI character is still recognized by its user as "the same one" after:

- conversations are interrupted and resumed,
- the user returns after a long absence,
- the underlying LLM is replaced,
- cloud and on-device models are switched,
- software is upgraded or hardware is replaced,
- memories accumulate over years.

The core managed object is a **Life Instance**:

```
Life Instance = Identity + Life State + Memory + Personality + Relationships + Development History + Behavior Policy + jhp
```

**Core promise**: the LLM can be swapped, the database migrated, the hardware body upgraded — yet the Life Instance must still be recognized as "the same one."

## Falsifiable Hypotheses

The project stands on three experimentally falsifiable hypotheses. Falsifying any of them stops or pivots the project:

- **H1 — Identity continuity is engineerable.** Continuity is determined primarily by externalized state (schema + memory + relationships + personality parameters), not by specific model weights.
- **H2 — Long-term memory is trustworthy and measurable.** Memory error and conflict rates can be measured and governed below thresholds as memory volume scales from 1k to 10k entries.
- **H3 — Users can perceive continuity.** In blind tests, users judge "is it the same one?" significantly above chance (falsification line: ≤ 55% agreement, n ≥ 50).

## Architecture: Deterministic Core + Probabilistic Leaves

Perception normalization, state decay, relationship updates, behavior selection, and safety approval are all **deterministic code**. The LLM only generates candidate intents, extracts memories, and renders language — it never writes authoritative state, relationships, or memory directly.

- **Three-level event model**: L0 raw events → L1 LLM-interpreted events (with full model provenance archived) → L2 committed domain events. Only L2 may modify authoritative long-term state; replays recompute L2 from archived L1 without re-calling the LLM. Haipeng
- **Core modules**: Life Kernel (internal states with lazy decay), Memory OS (working/episodic/semantic memory with deterministic temporal slot-conflict governance), Relationship Engine (bounded transparent rules), Behavior Planner (utility scoring with `reason` evidence chains), Policy Engine (10 red lines enforced before execution), Model Gateway (dual-provider hot swap, per-call cost accounting).
- **Single source of truth**: PostgreSQL 16 + pgvector.

## Technology Stack (all open source)

Python 3.13 / FastAPI / Pydantic / SQLAlchemy / Alembic, PostgreSQL 16 + pgvector, Valkey, vLLM / llama.cpp (local inference), Gradio / Streamlit (debug console), OpenTelemetry / Prometheus / Jaeger, DeepEval / Ragas / Promptfoo, pytest, Docker Compose. All core dependencies are Apache-2.0 / MIT / BSD / PostgreSQL License — no AGPL/SSPL/BSL in core.

## What's Genuinely Novel

- **I1** Model-agnostic long-term identity continuity (the engineering carrier of H1).
- **I2** A continuity evaluation metric system + gold set + measurement methodology — existing benchmarks (PersonaGym, InCharacter, CharacterEval) evaluate single-model persona fidelity, not continuity of a persistent instance across model migration and long time spans.
- **I3** The L0/L1/L2 event model with LLM-interpretation archiving for replay.
- **I4** Deterministic temporal governance of same-slot memory conflicts (bitemporal valid/transaction time).
- **I5** Life Instance Schema + Life Event Protocol.
- **I6** Policy/safety rule set (10 red lines as code) + attachment-safety policy.

Everything else — databases, RAG, utility AI, rule engines — is honest engineering integration, claimed as no more than that.

## Evaluation

Eight quantitative metrics with hard thresholds (core-fact recall ≥ 90% after model swap, naming/relationship consistency ≥ 95%, personality drift ≤ 0.15, memory error ≤ 5%, cross-model intent agreement ≥ 80%, blind-test agreement ≥ 75% **and** ≥ best baseline + 10pp), six one-vote-veto hard gates (e.g., L2 replay consistency must be 100%), three validation scenarios (long-term reunion / differentiated reactions per person / model swap where it's still itself), four baselines (raw history / summary / standard vector RAG / LifeOS), and a pre-registered statistical protocol (n ≥ 50, bootstrap 95% CI).

## Delivery Plan

Four gated phases, each independently stoppable, with staged authorization rather than a single approval:

1. **Phase 0** (3 weeks, 1–2 person-months): schemas, event protocol, replayable skeleton.
2. **Phase 1** (6–8 weeks, cumulative 6–10 person-months): minimal cross-model continuity validation.
3. **Phase 2** (8–10 weeks, cumulative 12–20 person-months): three demos + baseline comparison + time-accelerated continuity simulator.
4. **Phase 3** (12–16 weeks, cumulative 24–40 person-months): real-user validation with full data-governance compliance (informed consent, privacy tiers, verifiable deletion, no minors).

Only after the decision gate — proving "it's still it" — does expansion begin.

## Repository Layout

- `doc/` — current documents (v0.9.1, Chinese):
  - Product specification: [LifeOS_产品规格说明书_v0.9.1](/doc/LifeOS_产品规格说明书_v0.9.1.md)
  - Architecture design: [LifeOS_架构设计_v0.9.1](/doc/LifeOS_架构设计_v0.9.1.md)
  - R&D roadmap: [LifeOS_研发路线图_v0.9.1](/doc/LifeOS_研发路线图_v0.9.1.md)
  - Innovation literature baseline: [adadmic_innovation_v0.9.1](/doc/adadmic_innovation_v0.9.1.md) (literature survey date 2026-08-05); earlier versions (v0.5–v0.9) retained for lineage.
- `phases/` — per-phase design docs, ADRs and acceptance reports:
  - `phases/phase-0/` — Phase 0 (contract & replayable skeleton): detailed design, execution plan with acceptance cases AC-01…AC-10, human-authoring spec for the 50 core facts / 30 behavior scenarios, Gate 0 report.
- `src/lifeos/` — Phase 0 code skeleton (15-entity schema, L0/L1/L2 event pipeline, `deterministic_commit`, minimal Policy Engine, replay forensics, gold set validator/registry, verification CLI).
- `tests/` `scripts/` `data/goldset/` `alembic/` `docker-compose.yml` — the Phase 0 engineering skeleton (see `phases/phase-0/README.md` for commands).
- `paper/` — downloaded papers referenced by the literature baseline.
- `draft/` — earlier specification drafts (Draft 0.2, 0.3, v0.5).

## Licensing Strategy

- Runtime kernel & schemas: Apache-2.0
- SDK & toolchain: Apache-2.0
- Documentation & specs: CC BY 4.0
- Evaluation benchmarks & gold sets: Apache-2.0 (data under CC BY 4.0)

Core capabilities are never relicensed closed; there is no open-core bait. Commercial offerings (carrier products, hosting, enterprise support, proprietary datasets) are separate post-gate projects.
