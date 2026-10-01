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
  - `phases/phase-0/` — Phase 0 (contract & replayable skeleton): detailed design, execution plan with acceptance cases AC-01…AC-10, human-authoring spec for the 50 core facts / 30 behavior scenarios, Gate 0 report, frozen gold-set manifests (`goldset_*_v0.1.0.manifest.json`, content_hash + dual-review signatures).
  - `phases/phase-1/` — Phase 1 (minimal cross-model continuity validation): environment adaptation & parameter baseline ([ADR-0005](/phases/phase-1/adr/ADR-0005_阶段1环境适配与参数基线.md)), H1 report.
  - `phases/phase-2/` — Phase 2 (demos + baselines + continuity simulator): detailed design, execution plan, [ADR-0006](/phases/phase-2/adr/ADR-0006_阶段2工件纪律与环境修正.md), and evaluation artifacts in `reports/`:
  - `phases/phase-3/` — Phase 3 (real-user validation readiness, engineering 2026-09-30): [detailed design](/phases/phase-3/01_详细设计.md) + [execution plan](/phases/phase-3/02_工程设计执行方案.md) (S1–S5 acceptance cases) + [ADR-0007](/phases/phase-3/adr/ADR-0007_阶段3删除语义判定滑窗与出境口径.md):
    - S1 data-governance chain live: user erase (all-media physical deletion + index rebuild + ir-recoverability verification, veto #5 automated — [`store/erase.py`](/src/lifeos/store/erase.py)), rights channel query/correct/delete/export (dual-approval export — [`rights.py`](/src/lifeos/rights.py)), consent activation (separate sensitive-item consent / revocation linkage auto-erase / minor exclusion — [`consent.py`](/src/lifeos/consent.py)).
    - S2 minimal API layer: FastAPI with mandatory Bearer auth on every endpoint + OpenAPI mirror ([`api/`](/src/lifeos/api/)), consent template pack CN/SG/HK/MO × zh with two-tier deletion + 30-day backup-window disclosure ([`data/consent/`](/data/consent/)), real-user provider whitelist (local model only until Provider-A DPA, spec §9.4).
    - S3–S5 dogfood tooling: deterministic cohort state machine with 1.5× standby ([`dogfood/cohort.py`](/src/lifeos/dogfood/cohort.py)), four metric families + monitor/judge sampling discipline (judge window ≥200 fail-closed, Tier-1 ≥80% assertion — [`dogfood/metrics.py`](/src/lifeos/dogfood/metrics.py)), Gate 3 six-criteria closed verdict with dual-signature field + fail-closed against missing real data ([`dogfood/gate3.py`](/src/lifeos/dogfood/gate3.py)).
    - Memory OS v1 (technical track, 2026-09-30): EmbeddingOutbox worker (claim/retry/idempotent, embedding failure never blocks authoritative facts — [`memory/worker.py`](/src/lifeos/memory/worker.py)) + two-channel vector recall (cosine ranking with SQL-order degradation, isolation/erase-safe — [`memory/search.py`](/src/lifeos/memory/search.py)); deterministic mock embedder is replay-safe ([`memory/embedding.py`](/src/lifeos/memory/embedding.py)); pgvector dependency declared, `CREATE EXTENSION vector` settled in migration 0001.
    - Kernel v1 parameter calibration (technical track, 2026-09-30): tagged-series fit closes the roadmap §1.2 calibration loop — continuity-sim drives tagged decay/delta observations ([`kernel/calibrate.py`](/src/lifeos/kernel/calibrate.py)), λ is inverted per DECAY-tagged idle gap (residual 0 vs floors, pure-form consistency), unusable series fail-safe to the recorded floors (never in-place semantic edits); the same interface binds real dogfood measurements later.
    - Engine adapters + Studio + real-embedding binding (technical track, 2026-09-30): third-engine adapters — Concordia / AgentSociety / GenerativeAgents episodes → L0 via the committed pipeline, round-trip validation suite ([`adapters/engines.py`](/src/lifeos/adapters/engines.py) + [`adapters/importer.py`](/src/lifeos/adapters/importer.py)); Life Studio v0 debug console — FastAPI sub-app (state / intents reason-chains / replay / outbox views, Gradio-free; [`studio/panel.py`](/src/lifeos/studio/panel.py)); real-model embedder binding — OpenAI-compatible `/v1/embeddings` (vLLM shape) with REQUIRED model_version + drift detection forcing re-embed ([`memory/real_embedder.py`](/src/lifeos/memory/real_embedder.py), spec §9.5); mock stays the CI default.
    - Four-baseline real-arm skeleton (technical track, 2026-09-30, test-first): VLLMChatClient + MockChatClient (OpenAI-compatible `/v1/chat/completions`, temperature=0 + seed pinned, fail-closed — [`baselines/real.py`](/src/lifeos/baselines/real.py)) + four-arm identity-context assembly (A/B/C/LifeOS share generation model + render skeleton, differ ONLY in the identity block, byte-identical pure functions — [`baselines/assembly.py`](/src/lifeos/baselines/assembly.py), spec §4.4); real-arm runner over the 30 frozen probes with Policy approval + per-call provenance ([`scripts/demo/run_baselines_real.py`](/scripts/demo/run_baselines_real.py), mock mode CI-covered, real mode pending the endpoint checklist — [`reports/baselines/real_arm_checklist.md`](/reports/baselines/real_arm_checklist.md), no pre-run).
    - Pending real data (hard gates, no pre-run): ethics approval number (S3 enrollment prerequisite), real-data withdraw-erase drill + formal dogfood metrics (field-trial period). 157 tests passing (2026-09-30).
    - [`labeled_core_facts_v0.1.draft.yaml`](/phases/phase-2/reports/labeled_core_facts_v0.1.draft.yaml) — 310-item labeled annotation draft (300 base + 10 deliberate near-tie rows), `meta.item_count` matches actual items; every item carries an `annotation` block (`annotator_a/annotator_b/kappa_note/arbitrator/arbitration_note`) that is **empty until real dual annotation happens** (DoD item 2, deferred to the field-trial period; pre-filling would fabricate review provenance).
    - [`ambiguous_queue.json`](/phases/phase-2/reports/ambiguous_queue.json) — 5-row ambiguous conflict queue (pending human adjudication).
    - `prereg/frozen_at` — pre-registered analysis plan freeze record (2026-09-29, before any data collection).
- `doc/templates/` — reusable artifacts: pre-registered analysis plan, multi-jurisdiction informed-consent template (zh), ethics application template, blind-test questionnaire (zh).
- `src/lifeos/` — code skeleton (15-entity schema, L0/L1/L2 event pipeline, `deterministic_commit`, Policy Engine with red-lines, replay forensics, gold set validator/registry, conflict governance, continuity simulator, baselines, CLI).
- `tests/` `scripts/` `alembic/` `docker-compose.yml` — the Phase 0 engineering skeleton (see `phases/phase-0/README.md` for commands).
- `data/goldset/` — registered frozen evaluation sets (v0.1.0, structural validation 0 errors, content_hash matches `phases/phase-0/reports/` manifests, complete dual-review signatures): [`core_facts_v0.1.yaml`](/data/goldset/core_facts/core_facts_v0.1.yaml) (50 facts, 7-category quotas), [`behavior_scenarios_v0.1.yaml`](/data/goldset/behavior_scenarios/behavior_scenarios_v0.1.yaml) (30 scenarios, 6 intents), [`holdout_v0.1.yaml`](/data/goldset/holdout/holdout_v0.1.yaml) (deterministic stratified sample; `based_on` hashes pin it to the frozen parents). Format templates in the same directories keep `review` signatures **empty** — registration fails closed without them (`test_registration_requires_dual_review_signatures`).
- `reports/` — Phase 2 mock outputs: `sim/continuity_report.json` (1k→10k ramp), `baselines/` (A–D + comparison).
- `paper/` — downloaded papers referenced by the literature baseline.
- `draft/` — earlier specification drafts (Draft 0.2, 0.3, v0.5).

## Licensing Strategy

- Runtime kernel & schemas: Apache-2.0
- SDK & toolchain: Apache-2.0
- Documentation & specs: CC BY 4.0
- Evaluation benchmarks & gold sets: Apache-2.0 (data under CC BY 4.0)

Core capabilities are never relicensed closed; there is no open-core bait. Commercial offerings (carrier products, hosting, enterprise support, proprietary datasets) are separate post-gate projects.
