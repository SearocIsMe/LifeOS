#!/usr/bin/env bash
# ============================================================================
# Create / rotate the LifeOS secrets in namespace lifeos-dev (ADR-0004).
# Passwords are generated with `openssl rand -hex 16` and NEVER printed,
# stored in files, or committed - they live ONLY in the cluster Secrets.
#
# Usage:
#   bash k8s/create-secrets.sh            # create both secrets (idempotent update)
#   bash k8s/create-secrets.sh --rotate   # + ALTER USER in DB, then rolling restart
#                                         #   of postgres & ai-stack (use after any
#                                         #   password exposure incident)
#
# Prereq: namespace exists (`kubectl apply -f k8s/10-namespace.yaml`).
# For --rotate the postgres pod must be Running (psql is exec'd into it).
# ============================================================================
set -euo pipefail

NS="lifeos-dev"
ROTATE=0
[[ "${1:-}" == "--rotate" ]] && ROTATE=1

NEW_PW="$(openssl rand -hex 16)"   # URL-safe: hex only, no escaping issues
NEW_AI_PW="$(openssl rand -hex 16)"

if ! kubectl get namespace "$NS" >/dev/null 2>&1; then
  echo "FATAL: namespace $NS not found - run: kubectl apply -f k8s/10-namespace.yaml" >&2
  exit 1
fi

# 1) Upsert the postgres secret (POSTGRES_* for the image bootstrap +
#    DATABASE_URL injected into the ai-stack pod by k8s/40-dev-stack.yaml).
kubectl -n "$NS" create secret generic lifeos-postgres \
  --from-literal=POSTGRES_USER=lifeos \
  --from-literal=POSTGRES_PASSWORD="${NEW_PW}" \
  --from-literal=POSTGRES_DB=lifeos \
  --from-literal=DATABASE_URL="postgresql+psycopg://lifeos:${NEW_PW}@postgres.lifeos-dev.svc.cluster.local:5432/lifeos" \
  --dry-run=client -o yaml | kubectl apply -f - >/dev/null
echo "secret/lifeos-postgres upserted (values not shown)"

# 2) Upsert the ai-stack secret (APP_PASSWORD / JUPYTER_TOKEN / CODE_SERVER_PASSWORD).
kubectl -n "$NS" create secret generic lifeos-ai-stack \
  --from-literal=password="${NEW_AI_PW}" \
  --dry-run=client -o yaml | kubectl apply -f - >/dev/null
echo "secret/lifeos-ai-stack upserted (values not shown)"

# 3) Rotate mode: the password already lives INSIDE the existing DB cluster -
#    updating the Secret alone is NOT enough, ALTER USER must run first.
#    (On a fresh empty volume, skip --rotate: initdb uses the Secret value.)
if (( ROTATE )); then
  echo "rotating in-database password (ALTER USER via stdin, value not echoed)..."
  echo "ALTER USER lifeos WITH PASSWORD '${NEW_PW}';" \
    | kubectl -n "$NS" exec -i lifeos-postgres-0 -- psql -U lifeos -d lifeos -qAt
  kubectl -n "$NS" rollout restart statefulset/lifeos-postgres
  kubectl -n "$NS" rollout restart statefulset/lifeos-ai-stack
  kubectl -n "$NS" rollout status statefulset/lifeos-postgres --timeout=240s
  kubectl -n "$NS" rollout status statefulset/lifeos-ai-stack --timeout=240s
  echo "rotation complete: both statefulsets restarted with the new secret"
else
  echo "note: if postgres data already exists, run '$0 --rotate' instead of re-creating"
fi

# 4) Smoke check (exit-code-honest probe; DATABASE_URL reaches the cluster DNS).
if kubectl -n "$NS" get pod -l app=lifeos-ai-stack -o jsonpath='{.items[0].metadata.name}' 2>/dev/null | grep -q .; then
  kubectl -n "$NS" exec lifeos-ai-stack-0 -- /data/LifeOS/.venv/bin/python - <<'PYEOF' >/dev/null 2>&1 && echo "smoke check: DB reachable via injected DATABASE_URL" || echo "smoke check: SKIPPED/FAILED (venv or pod not ready yet)"
import sys
from lifeos.store.db import get_engine, wait_for_db
sys.exit(0 if wait_for_db(get_engine(), timeout_s=3) else 1)
PYEOF
fi
