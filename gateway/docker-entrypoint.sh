#!/bin/sh
set -eu

CERT_DIR="/etc/nginx/certs"
CERT_PATH="${GATEWAY_TLS_CERT_PATH:-${CERT_DIR}/fullchain.pem}"
KEY_PATH="${GATEWAY_TLS_KEY_PATH:-${CERT_DIR}/privkey.pem}"
TLS_CN="${GATEWAY_TLS_CN:-localhost}"
AUTH_HOST="${AUTH_SERVICE_HOST:-auth-service}"
AUTH_PORT="${AUTH_SERVICE_PORT:-8001}"

mkdir -p "$(dirname "${CERT_PATH}")"

if [ ! -f "${CERT_PATH}" ] || [ ! -f "${KEY_PATH}" ]; then
  echo "[gateway] TLS certificate not found; generating self-signed certificate for ${TLS_CN}" >&2
  openssl req -x509 -nodes -newkey rsa:2048 -days 365 \
    -subj "/CN=${TLS_CN}" \
    -keyout "${KEY_PATH}" \
    -out "${CERT_PATH}"
fi

# Cloud/Railway: auth upstream hostname override
if [ -f /etc/nginx/routes.conf ]; then
  sed -i "s|http://auth-service:8001|http://${AUTH_HOST}:${AUTH_PORT}|g" /etc/nginx/routes.conf
  echo "[gateway] auth upstream → http://${AUTH_HOST}:${AUTH_PORT}" >&2
fi

exec "$@"
