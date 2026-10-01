#!/usr/bin/env bash
# ============================================================================
# LifeOS Phase 0 one-shot acceptance (execution plan 02 §0).
# K8s acceptance path per ADR-0004 + HANDOVER §5-§7 (docker compose demoted to
# local dev fallback). Usage:
#   bash scripts/gate0_check.sh            # tier A only (no DB, no k8s)
#   bash scripts/gate0_check.sh --with-db  # + K8s postgres tier (AC-01/AC-02)
# Runner:
#   host (kubectl available): applies k8s/, waits for postgres, then opens a
#     temporary `kubectl port-forward` for the python steps (password fetched
#     from Secret lifeos-postgres, never printed or committed).
#   in-pod (no kubectl): DATABASE_URL must already be injected (Secret
#     lifeos-postgres -> ai-stack pod); k8s apply/wait steps are skipped.
# Report: phases/phase-0/reports/gate0_report.json
# ============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON="${PYTHON:-python3}"
NS="lifeos-dev"
PF_PORT="${PF_PORT:-15432}"

cleanup() { [[ -n "${PF_PID:-}" ]] && kill "${PF_PID}" 2>/dev/null || true; }
trap cleanup EXIT

echo "== [1/4] tier A: pytest (no DB) =="
"$PYTHON" -m pytest tests -q

echo "== [2/4] tier A: CLI verify all =="
"$PYTHON" -m lifeos.cli verify all

if [[ "${1:-}" == "--with-db" ]]; then
  # Exit-code-honest DB probe: cli `db wait` always exits 0 (it prints
  # {"reachable": ...} instead), so the script probes via wait_for_db directly.
  DB_PROBE='import sys
from lifeos.store.db import get_engine, wait_for_db
sys.exit(0 if wait_for_db(get_engine(), timeout_s=2) else 1)'
  echo "== [3/4] tier B: K8s postgres + alembic + pytest -m db =="
  if command -v kubectl >/dev/null 2>&1; then
    kubectl apply -k k8s/
    kubectl -n "$NS" wait --for=condition=ready pod -l app=lifeos-postgres --timeout=180s
  else
    echo "kubectl not found - assuming in-cluster runner (stack assumed applied)"
  fi

  if ! "$PYTHON" -c "$DB_PROBE"; then
    if command -v kubectl >/dev/null 2>&1; then
      echo "DATABASE_URL not reachable - opening port-forward 127.0.0.1:${PF_PORT} -> svc/postgres:5432"
      PG_PASSWORD="$(kubectl -n "$NS" get secret lifeos-postgres -o jsonpath='{.data.POSTGRES_PASSWORD}' | base64 -d)"
      kubectl -n "$NS" port-forward svc/postgres "${PF_PORT}:5432" >/dev/null 2>&1 &
      PF_PID=$!
      export DATABASE_URL="postgresql+psycopg://lifeos:${PG_PASSWORD}@127.0.0.1:${PF_PORT}/lifeos"
      for _ in $(seq 1 30); do
        "$PYTHON" -c "$DB_PROBE" && break
        sleep 1
      done
    else
      echo "FATAL: DATABASE_URL unreachable and no kubectl for port-forward" >&2
      exit 1
    fi
  fi
  "$PYTHON" -c "$DB_PROBE" || { echo "FATAL: postgres unreachable after setup" >&2; exit 1; }

  if "$PYTHON" -m alembic -c alembic.ini upgrade head; then
    echo "alembic: head applied"
  else
    echo "WARN: alembic upgrade failed - AC-02 must be fixed before Gate 0 PASS" >&2
    exit 1
  fi
  "$PYTHON" -m pytest tests -q -m db
else
  echo "== [3/4] tier B: SKIPPED (run with --with-db; Gate 0 cannot PASS without it) =="
fi

echo "== [4/4] Gate 0 report =="
mkdir -p phases/phase-0/reports
if [[ "${1:-}" == "--with-db" ]]; then
  set +e
  "$PYTHON" -m lifeos.cli gate0 report --with-db
  RC=$?
  set -e
else
  set +e
  "$PYTHON" -m lifeos.cli gate0 report
  RC=$?
  set -e
fi

echo "Done. Report: phases/phase-0/reports/gate0_report.json"
echo "gate0 exit code: $RC (0=PASS, 1=FAIL or INCOMPLETE - e.g. gold sets pending human authoring)"
exit 0
