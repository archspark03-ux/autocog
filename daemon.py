"""
daemon.py — 7/24 işləyən scheduler.
İki rejimdə işləyir:
  1) Foreground loop (--once, --n N)  — test üçün
  2) Background scheduler (default)   — APScheduler ilə 7/24

İstifadə:
  python daemon.py                 # 7/24 işlə
  python daemon.py --once          # bir dövrə
  python daemon.py --n 3           # 3 dövrə
  python daemon.py --interval 60   # hər 60 saniyə
  python daemon.py --research      # hər dövrədə research et
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
import signal
import sys
import time
from datetime import datetime, timedelta

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

import config
from agent import Agent
from memory import store
from tools import logger
import backup
import log_rotation


_running = True


def _stop(signum, frame):
    global _running
    logger.warn("siqnal alındı, dayanır…")
    _running = False
    sys.exit(0)


def _print_intro():
    logger.banner("AVTONOMCOGITATE — 7/24 DÜŞÜNƏN BEYİN")
    print(f"  Əsas beyin   : {config.PRIMARY_BRAIN}")
    print(f"  Fallback     : {config.FALLBACK_BRAIN}")
    print(f"  Aktiv        : {config.active_brain_name()}")
    print(f"  Loop interval: {config.LOOP_INTERVAL_SECONDS} saniyə")
    print(f"  Araşdırma    : {', '.join(__import__('research.searcher', fromlist=['Researcher']).Researcher().available_sources())}")
    print(f"  Yaddaş       : {config.MEMORY_DB}")
    print(f"  Qeydlər      : {config.NOTES_DIR}")
    print(f"  Loglar       : {config.LOGS_DIR}")
    print()
    print(f"  Məqsəd: {config.USER_GOAL[:120]}{'…' if len(config.USER_GOAL) > 120 else ''}")
    print()


def tick(force_research: bool = False):
    """Bir dövrə icra et (scheduler bunu çağırır)."""
    try:
        a = Agent()
        a.run_once(force_research=force_research)
    except Exception as e:
        logger.error(f"tick xətası: {e}")
        import traceback
        traceback.print_exc()


def backup_job():
    """Hər saat — SQLite backup et, köhnələri təmizlə."""
    try:
        logger.info("saatlıq backup başladır")
        backup.create_backup()
        backup.cleanup_old_backups()
    except Exception as e:
        logger.error(f"backup job xətası: {e}")


def log_rotation_job():
    """Hər gün — log-ları rotasiya et (sıxışdır/köhnələri sil)."""
    try:
        logger.info("günlük log rotasiyası başladır")
        result = log_rotation.rotate_logs(max_age_days=30, compress_age_days=7)
        logger.info(f"log rotasiya: sıxışdırıldı={result['compressed']}, silindi={result['deleted']}")
    except Exception as e:
        logger.error(f"log rotation xətası: {e}")


def run_forever(interval: int, force_research: bool):
    """APScheduler ilə 7/24."""
    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    sched = BlockingScheduler(timezone="UTC")
    sched.add_job(
        tick,
        trigger=IntervalTrigger(seconds=interval),
        args=[force_research],
        id="brain_tick",
        name="Avtonom beyin dövrəsi",
        max_instances=1,
        coalesce=True,
    )
    # Hər saat — SQLite backup (30s sonra, beyin işləməsinin üst-üstə düşməsin)
    sched.add_job(
        backup_job,
        trigger=IntervalTrigger(hours=1),
        id="backup_job",
        name="SQLite backup (saatlıq)",
        max_instances=1,
        coalesce=True,
        next_run_time=datetime.now() + timedelta(seconds=30),
    )
    # Hər gün — log rotasiya
    sched.add_job(
        log_rotation_job,
        trigger=IntervalTrigger(days=1),
        id="log_rotation_job",
        name="Log rotasiya (günlük)",
        max_instances=1,
        coalesce=True,
    )
    logger.success(f"scheduler başladı: hər {interval} saniyə beyin + hər saat backup + hər gün log rotasiya")
    logger.info("Ctrl+C ilə dayandıra bilərsən")
    try:
        sched.start()
    except (KeyboardInterrupt, SystemExit):
        logger.warn("scheduler dayandırıldı")


def run_n(n: int, force_research: bool):
    """N dəfə dövrə et (test)."""
    for i in range(n):
        if not _running:
            break
        if i > 0:
            logger.info(f"növbəti dövrə üçün gözləyirəm {config.LOOP_INTERVAL_SECONDS}s…")
            time.sleep(config.LOOP_INTERVAL_SECONDS)
        tick(force_research)
    logger.success("bütün dövrələr tamamlandı")
    s = store.stats()
    print()
    print("📊  ÜMUMİ STATİSTİKA")
    for k, v in s.items():
        print(f"  {k:18s}: {v}")


def main():
    p = argparse.ArgumentParser(description="Avtonom beyin daemon-u")
    p.add_argument("--once", action="store_true", help="bir dövrə icra et və çıx")
    p.add_argument("--n", type=int, default=0, help="N dəfə dövrə et")
    p.add_argument("--interval", type=int, default=config.LOOP_INTERVAL_SECONDS,
                   help="loop intervalı (saniyə)")
    p.add_argument("--research", action="store_true",
                   help="hər dövrədə dərin araşdırma da et")
    p.add_argument("--stats", action="store_true", help="statistikanı göstər və çıx")
    p.add_argument("--config-check", action="store_true", help="konfiqurasiyanı yoxla və çıx")
    args = p.parse_args()

    store.init_db()
    _print_intro()

    if args.config_check:
        return

    if args.stats:
        s = store.stats()
        print("📊  YADDAŞ STATİSTİKASI")
        for k, v in s.items():
            print(f"  {k:18s}: {v}")
        tasks = store.list_tasks(status="open", limit=20)
        if tasks:
            print(f"\n📋  AÇIQ TAPŞIRIQ ({len(tasks)}):")
            for t in tasks:
                print(f"  [P{t['priority']}] #{t['id']} {t['title']}")
        notes = store.recent_research(limit=5)
        if notes:
            print(f"\n🔍  SON ARAŞDIRMALAR:")
            for n in notes:
                print(f"  · #{n['cycle']} \"{n['query']}\" → {n['source']} ({len(n.get('results', []))} nəticə)")
        return

    if args.once:
        tick(force_research=args.research)
        return

    if args.n > 0:
        run_n(args.n, args.research)
        return

    # Default: 7/24
    run_forever(args.interval, args.research)


if __name__ == "__main__":
    main()
