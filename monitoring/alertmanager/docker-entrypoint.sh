#!/bin/sh
set -eu

: "${ALERTMANAGER_EMAIL_TO:?ALERTMANAGER_EMAIL_TO is required}"
: "${ALERTMANAGER_EMAIL_FROM:?ALERTMANAGER_EMAIL_FROM is required}"
: "${ALERTMANAGER_SMTP_SMARTHOST:?ALERTMANAGER_SMTP_SMARTHOST is required}"
: "${ALERTMANAGER_SMTP_AUTH_USERNAME:?ALERTMANAGER_SMTP_AUTH_USERNAME is required}"
: "${ALERTMANAGER_SMTP_AUTH_PASSWORD:?ALERTMANAGER_SMTP_AUTH_PASSWORD is required}"

cat > /etc/alertmanager/alertmanager.yml <<EOF
global:
  smtp_smarthost: '${ALERTMANAGER_SMTP_SMARTHOST}'
  smtp_from: '${ALERTMANAGER_EMAIL_FROM}'
  smtp_auth_username: '${ALERTMANAGER_SMTP_AUTH_USERNAME}'
  smtp_auth_password: '${ALERTMANAGER_SMTP_AUTH_PASSWORD}'
  smtp_require_tls: ${ALERTMANAGER_SMTP_REQUIRE_TLS:-true}

route:
  receiver: 'email-ops'
  group_by: ['alertname', 'service', 'severity']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 2h

receivers:
  - name: 'email-ops'
    email_configs:
      - to: '${ALERTMANAGER_EMAIL_TO}'
        send_resolved: true
        headers:
          Subject: '[DentAI] {{ .CommonLabels.severity }} - {{ .CommonLabels.alertname }}'

templates:
  - '/etc/alertmanager/template/*.tmpl'
EOF

exec /bin/alertmanager --config.file=/etc/alertmanager/alertmanager.yml --storage.path=/alertmanager
