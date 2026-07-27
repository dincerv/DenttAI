#!/bin/sh
set -eu

CERT_DIR="/etc/nginx/certs"
CERT_PATH="${GATEWAY_TLS_CERT_PATH:-${CERT_DIR}/fullchain.pem}"
KEY_PATH="${GATEWAY_TLS_KEY_PATH:-${CERT_DIR}/privkey.pem}"
TLS_CN="${GATEWAY_TLS_CN:-localhost}"

mkdir -p "$(dirname "${CERT_PATH}")"

if [ ! -f "${CERT_PATH}" ] || [ ! -f "${KEY_PATH}" ]; then
  echo "[gateway] TLS certificate not found; generating self-signed certificate for ${TLS_CN}" >&2
  openssl req -x509 -nodes -newkey rsa:2048 -days 365 \
    -subj "/CN=${TLS_CN}" \
    -keyout "${KEY_PATH}" \
    -out "${CERT_PATH}"
fi

exec "$@"