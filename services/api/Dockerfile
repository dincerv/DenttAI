FROM python:3.11-slim

WORKDIR /app

# Sistem bağımlılıkları (Pillow, asyncpg için)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Python bağımlılıkları — önce kopyala (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Uygulama kodunu kopyala
COPY . .

EXPOSE 8000

# Railway $PORT inject eder; lokal için 8000 fallback
# workers=1: APScheduler + Redis tek process'te güvenli
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
