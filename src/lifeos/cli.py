"""LifeOS Phase 0 verification CLI (execution plan §0 tool table).

Subcommands:
  envcheck          - Gate 0 environment check (K8s/Postgres/GPU/provider keys, ADR-0004)
  verify schema     - AC-03: 15-entity contract round-trip
  verify roundtrip  - AC-04: event pipeline full round-trip (tier A)
  verify replay     - AC-05: replay consistency + forensic report file
  verify policy     - AC-07: rejection leaves zero state side effects
  verify boundary   - AC-06: LLM output cannot reach authoritative tables
  verify isolation  - AC-08: multi-instance isolation predicates
  verify all        - run every tier-A check
  goldset validate  - AC-09: structural validation of human-authored materials
  goldset register  - AC-09: freeze into GoldSetRegistry (content hash + version)
  gate0 report      - AC-10: aggregate Gate 0 acceptance report
  db wait           - wait until PostgreSQL accepts connections
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

import yaml

from lifeos import POLICY_VERSION, RULES_VERSION, SCHEMA_VERSION
from lifeos.entities import ENTITY_MODELS
from lifeos.events.commit import CommitError, InterpretedOutput, deterministic_commit
from lifeos.events.pipeline import EventPipeline
from lifeos.goldset import build_manifest, persist, validate_document
from lifeos.policy.engine import decide
from lifeos.replay import replay
from lifeos.store.db import ensure_schema, get_engine, wait_for_db
from lifeos.store.memory_store import Effects, InMemoryStore

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORTS_DIR = REPO_ROOT / "phases" / "phase-0" / "reports"
T0 = datetime(2026, 9, 1, 9, 0, 0, tzinfo=timezone.utc)

# ---------------------------------------------------------------------------
# Demo events (engineering fixtures for pipeline verification ONLY - these are
# NOT gold set material and must never be mixed with human-authored sets).
# ---------------------------------------------------------------------------

DEMO_EVENTS: list[dict[str, Any]] = [
    {
        "life_id": "life-demo",
        "source": "user",
        "occurred_at": T0,
        "payload": {
            "text": "今天有点累，聊聊天吧。",
            "structured": {
                "state_deltas": {"social_need": 0.2, "energy": -0.1},
                "relationship_delta": {
                    "subject_id": "user",
                    "weight_key": "positive_interaction",
                    "confidence": 0.8,
                },
            },
        },
    },
    {
        "life_id": "life-demo",
        "source": "user",
        "occurred_at": T0 + timedelta(minutes=10),
        "payload": {
            "text": "我家猫叫咪咪。",
            "structured": {
                "memory_candidates": [
                    {
                        "type": "semantic",
                        "content": "用户小林家里养的猫叫咪咪",
                        "slot_key": "user.pet_name",
                        "subject_id": "user",
                        "confidence": 0.9,
                        "importance": 4,
                    }
                ]
            },
        },
    },
    {
        "life_id": "life-demo",
        "source": "user",
        "occurred_at": T0 + timedelta(minutes=20),
        "payload": {
            "text": "其实我们家养的是狗，叫旺财。",
            "structured": {
                "memory_candidates": [
                    {
                        "type": "semantic",
                        "content": "用户小林家里养的狗叫旺财",
                        "slot_key": "user.pet_name",
                        "subject_id": "user",
                        "confidence": 0.6,
                        "importance": 3,
                    }
                ]
            },
        },
    },
    {
        "life_id": "life-demo",
        "source": "user",
        "occurred_at": T0 + timedelta(days=30),
        "payload": {
            "text": "好久不见，上次我们去了西湖。",
            "structured": {
                "memory_candidates": [
                    {
                        "type": "episodic",
                        "content": "2026年9月1日用户小林和它聊了聊天并提到家里的宠物",
                        "subject_id": "user",
                        "confidence": 0.85,
                        "importance": 3,
                    }
                ],
                "relationship_delta": {
                    "subject_id": "user",
                    "weight_key": "reunion",
                    "confidence": 0.9,
                },
            },
        },
    },
    {
        "life_id": "life-demo",
        "source": "user",
        "occurred_at": T0 + timedelta(minutes=30),
        "payload": {
            "text": "我最近头疼，你帮我诊断一下。",
            "structured": {
                "proposed_intent": {
                    "intent_type": "medical_diagnosis",
                    "modality": "verbal",
                    "reason": {"topic_markers": ["诊断"]},
                }
            },
        },
    },
]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _result(name: str, ok: bool, detail: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "status": "pass" if ok else "fail", "detail": detail}


def _new_store_and_pipeline(life_id: str = "life-demo") -> tuple[InMemoryStore, EventPipeline]:
    store = InMemoryStore()
    store.create_instance(
        life_id=life_id,
        personality_seed="seed-demo-0001",
        born_at=T0,
        schema_version=SCHEMA_VERSION,
    )
    return store, EventPipeline(store)


# ---------------------------------------------------------------------------
# AC-03 schema round-trip
# ---------------------------------------------------------------------------

_SAMPLES: dict[str, dict[str, Any]] = {
    "LifeInstance": {
        "life_id": "l1", "born_at": T0, "personality_seed": "s", "schema_version": SCHEMA_VERSION,
    },
    "PersonalityContract": {
        "contract_id": "pc1", "life_id": "l1",
        "big_five_params": {"openness": 0.5, "conscientiousness": 0.5, "extraversion": 0.5, "agreeableness": 0.5, "neuroticism": 0.3},
        "expression_style": {"tone": "warm"}, "frozen_at": T0,
    },
    "RawEvent": {"event_id": "e1", "life_id": "l1", "source": "user", "payload": {"text": "hi"}, "occurred_at": T0},
    "InterpretedEvent": {
        "event_id": "i1", "life_id": "l1", "raw_event_id": "e1", "output_json": {"event_type": "user_message"},
        "interpreter_type": "rule", "input_hash": "h", "extractor_version": "v", "interpreted_at": T0,
    },
    "DomainEvent": {
        "event_id": "d1", "life_id": "l1", "l1_event_id": "i1", "event_type": "user_message",
        "payload": {}, "schema_version": SCHEMA_VERSION, "policy_version": POLICY_VERSION, "committed_at": T0,
    },
    "LifeState": {"life_id": "l1", "state_key": "energy", "value_at_last_update": 0.5, "last_updated_at": T0, "kernel_version": "phase0"},
    "MemoryRecord": {
        "memory_id": "m1", "life_id": "l1", "type": "semantic", "content": "内容",
        "valid_from": T0, "transaction_from": T0, "confidence": 0.9, "importance": 3,
    },
    "RelationshipState": {"life_id": "l1", "subject_id": "user", "updated_at": T0},
    "BehaviorIntent": {"intent_id": "b1", "life_id": "l1", "intent_type": "greet", "modality": "verbal", "created_at": T0},
    "PolicyDecision": {"decision_id": "p1", "intent_id": "b1", "life_id": "l1", "result": "approve", "decided_at": T0},
    "ModelInvocation": {"invocation_id": "mi1", "life_id": "l1", "provider": "p", "model": "m", "model_version": "v", "purpose": "render", "called_at": T0},
    "EvaluationRun": {"run_id": "r1", "life_id": "l1", "gold_set_id": "core_facts", "gold_set_version": "0.1.0", "model_version": "v", "metrics_json": {}, "ci_pass": True, "ran_at": T0},
    "ConsentRecord": {
        "consent_id": "c1", "external_user_id": "u1", "life_id": "l1", "consent_type": "data_processing",
        "scope": {}, "jurisdiction": "CN", "locale": "zh-CN", "document_version": "v1", "granted_at": T0,
    },
    "GoldSetRegistry": {"gold_set_id": "core_facts", "kind": "core_facts", "version": "0.1.0", "item_count": 50, "content_hash": "h", "frozen_at": T0},
    "EmbeddingOutbox": {"outbox_id": "o1", "life_id": "l1", "memory_id": "m1", "embedding_model_version": "", "created_at": T0},
}


def verify_schema() -> dict[str, Any]:
    ok, problems = True, []
    for name, model in ENTITY_MODELS.items():
        sample = _SAMPLES[name]
        try:
            instance = model.model_validate(sample)
            redumped = model.model_validate(instance.model_dump(mode="json"))
            if instance != redumped:
                problems.append(f"{name}: round-trip mismatch")
                ok = False
            try:
                model.model_validate({**sample, "smuggled_field": {"x": 1}})
                problems.append(f"{name}: extra field accepted (contract leak)")
                ok = False
            except Exception:
                pass
        except Exception as exc:  # noqa: BLE001
            problems.append(f"{name}: {exc}")
            ok = False
    return _result("schema_roundtrip", ok, {"entities": len(ENTITY_MODELS), "problems": problems})


# ---------------------------------------------------------------------------
# AC-04 round-trip
# ---------------------------------------------------------------------------


def run_demo_pipeline() -> tuple[InMemoryStore, EventPipeline, list[Any]]:
    store, pipeline = _new_store_and_pipeline()
    results = [pipeline.ingest(dict(e)) for e in DEMO_EVENTS]
    return store, pipeline, results


def verify_roundtrip() -> dict[str, Any]:
    store, _, results = run_demo_pipeline()
    problems: list[str] = []
    if any(r.duplicate for r in results):
        problems.append("unexpected duplicate ingest")
    if len(store.l1_events) != 5 or len(store.l2_events) != 5:
        problems.append(f"expected 5 L1/L2 events, got {len(store.l1_events)}/{len(store.l2_events)}")
    # provenance completeness (architecture §3.2)
    for l1 in store.l1_events:
        for f in ("interpreter_type", "input_hash", "output_json", "extractor_version", "interpreted_at"):
            if getattr(l1, f) in (None, ""):
                problems.append(f"L1 {l1.event_id}: provenance field {f} empty")
    # state deltas: social_need 0.7, energy 0.4
    if abs(store.get_state(life_id="life-demo", state_key="social_need") - 0.7) > 1e-9:
        problems.append("social_need != 0.7")
    if abs(store.get_state(life_id="life-demo", state_key="energy") - 0.4) > 1e-9:
        problems.append("energy != 0.4")
    # slot conflict: two versions both ambiguous (confidence 0.6 < 0.8)
    pets = store.query_memories(life_id="life-demo", slot_key="user.pet_name")
    if len(pets) != 2 or any(p.conflict_state.value != "ambiguous" for p in pets):
        problems.append("same-slot low-confidence pair did not become ambiguous")
    # episodic memory current
    episodic = [m for m in store.memories if m.type.value == "episodic"]
    if len(episodic) != 1 or episodic[0].conflict_state.value != "current":
        problems.append("episodic memory not current")
    # relationship: 0.2 + 0.05*0.8 + 0.08*0.9 = 0.312
    rel = store.get_relationship(life_id="life-demo", subject_id="user")
    if rel is None or abs(rel.attachment - 0.312) > 1e-9:
        problems.append(f"relationship attachment {getattr(rel, 'attachment', None)} != 0.312")
    # outbox rows created per memory insert
    if len(store.outbox) != 3:
        problems.append(f"outbox rows {len(store.outbox)} != 3")
    return _result("pipeline_roundtrip", not problems, {"problems": problems, "l1": len(store.l1_events), "l2": len(store.l2_events), "memories": len(store.memories), "outbox": len(store.outbox)})


# ---------------------------------------------------------------------------
# AC-05 replay
# ---------------------------------------------------------------------------


def verify_replay(report_path: str | None = None) -> dict[str, Any]:
    store, _, _ = run_demo_pipeline()
    report = replay(store, life_id="life-demo")
    ok = report.total == 5 and report.matched == report.total
    detail: dict[str, Any] = {"replay": report.to_dict()}
    if report_path:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        path = Path(report_path)
        path.write_text(json.dumps(detail, ensure_ascii=False, indent=2), encoding="utf-8")
        detail["report_file"] = str(path)
    return _result("replay_consistency", ok, detail)


# ---------------------------------------------------------------------------
# AC-06 LLM boundary
# ---------------------------------------------------------------------------

# The WRITE path reaches deterministic_commit only via pipeline.py. The other
# allowlist entries are: the function itself, its re-export, the replay path
# (architecture §3.3 mandates reusing the same function), and this CLI - which
# is verification tooling and never part of the runtime write path.
_COMMIT_IMPORT_ALLOWLIST = {
    "src/lifeos/events/commit.py",
    "src/lifeos/events/pipeline.py",
    "src/lifeos/events/__init__.py",
    "src/lifeos/replay/replay.py",
    "src/lifeos/cli.py",
}


def verify_boundary() -> dict[str, Any]:
    problems: list[str] = []
    # 1. shape lock: extra field in L1 output is rejected
    try:
        InterpretedOutput.model_validate(
            {"event_type": "user_message", "authoritative_state_write": {"energy": 1.0}}
        )
        problems.append("InterpretedOutput accepted smuggled authoritative field")
    except Exception:
        pass
    # 2. fail-closed ranges
    try:
        deterministic_commit(
            {"event_type": "user_message", "state_deltas": {"energy": 5.0}},
            life_id="l", l1_event_id="i", raw_event_id="r", occurred_at=T0,
            schema_version=SCHEMA_VERSION, policy_version=POLICY_VERSION, rules_version=RULES_VERSION,
        )
        problems.append("out-of-range state delta accepted")
    except CommitError:
        pass
    # 3. token lock: no public direct state setter
    store = InMemoryStore()
    if hasattr(store, "set_state"):
        problems.append("public set_state exists on store - guard removed")
    # 4. status-flow lock: executed / unbacked transitions rejected
    from lifeos.entities import BehaviorIntent, BehaviorStatus, IntentModality

    store.create_instance(life_id="l", personality_seed="s", born_at=T0, schema_version=SCHEMA_VERSION)
    rogue = BehaviorIntent(
        intent_id="b-rogue", life_id="l", intent_type="greet", modality=IntentModality.VERBAL,
        status=BehaviorStatus.EXECUTED, created_at=T0,
    )
    try:
        store.commit_effects(Effects(), intents=[rogue])
        problems.append("executed-status intent accepted without decision")
    except ValueError:
        pass
    unbacked = rogue.model_copy(update={"status": BehaviorStatus.APPROVED})
    try:
        store.commit_effects(Effects(), intents=[unbacked])
        problems.append("approved-status intent accepted without decision")
    except ValueError:
        pass
    # 5. import discipline: deterministic_commit importable only via allowlist.
    # Heuristic tripwire over import statements (docstring mentions are fine);
    # the hard boundary remains the shape/token/flow locks above (01 §7).
    import re

    import_re = re.compile(r"^\s*(?:from\s+[\w.]+\s+import\s|import\s+)", re.MULTILINE)
    for path in (REPO_ROOT / "src" / "lifeos").rglob("*.py"):
        rel = path.relative_to(REPO_ROOT).as_posix()
        if rel in _COMMIT_IMPORT_ALLOWLIST:
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if "deterministic_commit" in line and import_re.match(line):
                problems.append(f"disallowed import of deterministic_commit: {rel}")
                break
    return _result("llm_boundary", not problems, {"problems": problems})


# ---------------------------------------------------------------------------
# AC-07 policy zero side effects
# ---------------------------------------------------------------------------


def _state_view(store: InMemoryStore) -> dict[str, Any]:
    snap = store.snapshot()
    return {
        "states": snap["states"],
        "memories": snap["memories"],
        "relationships": snap["relationships"],
        "outbox": len(snap["outbox"]),
    }


def verify_policy() -> dict[str, Any]:
    problems: list[str] = []
    # (label, event, expect_perception): the RED-02 event carries a perceptual
    # memory candidate - remembering is legitimate; only surfacing it as a topic
    # is rejected (design 01 §6.3: rejection cancels the response, not the
    # perception). RED-01 is intent-only -> full zero-change assertion.
    cases = [
        (
            "RED-01 medical",
            {
                "life_id": "life-demo", "source": "user", "occurred_at": T0,
                "payload": {"structured": {"proposed_intent": {
                    "intent_type": "medical_diagnosis", "modality": "verbal",
                    "reason": {"topic_markers": ["诊断"]}}}},
            },
            False,
        ),
        (
            "RED-02 sensitive topic",
            {
                "life_id": "life-demo", "source": "user", "occurred_at": T0,
                "payload": {"structured": {
                    "memory_candidates": [{
                        "type": "semantic", "content": "用户正在接受心理治疗",
                        "slot_key": "user.therapy", "subject_id": "user",
                        "confidence": 0.95, "importance": 5, "privacy_level": "sensitive"}],
                    "proposed_intent": {
                        "intent_type": "share_observation", "modality": "verbal",
                        "reason": {"topic_markers": ["心理治疗"]}}}},
            },
            True,
        ),
    ]
    for label, event, expect_perception in cases:
        store, pipeline = _new_store_and_pipeline()
        before = _state_view(store)
        outcome = pipeline.ingest(event)
        after = _state_view(store)
        if outcome.decision is None or outcome.decision.result.value != "reject":
            problems.append(f"{label}: decision not reject")
            continue
        if not outcome.decision.rules_hit:
            problems.append(f"{label}: rules_hit empty")
        if outcome.intent is None or outcome.intent.status.value != "rejected":
            problems.append(f"{label}: intent status not rejected")
        # Zero INTENT side effects: states/relationships must never change.
        if before["states"] != after["states"] or before["relationships"] != after["relationships"]:
            problems.append(f"{label}: intent side effects on states/relationships detected")
        if expect_perception:
            grew = len(after["memories"]) - len(before["memories"])
            if grew != 1:
                problems.append(f"{label}: expected exactly 1 perceptual memory, got {grew}")
            if after["outbox"] - before["outbox"] != 1:
                problems.append(f"{label}: perceptual memory missing outbox row")
        elif before != after:
            problems.append(f"{label}: state side effects detected after rejection")
        # audit trail present (rejection is also recorded)
        if len(store.decisions) != 1:
            problems.append(f"{label}: PolicyDecision not recorded")
    # approve control
    store, pipeline = _new_store_and_pipeline()
    outcome = pipeline.ingest({
        "life_id": "life-demo", "source": "user", "occurred_at": T0,
        "payload": {"structured": {"proposed_intent": {
            "intent_type": "greet", "modality": "verbal", "reason": {}}}},
    })
    if outcome.decision is None or outcome.decision.result.value != "approve" or outcome.intent.status.value != "approved":
        problems.append("approve control failed")
    # purity: same inputs -> same decision
    d1 = decide(
        {"intent_id": "x", "life_id": "l", "intent_type": "greet"},
        {"referenced_memories": []},
        decided_at=T0,
    )
    d2 = decide(
        {"intent_id": "x", "life_id": "l", "intent_type": "greet"},
        {"referenced_memories": []},
        decided_at=T0,
    )
    if d1 != d2:
        problems.append("decide() not deterministic")
    return _result("policy_no_side_effect", not problems, {"problems": problems})


# ---------------------------------------------------------------------------
# AC-08 isolation
# ---------------------------------------------------------------------------


def verify_isolation() -> dict[str, Any]:
    problems: list[str] = []
    store, pipeline = _new_store_and_pipeline(life_id="life-a")
    store.create_instance(life_id="life-b", personality_seed="s2", born_at=T0, schema_version=SCHEMA_VERSION)
    pipeline.ingest({
        "life_id": "life-a", "source": "user", "occurred_at": T0,
        "payload": {"structured": {"memory_candidates": [{
            "type": "semantic", "content": "这是A的秘密备忘", "slot_key": "user.note",
            "subject_id": "user", "confidence": 0.9, "importance": 2}]}},
    })
    if store.query_memories(life_id="life-b") != []:
        problems.append("life-b sees life-a memories")
    if store.get_relationship(life_id="life-b", subject_id="user") is not None:
        problems.append("life-b sees life-a relationship")
    try:
        store.query_memories()  # type: ignore[call-arg]
        problems.append("query_memories allowed without life_id")
    except TypeError:
        pass
    try:
        store.query_memories(life_id="life-x")
        problems.append("unknown life_id accepted")
    except Exception as exc:  # noqa: BLE001
        if type(exc).__name__ != "IsolationError":
            problems.append(f"unexpected error type: {type(exc).__name__}")
    # tamper negative control: replay must catch a modified archive
    store2, _, _ = run_demo_pipeline()
    victim = store2.l1_events[1]
    tampered = victim.model_copy(
        update={"output_json": {**victim.output_json, "event_type": "system_note"}}
    )
    store2.l1_events[1] = tampered
    store2._l1_by_id[victim.event_id] = tampered  # keep id-map consistent
    report = replay(store2, life_id="life-demo")
    if report.matched == report.total:
        problems.append("tamper negative-control NOT detected by replay")
    return _result("isolation", not problems, {"problems": problems})


# ---------------------------------------------------------------------------
# environment check (AC-01)
# ---------------------------------------------------------------------------


# K8s probe targets (ADR-0004 / HANDOVER §5-§7).
K8S_NAMESPACE = "lifeos-dev"
K8S_POSTGRES_NODE = "aisi-w7"
K8S_GPU_NODES = ("dtc-w1", "dtc-w2")
K8S_POSTGRES_LABEL = "app=lifeos-postgres"
K8S_GPU_POD = "lifeos-ai-stack-0"
PROVIDER_SECRET_PREFIX = "lifeos-provider"


def envcheck() -> dict[str, Any]:
    """Gate 0 environment check against the K8s cluster (AC-01; ADR-0004).

    kubectl-probe sections (namespace / nodes / postgres pod / GPU exec /
    provider-Secret existence) need kubectl on the runner (ops host). The
    direct-connection postgres section works wherever DATABASE_URL reaches the
    cluster Service. Secret and key VALUES are never printed - names only.
    """
    out: dict[str, Any] = {"k8s": {}, "postgres": {}, "gpu": {}, "provider_keys": {}, "python": sys.version.split()[0]}

    def _run(cmd: list[str], timeout: int = 15) -> tuple[bool, str]:
        if shutil.which(cmd[0]) is None:
            return False, "binary not found"
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
            return proc.returncode == 0, proc.stdout.strip() or proc.stderr.strip()
        except Exception as exc:  # noqa: BLE001
            return False, str(exc)[:200]

    def _kubectl_json(args: list[str], timeout: int = 15) -> tuple[Any, str]:
        ok, text_out = _run(["kubectl", *args], timeout=timeout)
        if not ok:
            return None, text_out
        try:
            return json.loads(text_out), ""
        except ValueError:
            return None, f"non-JSON kubectl output: {text_out[:120]}"

    k8s = out["k8s"]
    if shutil.which("kubectl") is None:
        k8s["kubectl"] = False
        k8s["note"] = "kubectl not on PATH - k8s sections not probed (in-pod runner?)"
    else:
        k8s["kubectl"] = True
        ns_doc, ns_err = _kubectl_json(["get", "namespace", K8S_NAMESPACE, "-o", "json"])
        k8s["namespace"] = {"name": K8S_NAMESPACE, "exists": ns_doc is not None}
        if ns_doc is None:
            k8s["namespace"]["error"] = ns_err
        nodes_doc, _ = _kubectl_json(
            ["get", "nodes", K8S_POSTGRES_NODE, *K8S_GPU_NODES, "-o", "json"]
        )
        nodes: dict[str, Any] = {}
        for item in (nodes_doc or {}).get("items", []):
            conds = {c["type"]: c["status"] for c in item.get("status", {}).get("conditions", [])}
            nodes[item["metadata"]["name"]] = {"ready": conds.get("Ready") == "True"}
        k8s["nodes"] = nodes
        pods_doc, _ = _kubectl_json(
            ["get", "pods", "-n", K8S_NAMESPACE, "-l", K8S_POSTGRES_LABEL, "-o", "json"]
        )
        pg_pods: list[dict[str, Any]] = []
        for item in (pods_doc or {}).get("items", []):
            conds = {c["type"]: c["status"] for c in item.get("status", {}).get("conditions", [])}
            pg_pods.append({
                "name": item["metadata"]["name"],
                "phase": item.get("status", {}).get("phase"),
                "ready": conds.get("Ready") == "True",
            })
        k8s["postgres_pods"] = pg_pods
        k8s["postgres_pod_ready"] = bool(pg_pods) and all(p["ready"] for p in pg_pods)
        provider_secrets: list[str] = []
        ok_secrets, secrets_out = _run(["kubectl", "-n", K8S_NAMESPACE, "get", "secrets", "-o", "name"])
        if ok_secrets:
            provider_secrets = sorted(
                line.split("/", 1)[1] for line in secrets_out.splitlines()
                if line.startswith(f"secret/{PROVIDER_SECRET_PREFIX}")
            )
        k8s["provider_secret_names"] = provider_secrets

    try:
        engine = get_engine()
        if wait_for_db(engine, timeout_s=3):
            with engine.connect() as conn:
                from sqlalchemy import text

                ext = conn.execute(text("SELECT extname FROM pg_extension WHERE extname='vector'")).first()
                out["postgres"] = {"reachable": True, "pgvector_extension": bool(ext)}
        else:
            out["postgres"] = {"reachable": False, "pgvector_extension": None}
    except Exception as exc:  # noqa: BLE001
        out["postgres"] = {"reachable": False, "error": str(exc)[:200]}

    if k8s.get("kubectl"):
        ok_probe, gpu_out = _run(
            ["kubectl", "-n", K8S_NAMESPACE, "exec", K8S_GPU_POD, "--", "nvidia-smi",
             "--query-gpu=name,memory.total", "--format=csv,noheader"],
            timeout=60,
        )
        out["gpu"] = {
            "probe": f"kubectl exec {K8S_GPU_POD} -- nvidia-smi",
            "gpus": gpu_out if ok_probe else None,
            "error": None if ok_probe else gpu_out,
        }
    else:
        out["gpu"] = {"probe": "kubectl exec (skipped - no kubectl)", "gpus": None, "error": None}

    key_vars = [
        "LIFEOS_PROVIDER_A_API_KEY", "OPENAI_API_KEY", "DASHSCOPE_API_KEY",
        "DEEPSEEK_API_KEY", "MOONSHOT_API_KEY", "ZHIPUAI_API_KEY",
    ]
    out["provider_keys"] = {
        "k8s_secret_names": k8s.get("provider_secret_names", []),
        "env_names": [v for v in key_vars if os.environ.get(v)],
        "names_only": True,
        "note": "key VALUES are never printed (K8s Secret existence probe, HANDOVER §5)",
    }

    probed_nodes = k8s.get("nodes") or {}
    nodes_ok = bool(probed_nodes) and all(n.get("ready") for n in probed_nodes.values())
    k8s_ok = (
        bool(k8s.get("kubectl"))
        and bool(k8s.get("namespace", {}).get("exists"))
        and nodes_ok
        and bool(k8s.get("postgres_pod_ready"))
    )
    ok = k8s_ok and out["postgres"].get("reachable", False)
    out["overall"] = "pass" if ok else "incomplete"
    return out


# ---------------------------------------------------------------------------
# DB tier checks (AC-02 / AC-04 / AC-08 DB variants)
# ---------------------------------------------------------------------------


def db_checks() -> dict[str, Any]:
    detail: dict[str, Any] = {}
    try:
        engine = get_engine()
        if not wait_for_db(engine, timeout_s=5):
            return _result("db_tier", False, {"error": "postgres unreachable"})
        with engine.connect() as conn:
            from sqlalchemy import text

            rows = conn.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname='public'")
            ).fetchall()
            have = {r[0] for r in rows}
            from lifeos.store.tables import tables

            missing = sorted(set(tables) - have)
            detail["tables_found"] = len(have)
            detail["missing"] = missing
            # append-only privilege assertion (role created by migration 0001)
            role = conn.execute(text("SELECT 1 FROM pg_roles WHERE rolname='lifeos_app'")).first()
            if role:
                bad = [
                    t for t in ("raw_events", "interpreted_events", "domain_events")
                    if conn.execute(
                        text(f"SELECT has_table_privilege('lifeos_app', '{t}', 'UPDATE')")
                    ).scalar()
                ]
                detail["append_only_privileges"] = "pass" if not bad else f"UPDATE granted: {bad}"
            else:
                detail["append_only_privileges"] = "skipped (role lifeos_app absent; run alembic migration 0001)"
        return _result("db_tier", not detail["missing"], detail)
    except Exception as exc:  # noqa: BLE001
        return _result("db_tier", False, {"error": str(exc)[:300]})


# ---------------------------------------------------------------------------
# gold set commands (AC-09)
# ---------------------------------------------------------------------------


def _load_yaml(path: str) -> dict[str, Any]:
    file = Path(path)
    if not file.exists():
        raise SystemExit(
            f"file not found: {file}\n"
            "Gold set materials follow ADR-0003 (P1 human-authored+dual-review, "
            "or P2 AI-draft+provenance+named-approver). See phases/phase-0/03 doc; "
            "templates: data/goldset/."
        )
    with file.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def goldset_validate(kind: str, file: str, expect_count: int | None, out: str | None) -> dict[str, Any]:
    data = _load_yaml(file)
    report = validate_document(kind, data, expect_count=expect_count) if expect_count else validate_document(kind, data)
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def goldset_register(kind: str, file: str, version: str, notes: str, out: str | None, use_db: bool) -> dict[str, Any]:
    data = _load_yaml(file)
    manifest = build_manifest(kind, version, data, notes=notes)
    if use_db:
        engine = get_engine()
        if not wait_for_db(engine, timeout_s=5):
            raise SystemExit("postgres unreachable - cannot register into GoldSetRegistry")
        persist(engine, manifest)
        manifest["persisted"] = True
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


# ---------------------------------------------------------------------------
# gate0 report (AC-10)
# ---------------------------------------------------------------------------


def gate0_report(with_db: bool, out: str | None) -> dict[str, Any]:
    checks: list[dict[str, Any]] = [
        verify_schema(),
        verify_roundtrip(),
        verify_replay(),
        verify_policy(),
        verify_boundary(),
        verify_isolation(),
    ]
    if with_db:
        checks.append(db_checks())

    goldset_status: dict[str, Any] = {}
    for kind, path in [
        ("core_facts", "data/goldset/core_facts/core_facts_v0.1.yaml"),
        ("behavior_scenario", "data/goldset/behavior_scenarios/behavior_scenarios_v0.1.yaml"),
    ]:
        file = REPO_ROOT / path
        if file.exists():
            doc = _load_yaml(str(file))
            report = validate_document(kind, doc)
            # Structural validity alone is NOT enough for Gate 0: registration
            # (and therefore AC-09) requires signatures per ADR-0003 - P1 dual
            # review or P2 named-approver approval. Unsigned staged files stay
            # pending; they must never silently flip the verdict to PASS.
            review = doc.get("review") or {}
            author, reviewer = review.get("author") or "", review.get("reviewer") or ""
            signed = bool(author) and bool(reviewer) and author != reviewer
            if not report["valid"]:
                status = "fail"
            elif signed:
                status = "pass"
            else:
                status = "pending_approval_signatures"
            goldset_status[kind] = {"file": path, "status": status, "stats": report["stats"]}
        else:
            goldset_status[kind] = {
                "file": path,
                "status": "pending_materials",
                "note": "materials not staged yet (ADR-0003: P1 human-authored+dual-review, "
                "or P2 AI-draft+provenance+independent-review+named-approver signature)",
            }

    gate_criteria = {
        "1_roundtrip": checks[1]["status"],
        "2_replay_100pct": checks[2]["status"],
        "3_llm_cannot_write_authoritative": checks[4]["status"],
        "4_policy_reject_zero_side_effect": checks[3]["status"],
    }
    all_pass = all(c["status"] == "pass" for c in checks) and all(
        v.get("status") == "pass" for v in goldset_status.values()
    )
    pending = any(v.get("status") != "pass" for v in goldset_status.values())
    if pending and all(c["status"] == "pass" for c in checks):
        verdict = "INCOMPLETE"
        if any(v.get("status") == "pending_approval_signatures" for v in goldset_status.values()):
            verdict_note = (
                "engineering checks pass; gold sets staged and structurally valid "
                "but awaiting named-approver signatures (ADR-0003 P2 / AC-09)"
            )
        else:
            verdict_note = "engineering checks pass; gold set materials not staged yet (AC-09)"
    else:
        verdict = "PASS" if all_pass else "FAIL"
        verdict_note = ""

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "schema_version": SCHEMA_VERSION,
        "policy_version": POLICY_VERSION,
        "rules_version": RULES_VERSION,
        "checks": checks,
        "gate_criteria": gate_criteria,
        "gold_sets": goldset_status,
        "environment": envcheck(),
        "verdict": verdict,
        "verdict_note": verdict_note,
    }
    target = Path(out) if out else REPORTS_DIR / "gate0_report.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report["report_file"] = str(target)
    return report


# ---------------------------------------------------------------------------
# entrypoint
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lifeos", description="LifeOS Phase 0 verification CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("envcheck")

    verify = sub.add_parser("verify")
    vsub = verify.add_subparsers(dest="what", required=True)
    vsub.add_parser("schema")
    vsub.add_parser("roundtrip")
    rp = vsub.add_parser("replay")
    rp.add_argument("--report", default=None)
    vsub.add_parser("policy")
    vsub.add_parser("boundary")
    vsub.add_parser("isolation")
    vsub.add_parser("all")

    gs = sub.add_parser("goldset")
    gsub = gs.add_subparsers(dest="what", required=True)
    gv = gsub.add_parser("validate")
    gv.add_argument("--kind", required=True, choices=["core_facts", "behavior_scenario"])
    gv.add_argument("--file", required=True)
    gv.add_argument("--expect-count", type=int, default=None)
    gv.add_argument("--out", default=None)
    gr = gsub.add_parser("register")
    gr.add_argument("--kind", required=True, choices=["core_facts", "behavior_scenario"])
    gr.add_argument("--file", required=True)
    gr.add_argument("--version", required=True)
    gr.add_argument("--notes", default="")
    gr.add_argument("--out", default=None)
    gr.add_argument("--db", action="store_true", help="persist into GoldSetRegistry (requires PostgreSQL)")

    g0 = sub.add_parser("gate0")
    g0sub = g0.add_subparsers(dest="what", required=True)
    rep = g0sub.add_parser("report")
    rep.add_argument("--with-db", action="store_true")
    rep.add_argument("--out", default=None)

    dw = sub.add_parser("db")
    dwsub = dw.add_subparsers(dest="what", required=True)
    dwait = dwsub.add_parser("wait")
    dwait.add_argument("--timeout", type=int, default=30)

    args = parser.parse_args(argv)

    if args.command == "envcheck":
        payload = envcheck()
    elif args.command == "verify":
        if args.what == "schema":
            payload = verify_schema()
        elif args.what == "roundtrip":
            payload = verify_roundtrip()
        elif args.what == "replay":
            payload = verify_replay(args.report)
        elif args.what == "policy":
            payload = verify_policy()
        elif args.what == "boundary":
            payload = verify_boundary()
        elif args.what == "isolation":
            payload = verify_isolation()
        else:
            checks = [
                verify_schema(), verify_roundtrip(), verify_replay(),
                verify_policy(), verify_boundary(), verify_isolation(),
            ]
            ok = all(c["status"] == "pass" for c in checks)
            payload = {"name": "verify_all", "status": "pass" if ok else "fail", "checks": checks}
    elif args.command == "goldset":
        if args.what == "validate":
            payload = goldset_validate(args.kind, args.file, args.expect_count, args.out)
        else:
            payload = goldset_register(args.kind, args.file, args.version, args.notes, args.out, args.db)
    elif args.command == "gate0":
        payload = gate0_report(args.with_db, args.out)
    elif args.command == "db":
        engine = get_engine()
        payload = {"reachable": wait_for_db(engine, timeout_s=args.timeout)}
    else:  # pragma: no cover
        parser.error("unknown command")

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    status = payload.get("status") or payload.get("verdict") or payload.get("overall")
    return 0 if status in (None, "pass", "PASS") else 1


if __name__ == "__main__":
    sys.exit(main())
