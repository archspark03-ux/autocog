"""
backup.py — SQLite database avtomatik backup.
Hər saat yeni backup, 7 gün saxlanır, sonra silinir.
"""
from __future__ import annotations

import shutil
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path

import config
from tools import logger


BACKUP_DIR = config.ROOT / "memory" / "backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)
MAX_BACKUP_AGE_DAYS = 7
MAX_BACKUPS = 24 * 7  # 7 günlük saatlıq backup

# Backup zamanı digər yazmaları blokla (atomic backup)
import threading
_backup_lock = threading.Lock()


def create_backup() -> Path:
    """Cari baza faylının backup-ını yarat (thread-safe, atomic)."""
    with _backup_lock:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = BACKUP_DIR / f"brain_{timestamp}.db"
        try:
            # Remote DB üçün lokal backup mümkün deyil — skip
            if config.USE_REMOTE_DB:
                logger.warn("remote DB üçün lokal backup skip olunur "
                            "(Turso özü avtomatik snapshot edir)")
                return None
            if not config.MEMORY_DB.exists():
                logger.warn("DB faylı mövcud deyil, backup skip")
                return None
            # SQLite backup API (atomic, consistent)
            # WAL mode + busy_timeout sayəsində paralel reads işləyir
            with sqlite3.connect(str(config.MEMORY_DB)) as src:
                with sqlite3.connect(str(backup_path)) as dst:
                    src.backup(dst)
            # VACUUM et ki kiçik olsun
            try:
                with sqlite3.connect(str(backup_path)) as c:
                    c.execute("VACUUM")
            except Exception:
                pass
            size_kb = backup_path.stat().st_size / 1024
            logger.info(f"backup yaradıldı: {backup_path.name} ({size_kb:.1f} KB)")
            return backup_path
        except Exception as e:
            logger.error(f"backup xətası: {e}")
            # Yarımçıq faylı sil
            try:
                if backup_path.exists():
                    backup_path.unlink()
            except Exception:
                pass
            return None


def cleanup_old_backups() -> int:
    """7 gündən köhnə backup-ları sil."""
    cutoff = datetime.now() - timedelta(days=MAX_BACKUP_AGE_DAYS)
    removed = 0
    for f in sorted(BACKUP_DIR.glob("brain_*.db")):
        try:
            file_time = datetime.fromtimestamp(f.stat().st_mtime)
            if file_time < cutoff:
                f.unlink()
                removed += 1
        except Exception:
            pass
    # Çox backup varsa, ən köhnələri də sil
    backups = sorted(BACKUP_DIR.glob("brain_*.db"), key=lambda p: p.stat().st_mtime)
    if len(backups) > MAX_BACKUPS:
        for f in backups[:-MAX_BACKUPS]:
            try:
                f.unlink()
                removed += 1
            except Exception:
                pass
    if removed:
        logger.info(f"köhnə backup silindi: {removed} fayl")
    return removed


def list_backups() -> list[dict]:
    """Mövcud backup-ları qaytar."""
    out = []
    for f in sorted(BACKUP_DIR.glob("brain_*.db"), reverse=True):
        stat = f.stat()
        out.append({
            "name": f.name,
            "size_kb": stat.st_size / 1024,
            "created": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        })
    return out


def run_backup_loop(interval_seconds: int = 3600):
    """Hər N saniyədən bir backup et, köhnələri təmizlə."""
    logger.info(f"backup loop başladı: hər {interval_seconds} saniyə")
    while True:
        try:
            create_backup()
            cleanup_old_backups()
        except Exception as e:
            logger.error(f"backup loop xətası: {e}")
        time.sleep(interval_seconds)


if __name__ == "__main__":
    print("Backup modulu test")
    b = create_backup()
    if b:
        print(f"OK: {b}")
    cleanup_old_backups()
    print(f"Mövcud backup: {len(list_backups())}")
