"""
health_monitor.py — Sistem sağlamlığı monitorinqi.
- Uptime tracking
- Stuck detection (5 dəq-dən çox cavab yoxdursa)
- Disk/memory yoxlaması
- Son dövrə vaxtı
"""
from __future__ import annotations

import os
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path

import psutil

import config
from memory import store


START_TIME = time.time()
LAST_TICK_FILE = config.MEMORY_DB.parent / ".last_tick"


def uptime_seconds() -> float:
    """Sistem nə qədər işləyir (saniyə)."""
    return time.time() - START_TIME


def uptime_str() -> str:
    """Uptime-i insan oxuya bilən formatda."""
    secs = int(uptime_seconds())
    days = secs // 86400
    hours = (secs % 86400) // 3600
    mins = (secs % 3600) // 60
    sec = secs % 60
    if days > 0:
        return f"{days}g {hours}s {mins}d"
    if hours > 0:
        return f"{hours}s {mins}d {sec}san"
    return f"{mins}d {sec}san"


def last_tick_age_seconds() -> float | None:
    """Son beyin dövrəsi neçə saniyə əvvəl?"""
    if not LAST_TICK_FILE.exists():
        return None
    try:
        mtime = LAST_TICK_FILE.stat().st_mtime
        return time.time() - mtime
    except Exception:
        return None


def mark_tick() -> None:
    """Son dövrə vaxtını qeyd et."""
    try:
        LAST_TICK_FILE.parent.mkdir(parents=True, exist_ok=True)
        LAST_TICK_FILE.write_text(datetime.now().isoformat(timespec="seconds"), encoding="utf-8")
    except Exception:
        pass


def is_stuck(max_idle_seconds: int = 600) -> bool:
    """Beyin çoxdan cavab vermirsə, stuck sayılır (10 dəq)."""
    age = last_tick_age_seconds()
    # Heç bir tick yoxdursa, amma sistem 5+ dəq işləyirsə → stuck
    if age is None:
        return uptime_seconds() > 300
    return age > max_idle_seconds


def disk_usage() -> dict:
    """Disk istifadəsi."""
    try:
        usage = psutil.disk_usage(str(config.ROOT))
        return {
            "total_gb": usage.total / (1024**3),
            "used_gb": usage.used / (1024**3),
            "free_gb": usage.free / (1024**3),
            "percent": usage.percent,
        }
    except Exception as e:
        return {"error": str(e)}


def memory_usage() -> dict:
        """RAM istifadəsi."""
        try:
            mem = psutil.virtual_memory()
            return {
                "total_gb": mem.total / (1024**3),
                "used_gb": mem.used / (1024**3),
                "percent": mem.percent,
            }
        except Exception as e:
            return {"error": str(e)}


def database_health() -> dict:
    """SQLite baza sağlamlığı."""
    try:
        if not config.MEMORY_DB.exists():
            return {
                "ok": False,
                "thoughts": 0,
                "size_mb": 0.0,
                "path": str(config.MEMORY_DB),
                "error": "DB faylı mövcud deyil",
            }
        with sqlite3.connect(config.MEMORY_DB) as c:
            # Connection.execute() cursor qaytarır, fetchone() cursor metodudur
            integrity = c.execute("PRAGMA integrity_check").fetchone()
            try:
                count = c.execute("SELECT COUNT(*) FROM thoughts").fetchone()[0]
            except sqlite3.OperationalError:
                count = 0
            integrity_val = integrity[0] if integrity else None
            count_val = int(count) if count is not None else 0
        size_mb = config.MEMORY_DB.stat().st_size / (1024**2)
        return {
            "ok": bool(integrity_val) and integrity_val == "ok",
            "thoughts": count_val,
            "size_mb": round(size_mb, 2),
            "path": str(config.MEMORY_DB),
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "thoughts": 0, "size_mb": 0.0, "path": str(config.MEMORY_DB)}


def health_report() -> dict:
    """Tam sağlamlıq hesabatı."""
    return {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "uptime_seconds": int(uptime_seconds()),
        "uptime_str": uptime_str(),
        "active_brain": config.active_brain_name(),
        "available_brains": config.available_brains(),
        "last_tick_age_s": last_tick_age_seconds(),
        "is_stuck": is_stuck(),
        "disk": disk_usage(),
        "memory": memory_usage(),
        "database": database_health(),
        "stats": store.stats(),
    }


if __name__ == "__main__":
    import json
    print(json.dumps(health_report(), ensure_ascii=False, indent=2))
