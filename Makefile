# ============================================================
# DentAI Flow — Makefile
# Yaygın komutlar için kısayollar
# ============================================================

.PHONY: up down build logs ps clean

## Tüm servisleri başlat
up:
	docker compose up -d

## Tüm servisleri durdur
down:
	docker compose down

## Image'ları yeniden oluştur
build:
	docker compose build --no-cache

## Log akışını izle
logs:
	docker compose logs -f

## Çalışan container'ları listele
ps:
	docker compose ps

## Container + volume'ları temizle (dikkatli!)
clean:
	docker compose down -v --remove-orphans

## Postgres'e bağlan
db:
	docker compose exec postgres psql -U dentai -d dentai_db
