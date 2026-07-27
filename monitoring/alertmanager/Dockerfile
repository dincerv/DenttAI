FROM prom/alertmanager:v0.28.1

COPY alertmanager.yml.tmpl /etc/alertmanager/alertmanager.yml.tmpl
COPY --chmod=755 docker-entrypoint.sh /docker-entrypoint.sh

ENTRYPOINT ["/docker-entrypoint.sh"]
