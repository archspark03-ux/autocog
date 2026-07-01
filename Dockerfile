# AvtonomCogitate — Dockerfile
# Çox yüngül image, təhlükəsiz, sürətli

FROM python:3.12-slim

# Metadata
LABEL maintainer="avtonom-cogitate"
LABEL description="7/24 işləyən avtonom beyin sistemi"
LABEL version="0.1.0"

# Sistem paketləri
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# İş qovluğu
WORKDIR /app

# Asılılıqlar (cache üçün əvvəl)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Layihə faylları
COPY . .

# Qovluqları yarat
RUN mkdir -p /app/memory/backups /app/logs /app/notes

# Environment
ENV PYTHONIOENCODING=utf-8 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LOOP_INTERVAL_SECONDS=300

# Expose dashboard port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8080/ping || exit 1

# Start command — auto_restart.py bütün xətalardan qoruyur
CMD ["python", "auto_restart.py", "--max-restarts=999", "--cooldown=10"]
