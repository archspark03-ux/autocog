"""
log_rotation.py — Köhnə log-ları sıxışdır və sil.
- Hər gün ən son log saxlanır
- 7 gündən köhnələr sıxışdırılır (gzip)
- 30 gündən köhnələr silinir
- Disk dolmasının qarşısını alır
"""
from __future__ import annotations

import gzip
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path

import config


def rotate_logs(max_age_days: int = 30, compress_age_days: int = 7) -> dict:
    """Log-ları rotasiya et.

    Args:
        max_age_days: Bu gündən köhnə log-lar silinir.
        compress_age_days: Bu gündən köhnə log-lar gzip ilə sıxışdırılır.

    Returns:
        Rotasiya statistikası.
    """
    logs_dir = config.LOGS_DIR
    if not logs_dir.exists():
        return {"compressed": 0, "deleted": 0}

    now = datetime.now()
    compressed = 0
    deleted = 0

    # Bütün .log fayllarını tap (gzip olunmamış)
    for log_file in logs_dir.glob("*.log"):
        try:
            mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
            age_days = (now - mtime).days

            # Çox köhnədirsə — sil
            if age_days > max_age_days:
                log_file.unlink()
                deleted += 1
                continue

            # Sıxışdırma vaxtıdırsa — gzip
            if age_days > compress_age_days:
                gz_path = log_file.with_suffix(".log.gz")
                with open(log_file, "rb") as f_in:
                    with gzip.open(gz_path, "wb") as f_out:
                        shutil.copyfileobj(f_in, f_out)
                log_file.unlink()
                compressed += 1
        except Exception:
            pass

    return {"compressed": compressed, "deleted": deleted}


def log_dir_size_mb() -> float:
    """Log qovluğunun ümumi ölçüsü (MB)."""
    logs_dir = config.LOGS_DIR
    if not logs_dir.exists():
        return 0.0
    total = 0
    for f in logs_dir.rglob("*"):
        if f.is_file():
            total += f.stat().st_size
    return total / (1024 * 1024)


if __name__ == "__main__":
    result = rotate_logs()
    print(f"Sıxışdırıldı: {result['compressed']}, silindi: {result['deleted']}")
    print(f"Log qovluğu ölçüsü: {log_dir_size_mb():.2f} MB")
