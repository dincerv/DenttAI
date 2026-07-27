#!/bin/bash
# ============================================================
# DentAI Flow — PostgreSQL Backup Script
# Günlük cron ile çalıştırılmak üzere tasarlandı.
# Kullanım: ./scripts/backup.sh
# Cron örneği: 0 3 * * * /opt/daf/scripts/backup.sh >> /var/log/dentai-backup.log 2>&1
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

# ── Konfigürasyon ────────────────────────────────────────
BACKUP_DIR="${BACKUP_DIR:-/opt/daf/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
CONTAINER_NAME="${CONTAINER_NAME:-dentai_postgres}"
PG_USER="${POSTGRES_USER}"
PG_DB="${POSTGRES_DB}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/dentai_${TIMESTAMP}.sql.gz"

# ── Klasör oluştur ──────────────────────────────────────
mkdir -p "${BACKUP_DIR}"

# ── Backup al ───────────────────────────────────────────
echo "[$(date)] Backup başlıyor: ${BACKUP_FILE}"

docker exec "${CONTAINER_NAME}" \
  pg_dump -U "${PG_USER}" -d "${PG_DB}" --no-owner --no-acl \
  | gzip > "${BACKUP_FILE}"

FILESIZE=$(stat -f%z "${BACKUP_FILE}" 2>/dev/null || stat --printf="%s" "${BACKUP_FILE}" 2>/dev/null || echo "unknown")
echo "[$(date)] Backup tamamlandı: ${BACKUP_FILE} (${FILESIZE} bytes)"

# ── Eski backup'ları temizle ────────────────────────────
DELETED=$(find "${BACKUP_DIR}" -name "dentai_*.sql.gz" -mtime +"${RETENTION_DAYS}" -delete -print | wc -l)
echo "[$(date)] ${DELETED} eski backup silindi (>${RETENTION_DAYS} gün)"

# ── Doğrulama ───────────────────────────────────────────
if [ -s "${BACKUP_FILE}" ]; then
  echo "[$(date)] ✓ Backup doğrulandı — dosya boş değil."
else
  echo "[$(date)] ✗ HATA: Backup dosyası boş!"
  exit 1
fi
