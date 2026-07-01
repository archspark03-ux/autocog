"""
start_all.py — Production entry point (Render.com üçün).
Həm dashboard, həm də daemon-u eyni prosesdə işə salır.
Dashboard background thread-də (port 8080), daemon əsas thread-də (APScheduler).

İstifadə:
  python start_all.py

Bu fayl Render.com, Docker, VPS və s. üçün entry point-dir.
Lokal inkişaf üçün hələ də `python daemon.py` və `python -m web.dashboard`
ayrı-ayrı işlədilə bilər.
"""
from __future__ import annotations

import sys
import os
import time
import signal
import threading
import subprocess
from pathlib import Path

# UTF-8
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from tools import logger


# ════════════════════════════════════════════════════════════
# Dashboard (background thread, port 8080)
# ════════════════════════════════════════════════════════════
def start_dashboard_subprocess():
    """Dashboard-u ayrı subprocess kimi başlat (uvicorn ilə)."""
    log_path = config.LOGS_DIR / "dashboard.log"
    config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_f = open(log_path, "a", encoding="utf-8")
    cmd = [
        sys.executable, "-m", "uvicorn",
        "web.dashboard:app",
        "--host", "0.0.0.0",
        "--port", "8080",
        "--log-level", "info",
    ]
    logger.info(f"▶ dashboard başladılır: {' '.join(cmd)}")
    return subprocess.Popen(
        cmd,
        stdout=log_f,
        stderr=subprocess.STDOUT,
        cwd=os.path.dirname(os.path.abspath(__file__)),
    )


def wait_for_ping(max_wait: int = 30) -> bool:
    """Dashboard /ping endpoint-i hazır olana qədər gözlə."""
    import urllib.request
    deadline = time.time() + max_wait
    while time.time() < deadline:
        try:
            r = urllib.request.urlopen("http://127.0.0.1:8080/ping", timeout=2)
            if r.status == 200:
                logger.success("✓ dashboard /ping hazırdır")
                return True
        except Exception:
            time.sleep(1)
    logger.warn("⚠ dashboard /ping 30s-də hazır olmadı, amma davam edirik")
    return False


# ════════════════════════════════════════════════════════════
# Daemon (main thread, APScheduler)
# ════════════════════════════════════════════════════════════
def run_daemon_forever():
    """Daemon-u əsas thread-də işə sal (7/24 loop)."""
    from daemon import run_forever
    interval = config.LOOP_INTERVAL_SECONDS
    logger.info(f"▶ daemon başladılır (interval={interval}s)")
    run_forever(interval=interval, force_research=False)


# ════════════════════════════════════════════════════════════
# Main — orchestration
# ════════════════════════════════════════════════════════════
def main():
    logger.banner("AVTONOMCOGITATE — 7/24 (dashboard + daemon)")
    print(f"  Backend : {'postgres' if config.USE_REMOTE_DB else 'local-sqlite'}")
    print(f"  Brain   : {config.active_brain_name()}")
    print(f"  Interval: {config.LOOP_INTERVAL_SECONDS}s")
    print()

    # 1) Database init
    from memory import store
    store.init_db()
    logger.success("✓ DB sxemi hazırdır")

    # 2) Dashboard subprocess
    dash_proc = start_dashboard_subprocess()
    time.sleep(2)
    wait_for_ping(max_wait=30)

    # 3) Daemon (əsas thread) — dashboard onu öldürməsin
    def _stop(signum, frame):
        logger.warn(f"siqnal {signum} alındı, dashboard və daemon dayanır...")
        try:
            dash_proc.terminate()
        except Exception:
            pass
        sys.exit(0)

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    try:
        run_daemon_forever()
    finally:
        try:
            dash_proc.terminate()
        except Exception:
            pass


if __name__ == "__main__":
    main()
