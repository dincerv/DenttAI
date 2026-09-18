#!/bin/bash
# DentAI Flow — Health Check (monolith)
# Kullanım: ./scripts/healthcheck.sh
# BASE_URL varsayılan: http://localhost:8000

set -euo pipefail

if [ -f .env ]; then
  set -a
  # shellcheck source=../.env
  source .env
  set +a
fi

BASE_URL="${BASE_URL:-http://localhost:8000}"
FAILED=0

check() {
  local name=$1
  local url=$2
  local response
  response=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 --max-time 10 "${url}" 2>/dev/null || echo "000")
  if [ "${response}" = "200" ]; then
    echo "OK  ${name}"
  else
    echo "FAIL ${name} (HTTP ${response})"
    FAILED=$((FAILED + 1))
  fi
}

echo "=== DentAI Flow Health Check === ($(date))"
check "API /health"          "${BASE_URL}/health"
check "API /api/health"      "${BASE_URL}/api/health"
check "API /api/auth/health" "${BASE_URL}/api/auth/health"

if [ ${FAILED} -gt 0 ]; then
  echo "${FAILED} check failed"
  exit 1
fi
echo "All checks passed."
