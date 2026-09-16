#!/bin/sh
set -eu

LISTEN_PORT="${PORT:-8080}"
AUTH_HOST="${AUTH_SERVICE_HOST:-denttai.railway.internal}"
AUTH_PORT="${AUTH_SERVICE_PORT:-8080}"
APPT_HOST="${APPOINTMENT_SERVICE_HOST:-meticulous-rejoicing.railway.internal}"
APPT_PORT="${APPOINTMENT_SERVICE_PORT:-8080}"

AUTH_UPSTREAM="http://${AUTH_HOST}:${AUTH_PORT}"
APPT_UPSTREAM="http://${APPT_HOST}:${APPT_PORT}"

sed "s/LISTEN_PORT/${LISTEN_PORT}/g" /etc/nginx/nginx.cloud.conf > /etc/nginx/nginx.conf

sed \
  -e "s|AUTH_UPSTREAM|${AUTH_UPSTREAM}|g" \
  -e "s|APPT_UPSTREAM|${APPT_UPSTREAM}|g" \
  /etc/nginx/routes.cloud.conf > /etc/nginx/routes.proxy.conf

echo "[gateway] listen 0.0.0.0:${LISTEN_PORT}" >&2
echo "[gateway] auth → ${AUTH_UPSTREAM}" >&2
echo "[gateway] appointment → ${APPT_UPSTREAM}" >&2

nginx -t

exec "$@"
