#!/bin/bash
# ============================================================
# DentAI Flow — Deploy Script
# Production sunucusunda çalıştırılır.
# Kullanım: ./scripts/deploy.sh [--no-build]
# ============================================================

set -euo pipefail

COMPOSE_FILE="docker-compose.prod.yml"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

cd "${PROJECT_DIR}"

echo "[$(date)] Deploy başlıyor..."

# 1. Kodu güncelle
echo "→ Git pull..."
git pull origin main

# 2. .env kontrolü ve shell ortamına yükleme
if [ ! -f .env ]; then
  echo "HATA: .env dosyası bulunamadı. cp .env.example .env yapıp doldurun."
  exit 1
fi
set -a
# shellcheck source=../.env
source .env
set +a
: "${POSTGRES_USER:?POSTGRES_USER is required}"
: "${POSTGRES_DB:?POSTGRES_DB is required}"
echo "  .env yüklendi (POSTGRES_DB=${POSTGRES_DB}, POSTGRES_USER=${POSTGRES_USER})"

# 3. Build & deploy
if [ "${1:-}" = "--no-build" ]; then
  echo "→ Servisler yeniden başlatılıyor (build atlandı)..."
  docker compose -f "${COMPOSE_FILE}" up -d
else
  echo "→ Image'lar build ediliyor ve servisler başlatılıyor..."
  docker compose -f "${COMPOSE_FILE}" up -d --build
fi

# 4. Postgres'in hazır olmasını bekle
echo "→ Postgres hazır bekleniyor..."
for i in $(seq 1 30); do
  if docker exec dentai_postgres pg_isready -U "${POSTGRES_USER}" > /dev/null 2>&1; then
    echo "  Postgres hazır."
    break
  fi
  sleep 2
done

# 5. Migration registry tablosunu oluştur (idempotent — sadece ilk kez etkili olur)
docker exec -i dentai_postgres psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" <<'SQL'
CREATE TABLE IF NOT EXISTS schema_migrations (
    filename   TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
SQL

# 6. Sadece daha önce çalıştırılmamış migration'ları uygula
echo "→ Veritabanı migration'ları kontrol ediliyor..."
for migration in shared/db/migrations/*.sql; do
  [ -f "$migration" ] || continue
  filename="$(basename "$migration")"
  already_applied=$(docker exec dentai_postgres psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -tAc \
    "SELECT COUNT(*) FROM schema_migrations WHERE filename = '${filename}';")
  if [ "${already_applied}" = "1" ]; then
    echo "  SKIP (zaten uygulandı): ${filename}"
  else
    echo "  Uygulanıyor: ${filename}"
    docker exec -i dentai_postgres psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" < "$migration"
    docker exec dentai_postgres psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -c \
      "INSERT INTO schema_migrations (filename) VALUES ('${filename}');"
    echo "    ✓ ${filename} uygulandı ve kayıt edildi."
  fi
done

# 7. Sağlık kontrolü
echo "→ Servisler denetleniyor..."
sleep 15

docker compose -f "${COMPOSE_FILE}" ps --format "table {{.Name}}\t{{.Status}}"

# 8. Health endpoint kontrolü
echo ""
BASE_URL="${BASE_URL:-http://localhost}" ./scripts/healthcheck.sh || echo "⚠ Bazı servisler henüz hazır olmayabilir, bekledikten sonra tekrar deneyin."

echo ""
echo "[$(date)] ✓ Deploy tamamlandı."
