#!/bin/bash
# ============================================================
# DentAI Flow — Health Check Script
# Tüm servislerin sağlık durumunu kontrol eder.
# Cron veya monitoring aracıyla kullanılabilir.
# Kullanım: ./scripts/healthcheck.sh
# ============================================================

set -euo pipefail

if [ -f .env ]; then
  set -a
  # shellcheck source=../.env
  source .env
  set +a
fi

BASE_URL="${BASE_URL:-http://localhost}"
FAILED=0

check() {
  local name=$1
  local url=$2
  local response
  response=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 --max-time 10 "${url}" 2>/dev/null || echo "000")
  if [ "${response}" = "200" ]; then
    echo "✓ ${name}: OK"
  else
    echo "✗ ${name}: FAIL (HTTP ${response})"
    FAILED=$((FAILED + 1))
  fi
}

echo "=== DentAI Flow Health Check === ($(date))"
echo ""

check "Gateway"           "${BASE_URL}/health"
check "Auth Service"      "${BASE_URL}/api/auth/health"
check "Appointment Svc"   "${BASE_URL}/api/appointments/health"
check "Notification Svc"  "${BASE_URL}/api/notifications/health"
check "Inventory Service"  "${BASE_URL}/api/inventory/health"
check "Analytics Service"  "${BASE_URL}/api/analytics/health"
check "Integration Svc"   "${BASE_URL}/api/integration/health"

echo ""
if [ ${FAILED} -gt 0 ]; then
  echo "⚠ ${FAILED} servis sağlıksız!"
  exit 1
else
  echo "✓ Tüm servisler sağlıklı."
  exit 0
fi
