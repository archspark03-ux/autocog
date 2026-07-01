"""
auto_restart.py — 7/24 davamlılıq üçün AUTO-RESTART mexanizmi.
Əgər daemon dayanırsa (xəta, CRASH, internet kəsilməsi, vs.),
avtomatik olaraq yenidən başladır.

İstifadə:
  python auto_restart.py           # daemon.py avtomatik izləyir
  python auto_restart.py --nodaemon  # cari proses kimi
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import argparse
import subprocess
import time
from datetime import datetime
from pathlib import Path

import config
from tools import logger


LOG_FILE = config.LOGS_DIR / "auto_restart.log"


def log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def run_with_restart(cmd: list[str], max_restarts: int = 50, cooldown: int = 10):
    """Prosesi işlət, dayandırılsa yenidən başlat (exponential backoff ilə)."""
    restart_count = 0
    last_restart = None
    log(f"▶ avto-restart başladı: {' '.join(cmd)}")
    log(f"  max_restarts={max_restarts}, cooldown={cooldown}s, exponential backoff")

    # Qısa müddətdə çoxlu crash varsa, dayan (real bug maskelenməsin)
    crash_window = []  # (ts, error)
    MAX_CRASHES_PER_HOUR = 10

    while restart_count < max_restarts:
        try:
            log(f"▶ proses başladılır (cəhd #{restart_count + 1})")
            proc = subprocess.Popen(
                cmd,
                stdout=open(config.LOGS_DIR / "daemon_stdout.log", "a", encoding="utf-8"),
                stderr=subprocess.STDOUT,
                cwd=os.path.dirname(os.path.abspath(__file__)),
            )
            return_code = proc.wait()
            restart_count += 1
            now = datetime.now()
            last_restart = now

            # Crash window — son 1 saat
            crash_window.append(now)
            crash_window = [t for t in crash_window if (now - t).total_seconds() < 3600]
            if len(crash_window) > MAX_CRASHES_PER_HOUR:
                log(f"⏹ {MAX_CRASHES_PER_HOUR}+ crash 1 saatda — real bug var, dayanırıq")
                log("  Log yoxla: d:\code\avtonomcogitate\logs\daemon_stdout.log")
                return

            # Exponential backoff (10s, 20s, 40s, max 5 dəq)
            wait_s = min(cooldown * (2 ** (restart_count - 1)), 300)
            log(f"⚠ proses dayandı (return_code={return_code}), "
                f"restart #{restart_count}/{max_restarts} in {wait_s}s")
            time.sleep(wait_s)
        except KeyboardInterrupt:
            log("⏹ istifadəçi dayandırdı (Ctrl+C)")
            return
        except Exception as e:
            log(f"✖ restart xətası: {e}")
            restart_count += 1
            time.sleep(cooldown * 2)

    log(f"⏹ max_restarts ({max_restarts}) çatdı, dayanır")


def main():
    p = argparse.ArgumentParser(description="Avto-restart wrapper")
    p.add_argument("--nodaemon", action="store_true",
                   help="cari proses kimi işlət (test üçün)")
    p.add_argument("--max-restarts", type=int, default=50)
    p.add_argument("--cooldown", type=int, default=10)
    args = p.parse_args()

    cmd = [sys.executable, "daemon.py"]
    run_with_restart(cmd, max_restarts=args.max_restarts, cooldown=args.cooldown)


if __name__ == "__main__":
    main()
