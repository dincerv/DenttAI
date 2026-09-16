FROM nginx:1.27-alpine

RUN apk add --no-cache openssl

COPY nginx.conf /etc/nginx/nginx.conf
COPY routes.conf /etc/nginx/routes.conf
COPY docker-entrypoint.sh /docker-entrypoint.sh

# Windows checkout CRLF kırılmasını önle
RUN sed -i 's/\r$//' /docker-entrypoint.sh \
	&& chmod +x /docker-entrypoint.sh \
	&& mkdir -p /etc/nginx/certs

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]

EXPOSE 80 443
