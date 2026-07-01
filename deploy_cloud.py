"""
deploy_cloud.py — Cloud deployment üçün konfiqurasiya.
Hədəflər:
  - Render.com (pulsuz tier)
  - Railway.app (pulsuz tier)
  - Hetzner VPS ($4/ay)
  - DigitalOcean droplet ($6/ay)
  - Fly.io (pulsuz tier)

Avtonom beyin 7/24 işləyəcək, heç bir lokal kompüter istəmir.
"""
import sys
import os
import textwrap
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


DEPLOY_INSTRUCTIONS = """
# ════════════════════════════════════════════════════════════
# 7/24 CLOUD DEPLOYMENT — 4 ADDIM
# ════════════════════════════════════════════════════════════

## VARIANT 1: Render.com (PULSUZ, ən asan)
─────────────────────────────────────────
1. https://render.com-da GitHub ilə qeydiyyatdan keç
2. "New Web Service" → GitHub repo-nu bağla
3. Build Command: pip install -r requirements.txt
4. Start Command: python auto_restart.py
5. .env faylını Environment bölməsinə yapışdır
6. Pulsuz tier ayda 750 saat = 24/7 işləyir (1 instance üçün kifayətdir)

## VARIANT 2: Hetzner VPS (€3.79/ay, ən ucuz, Avropa serveri)
─────────────────────────────────────────
1. https://hetzner.com/cloud — qeydiyyat (kart lazımdır, amma 1 ay pulsuz)
2. CPX11 seç: 2 vCPU, 2GB RAM, 40GB SSD — €3.79/ay
3. Ubuntu 22.04 quraşdır
4. SSH ilə qoşul:
   ssh root@IP_ADRES
5. Python quraşdır:
   apt update && apt install python3.12 python3-pip -y
6. Repo-nu clone et, faylları köçür
7. systemd servisi yarat (aşağıya bax)

## VARIANT 3: Raspberry Pi (bir dəfəlik $35-50)
─────────────────────────────────────────
- Evdə 7/24 işləyir, enerji sərfiyyatı ~5W
- İnternet kəsilsə avtomatik dayanır
- Auto-restart skripti lazımdır (auto_restart.py)

## VARIANT 4: Fly.io (PULSUZ tier)
─────────────────────────────────────────
- 3 paylaşılan instance (256MB RAM) pulsuz
- Hər ay 160GB trafik
- Global edge network (sürətli)
"""


SYSTEMD_SERVICE = """
# /etc/systemd/system/avtonom-cogitate.service
# Hetzner/DigitalOcean VPS üçün systemd servisi

[Unit]
Description=AvtonomCogitate - 7/24 düşünən beyin
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/avtonomcogitate
ExecStart=/usr/bin/python3 auto_restart.py --max-restarts 999 --cooldown 10
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
Environment="PYTHONIOENCODING=utf-8"

# Auto-restart on failure
StartLimitIntervalSec=0
StartLimitBurst=0

[Install]
WantedBy=multi-user.target
"""


DOCKERFILE = """
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONIOENCODING=utf-8
ENV PYTHONUNBUFFERED=1

# Expose dashboard port
EXPOSE 8080

# Start auto-restart wrapper (which starts daemon.py)
CMD ["python", "auto_restart.py", "--max-restarts=999", "--cooldown=10"]
"""


DOCKER_COMPOSE = """
version: "3.8"
services:
  brain:
    build: .
    container_name: avtonom-cogitate
    env_file:
      - .env
    ports:
      - "8080:8080"
    volumes:
      - ./memory:/app/memory
      - ./notes:/app/notes
      - ./logs:/app/logs
    restart: always
    healthcheck:
      test: ["CMD", "python", "-c", "import httpx; httpx.get('http://localhost:8080/api/health', timeout=5)"]
      interval: 60s
      timeout: 10s
      retries: 3
"""


def main():
    print(DEPLOY_INSTRUCTIONS)
    print()
    print(textwrap.dedent(SYSTEMD_SERVICE))
    print()
    print("# ─────── Dockerfile ───────")
    print(textwrap.dedent(DOCKERFILE))
    print("# ─────── docker-compose.yml ───────")
    print(textwrap.dedent(DOCKER_COMPOSE))
    print()
    print("# ════════════════════════════════════════════════════════════")
    print("#  CLOUD DEPLOYMENT ÜÇÜN HAZIR KONFİQURASİYA")
    print("# ════════════════════════════════════════════════════════════")


if __name__ == "__main__":
    main()
