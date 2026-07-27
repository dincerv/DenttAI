#!/bin/bash
# ============================================================
# DentAI Flow — PostgreSQL Restore Script
# Kullanım: ./scripts/restore.sh backups/dentai_20260503_030000.sql.gz
# ============================================================

set -euo pipefail

if [ -f .env ]; then
  set -a
  # shellcheck source=../.env
  source .env
  set +a
fi

: "${POSTGRES_USER:?POSTGRES_USER is required}"
: "${POSTGRES_DB:?POSTGRES_DB is required}"

BACKUP_FILE="${1:?Kullanım: ./scripts/restore.sh <backup_dosyasi.sql.gz>}"
CONTAINER_NAME="${CONTAINER_NAME:-dentai_postgres}"
PG_USER="${POSTGRES_USER}"
PG_DB="${POSTGRES_DB}"

if [ ! -f "${BACKUP_FILE}" ]; then
  echo "HATA: ${BACKUP_FILE} bulunamadı."
  exit 1
fi

echo "⚠ UYARI: Bu işlem mevcut '${PG_DB}' veritabanını SİLECEK ve yedeği yükleyecek."
echo "Devam etmek için 'EVET' yazın:"
read -r CONFIRM
if [ "${CONFIRM}" != "EVET" ]; then
  echo "İptal edildi."
  exit 0
fi

echo "[$(date)] Mevcut bağlantılar kapatılıyor..."
docker exec "${CONTAINER_NAME}" psql -U "${PG_USER}" -d postgres \
  -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='${PG_DB}' AND pid <> pg_backend_pid();" \
  || true

echo "[$(date)] Veritabanı yeniden oluşturuluyor..."
docker exec "${CONTAINER_NAME}" psql -U "${PG_USER}" -d postgres \
  -c "DROP DATABASE IF EXISTS ${PG_DB};"
docker exec "${CONTAINER_NAME}" psql -U "${PG_USER}" -d postgres \
  -c "CREATE DATABASE ${PG_DB} OWNER ${PG_USER};"

echo "[$(date)] Yedek yükleniyor: ${BACKUP_FILE}..."
gunzip -c "${BACKUP_FILE}" | docker exec -i "${CONTAINER_NAME}" psql -U "${PG_USER}" -d "${PG_DB}"

echo "[$(date)] ✓ Restore tamamlandı."
echo "Servisleri yeniden başlatmayı unutma:"
echo "  docker compose -f docker-compose.prod.yml restart"
