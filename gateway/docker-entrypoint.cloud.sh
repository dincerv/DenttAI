#!/bin/sh
set -eu

LISTEN_PORT="${PORT:-80}"
AUTH_HOST="${AUTH_SERVICE_HOST:-denttai.railway.internal}"
AUTH_PORT="${AUTH_SERVICE_PORT:-8080}"
APPT_HOST="${APPOINTMENT_SERVICE_HOST:-meticulous-rejoicing.railway.internal}"
APPT_PORT="${APPOINTMENT_SERVICE_PORT:-8080}"

# nginx.conf: listen PORT
sed "s/LISTEN_PORT/${LISTEN_PORT}/g" /etc/nginx/nginx.cloud.conf > /etc/nginx/nginx.conf

# upstream hostnames
sed -i "s|http://auth-service:8001|http://${AUTH_HOST}:${AUTH_PORT}|g" /etc/nginx/routes.conf
sed -i "s|http://appointment-service:8002|http://${APPT_HOST}:${APPT_PORT}|g" /etc/nginx/routes.conf

echo "[gateway] listen :${LISTEN_PORT}" >&2
echo "[gateway] auth → http://${AUTH_HOST}:${AUTH_PORT}" >&2
echo "[gateway] appointment → http://${APPT_HOST}:${APPT_PORT}" >&2

exec "$@"
