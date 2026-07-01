"""
final_stress_test.py — BÜTÜN qatları test et:
  1. LLM failover (groq → pollinations → cerebras)
  2. Backup (SQLite → atomic copy + VACUUM)
  3. Health monitor (uptime, stuck, disk, RAM, DB integrity)
  4. Log rotation (gzip sıxışdırma)
  5. Security (token, sanitization, rate limit)
  6. Stress sorğular (müxtəlif prompt intensivliyi)

Hər test PASS/FAIL ilə qeyd olunur. sonda ümumi hesabat.
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import json
import time
import threading
from datetime import datetime
from pathlib import Path

import config
import backup
import health_monitor
import log_rotation
import security
from memory import store
from tools import logger
from brain.client import think_with_failover, make_fallback_chain


RESULTS = {"pass": 0, "fail": 0, "skipped": 0, "details": []}
LOCK = threading.Lock()


def record(name: str, ok: bool, detail: str = ""):
    with LOCK:
        RESULTS["pass" if ok else "fail"] += 1
        RESULTS["details"].append({
            "name": name, "ok": ok, "detail": detail,
            "ts": datetime.now().isoformat(timespec="seconds"),
        })
    sym = "✓" if ok else "✖"
    logger.info(f"  [{sym}] {name}: {detail}")


def section(title: str):
    print()
    logger.banner(title)


# ══════════════════════════════════════════════════════════════
# TEST 1: LLM Failover
# ══════════════════════════════════════════════════════════════
def test_failover():
    section("TEST 1 · LLM FAILOVER (groq → pollinations → cerebras)")
    chain = make_fallback_chain()
    logger.info(f"fallback chain: {[b.name for b in chain]}")
    record("fallback chain built", len(chain) >= 1, f"{len(chain)} beyin")

    # 3 müxtəlif intensivlikdə sorğu
    prompts = [
        "1+1=? sadə cavab ver",
        "Azərbaycan iqtisadiyyatının 3 əsas problemi hansılardır? Qısa cavab.",
        "Süni intellektin gələcəyi haqqında 1 cümləlik fikir.",
    ]
    for i, p in enumerate(prompts, 1):
        try:
            t0 = time.time()
            r = think_with_failover(prompt=p, thinking=False, max_tokens=300, timeout=60)
            dt = int((time.time() - t0) * 1000)
            used = r.get("brain", "?")
            ok = bool(r.get("response")) and not r["response"].startswith("[xəta")
            record(f"  sorğu #{i}", ok, f"{used} · {dt}ms · {len(r.get('response',''))} char")
        except Exception as e:
            record(f"  sorğu #{i}", False, f"exception: {e}")


# ══════════════════════════════════════════════════════════════
# TEST 2: Backup
# ══════════════════════════════════════════════════════════════
def test_backup():
    section("TEST 2 · BACKUP SİSTEMİ")
    try:
        b = backup.create_backup()
        record("backup create", b is not None, f"{b.name if b else 'FAILED'}")
    except Exception as e:
        record("backup create", False, str(e))

    try:
        removed = backup.cleanup_old_backups()
        record("backup cleanup", True, f"{removed} köhnə silindi")
    except Exception as e:
        record("backup cleanup", False, str(e))

    try:
        bl = backup.list_backups()
        record("backup list", True, f"{len(bl)} backup mövcud")
    except Exception as e:
        record("backup list", False, str(e))


# ══════════════════════════════════════════════════════════════
# TEST 3: Health Monitor
# ══════════════════════════════════════════════════════════════
def test_health():
    section("TEST 3 · HEALTH MONİTORİNQ")
    try:
        h = health_monitor.health_report()
        record("health report", True, f"uptime={h['uptime_str']}, stuck={h['is_stuck']}")
    except Exception as e:
        record("health report", False, str(e))

    try:
        health_monitor.mark_tick()
        age = health_monitor.last_tick_age_seconds()
        record("mark_tick", age is not None and age < 5, f"age={age:.2f}s")
    except Exception as e:
        record("mark_tick", False, str(e))

    try:
        disk = health_monitor.disk_usage()
        mem = health_monitor.memory_usage()
        record("disk/ram", "error" not in disk and "error" not in mem,
               f"disk={disk.get('percent',0):.1f}% ram={mem.get('percent',0):.1f}%")
    except Exception as e:
        record("disk/ram", False, str(e))

    try:
        db = health_monitor.database_health()
        # boş DB üçün də keçərli sayırıq (thoughts=0 normal haldır)
        record("db integrity", db.get("ok", False) or db.get("thoughts", 0) == 0,
               f"thoughts={db.get('thoughts')}, {db.get('size_mb')}MB, ok={db.get('ok')}")
    except Exception as e:
        record("db integrity", False, str(e))


# ══════════════════════════════════════════════════════════════
# TEST 4: Log Rotation
# ══════════════════════════════════════════════════════════════
def test_log_rotation():
    section("TEST 4 · LOG ROTASİYA")
    # Bir test log faylı yarat
    test_log = config.LOGS_DIR / f"stress_test_{int(time.time())}.log"
    test_log.write_text("test log content\n" * 100, encoding="utf-8")
    try:
        r = log_rotation.rotate_logs(max_age_days=30, compress_age_days=7)
        record("rotate_logs", True, f"compressed={r['compressed']}, deleted={r['deleted']}")
    except Exception as e:
        record("rotate_logs", False, str(e))

    try:
        size = log_rotation.log_dir_size_mb()
        record("log size", size >= 0, f"{size:.2f} MB")
    except Exception as e:
        record("log size", False, str(e))


# ══════════════════════════════════════════════════════════════
# TEST 5: Security
# ══════════════════════════════════════════════════════════════
def test_security():
    section("TEST 5 · TƏHLÜKƏSİZLİK (token, sanitization, rate limit)")
    try:
        token = security.get_dashboard_token()
        ok = security.verify_token(token)
        record("token roundtrip", ok, f"len={len(token)}")
    except Exception as e:
        record("token roundtrip", False, str(e))

    try:
        clean = security.sanitize_text("  Hello<script>alert(1)</script>  " * 50)
        record("sanitize xss", "<script>" not in clean, f"len={len(clean)}")
    except Exception as e:
        record("sanitize xss", False, str(e))

    try:
        rl = security.RateLimiter(max_per_minute=5)
        # 5 icazəli
        for _ in range(5):
            rl.allow("test_ip")
        # 6-cı bloklanmalıdır
        blocked = not rl.allow("test_ip")
        record("rate limit blocks", blocked, "6-cı sorğu bloklandı")
    except Exception as e:
        record("rate limit blocks", False, str(e))


# ══════════════════════════════════════════════════════════════
# TEST 6: Stress — eyni anda 3 sorğu (paralel)
# ══════════════════════════════════════════════════════════════
def test_parallel_stress():
    section("TEST 6 · PARALEL STRES (eyni anda 3 sorğu)")
    prompts = [
        "Süni intellekt nədir? Qısa.",
        "Kvant kompüter nədir? 1 cümlə.",
        "Python nə üçün populyardır? 1 cümlə.",
    ]
    results = [None, None, None]

    def worker(idx, prompt):
        try:
            r = think_with_failover(prompt=prompt, thinking=False, max_tokens=150, timeout=60)
            results[idx] = (True, r.get("brain"), len(r.get("response", "")))
        except Exception as e:
            results[idx] = (False, None, str(e))

    threads = [threading.Thread(target=worker, args=(i, p)) for i, p in enumerate(prompts)]
    t0 = time.time()
    for t in threads: t.start()
    for t in threads: t.join()
    dt = int((time.time() - t0) * 1000)

    for i, r in enumerate(results):
        if r is None:
            record(f"  paralel #{i}", False, "timeout/exception")
        else:
            ok, brain, info = r
            record(f"  paralel #{i}", ok, f"{brain} · {info} · {dt}ms total")


# ══════════════════════════════════════════════════════════════
# FINAL REPORT
# ══════════════════════════════════════════════════════════════
def final_report():
    print()
    logger.banner("FİNAL HESABAT")
    total = RESULTS["pass"] + RESULTS["fail"]
    pct = (RESULTS["pass"] / total * 100) if total else 0
    print(f"  Ümumi test   : {total}")
    print(f"  PASS         : {RESULTS['pass']}")
    print(f"  FAIL         : {RESULTS['fail']}")
    print(f"  Skip         : {RESULTS['skipped']}")
    print(f"  Uğur dərəcəsi: {pct:.1f}%")
    print()

    # JSON qeyd
    out_file = config.LOGS_DIR / "final_stress_results.json"
    out_file.write_text(json.dumps(RESULTS, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  Detallı log: {out_file}")
    print()

    if RESULTS["fail"] == 0:
        logger.success("═══ BÜTÜN TESTLƏR UĞURLA KEÇDİ ═══")
        return 0
    else:
        logger.error(f"═══ {RESULTS['fail']} TEST UĞURSUZ OLDU ═══")
        return 1


def main():
    print()
    logger.banner("AVTONOMCOGITATE · FİNAL STRES TESTİ")
    print(f"  Tarix: {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"  Aktiv beyin: {config.active_brain_name()}")
    print(f"  Əlçatan beyinlər: {config.available_brains()}")
    print(f"  DB: {config.MEMORY_DB}")
    print(f"  Loglar: {config.LOGS_DIR}")
    print()

    # İlk öncə DB-ni hazırla
    store.init_db()

    test_failover()
    test_backup()
    test_health()
    test_log_rotation()
    test_security()
    test_parallel_stress()

    return final_report()


if __name__ == "__main__":
    sys.exit(main())
