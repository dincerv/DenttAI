#!/bin/bash
# ============================================================
# DentAI Flow — PostgreSQL Backup (Linux/macOS)
# Windows: powershell -File scripts/backup.ps1
#
# Neon (önerilen, canlı): DATABASE_URL .env'de olsun
# Yerel docker: CONTAINER_NAME=dentai_postgres
# ============================================================

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ -f .env ]; then
  set -a
  # shellcheck source=../.env
  source .env
  set +a
fi

BACKUP_DIR="${BACKUP_DIR:-$ROOT/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
mkdir -p "${BACKUP_DIR}"

normalize_url() {
  local url="$1"
  url="${url#postgresql+asyncpg://}"
  if [ "$url" = "$1" ]; then
    url="$1"
  else
    url="postgresql://${url}"
  fi
  url="${url/postgres:\/\//postgresql:\/\/}"
  if [[ "$url" == *neon.tech* && "$url" != *sslmode=* ]]; then
    if [[ "$url" == *\?* ]]; then
      url="${url}&sslmode=require"
    else
      url="${url}?sslmode=require"
    fi
  fi
  printf '%s' "$url"
}

dump_ok() {
  local file="$1"
  if [ ! -s "$file" ]; then
    echo "HATA: yedek bos: $file" >&2
    exit 1
  fi
  local size
  size="$(wc -c < "$file" | tr -d ' ')"
  echo "[$(date)] tamam: $file (${size} bytes)"
}

if [ -n "${DATABASE_URL:-}" ]; then
  URL="$(normalize_url "$DATABASE_URL")"
  HOST="${URL##*@}"
  HOST="${HOST%%/*}"
  echo "[$(date)] Neon yedek: host=${HOST}"
  OUT="${BACKUP_DIR}/dentai_neon_${TIMESTAMP}.dump"
  pg_dump "$URL" --no-owner --no-acl -Fc -f "$OUT"
  dump_ok "$OUT"
else
  : "${POSTGRES_USER:?POSTGRES_USER or DATABASE_URL required}"
  : "${POSTGRES_DB:?POSTGRES_DB or DATABASE_URL required}"
  CONTAINER_NAME="${CONTAINER_NAME:-dentai_postgres}"
  echo "[$(date)] Yerel docker yedek: ${CONTAINER_NAME}"
  OUT="${BACKUP_DIR}/dentai_local_${TIMESTAMP}.dump"
  docker exec "${CONTAINER_NAME}" pg_dump -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" --no-owner --no-acl -Fc \
    > "$OUT"
  dump_ok "$OUT"
fi

DELETED="$(find "${BACKUP_DIR}" -name "dentai_*.dump" -mtime +"${RETENTION_DAYS}" -delete -print | wc -l | tr -d ' ')"
echo "[$(date)] ${DELETED} eski yedek silindi (>${RETENTION_DAYS} gun)"
echo "Kod yedegi git/GitHub. Dump dosyalari git'e girmez."
