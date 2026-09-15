#!/usr/bin/env bash
# ============================================================================
# LifeOS Phase 0 one-shot acceptance (execution plan 02 §0).
# Usage:
#   bash scripts/gate0_check.sh            # tier A only (no DB)
#   bash scripts/gate0_check.sh --with-db  # + PostgreSQL tier (needs Docker)
# Report: phases/phase-0/reports/gate0_report.json
# ============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON="${PYTHON:-python3}"

echo "== [1/4] tier A: pytest (no DB) =="
"$PYTHON" -m pytest tests -q

echo "== [2/4] tier A: CLI verify all =="
"$PYTHON" -m lifeos.cli verify all

if [[ "${1:-}" == "--with-db" ]]; then
  echo "== [3/4] tier B: postgres + alembic + pytest -m db =="
  docker compose up -d postgres
  "$PYTHON" -m lifeos.cli db wait --timeout 60 >/dev/null
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
