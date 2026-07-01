"""
memory/store.py — Yaddaş qatı.
Dual backend: lokal SQLite (default) və ya remote PostgreSQL/Neon (7/24).
SQLite AUTOINCREMENT → PostgreSQL SERIAL avtomatik translate olunur.
? placeholder-i sqlite3 üçün, psycopg2 üçün %s — bu da avtomatikdir.

Cədvəllər: thoughts, research, notes, tasks, metrics, schema_version
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

import config

_lock = threading.RLock()

# Backend
_backend_kind = "local"   # "local" | "postgres"
_backend = None           # sqlite3.Connection | psycopg2 connection pool


# ════════════════════════════════════════════════════════════
# Backend init
# ════════════════════════════════════════════════════════════
def _init_backend():
    global _backend_kind, _backend
    if _backend is not None:
        return
    pg_dsn = os.getenv("DATABASE_URL", "").strip()
    if pg_dsn:
        # Remote PostgreSQL (Neon, Supabase, Render, istənilən)
        import psycopg2
        from psycopg2.extras import RealDictCursor, execute_batch
        # Neon üçün SSL tələb olunur, əgər URL-də yoxdursa əlavə et
        if "sslmode" not in pg_dsn:
            sep = "&" if "?" in pg_dsn else "?"
            pg_dsn = f"{pg_dsn}{sep}sslmode=require"
        _backend = psycopg2.connect(pg_dsn, cursor_factory=RealDictCursor, connect_timeout=10)
        _backend.autocommit = True
        _backend_kind = "postgres"
    else:
        # Lokal SQLite
        config.MEMORY_DB.parent.mkdir(parents=True, exist_ok=True)
        c = sqlite3.connect(
            str(config.MEMORY_DB),
            timeout=30,
            check_same_thread=False,
            isolation_level=None,  # autocommit
        )
        c.row_factory = sqlite3.Row
        try:
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("PRAGMA synchronous=NORMAL")
            c.execute("PRAGMA foreign_keys=ON")
            c.execute("PRAGMA busy_timeout=30000")
        except Exception:
            pass
        _backend = c
        _backend_kind = "local"


def _is_pg() -> bool:
    _init_backend()
    return _backend_kind == "postgres"


# ════════════════════════════════════════════════════════════
# SQL translation (SQLite → PostgreSQL)
# ════════════════════════════════════════════════════════════
def _adapt_sql(sql: str) -> str:
    """SQLite SQL-i PostgreSQL-ə çevir:
    - ? → %s
    - INTEGER PRIMARY KEY AUTOINCREMENT → SERIAL PRIMARY KEY
    - INSERT OR REPLACE → INSERT ... ON CONFLICT
    - datetime('now') → CURRENT_TIMESTAMP (artıq istifadə etmirik)
    - INTEGER DEFAULT 0 (boolean) üçün BOOLEAN DEFAULT FALSE (skip — INTEGER işləyir)
    """
    if not _is_pg():
        return sql
    s = sql
    # Placeholder: ? → %s
    s = s.replace("?", "%s")
    # AUTOINCREMENT yalnız CREATE TABLE-də olur
    s = re.sub(
        r"(\w+)\s+INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT",
        r"\1 SERIAL PRIMARY KEY",
        s,
        flags=re.IGNORECASE,
    )
    # INSERT OR REPLACE → INSERT ... ON CONFLICT (id) DO UPDATE SET ...
    # Sadə hallarda: "INSERT OR REPLACE INTO t (a,b,c) VALUES (...)" — bütün sütunlar üçün
    m = re.match(
        r"\s*INSERT\s+OR\s+REPLACE\s+INTO\s+(\w+)\s*\(([^)]+)\)\s*VALUES\s*\(([^)]+)\)\s*$",
        s,
        re.IGNORECASE | re.DOTALL,
    )
    if m:
        table, cols, vals = m.group(1), m.group(2), m.group(3)
        col_list = [c.strip() for c in cols.split(",")]
        s = (
            f"INSERT INTO {table} ({cols}) VALUES ({vals}) "
            f"ON CONFLICT (id) DO UPDATE SET "
            + ", ".join(f"{c}=EXCLUDED.{c}" for c in col_list if c.lower() != "id")
        )
    return s


# ════════════════════════════════════════════════════════════
# SQL icra (backend-agnostic)
# ════════════════════════════════════════════════════════════
def _exec(sql: str, args: tuple = ()) -> int:
    """INSERT/UPDATE/DELETE — affected_rows qaytarır."""
    _init_backend()
    sql2 = _adapt_sql(sql)
    if _is_pg():
        with _backend.cursor() as cur:
            cur.execute(sql2, args)
            return cur.rowcount
    cur = _backend.execute(sql, args)
    return cur.rowcount if cur else 0


def _exec_returning_id(sql: str, args: tuple = ()) -> int:
    """INSERT — id qaytarır (RETURNING hər iki backenddə işləyir)."""
    _init_backend()
    sql2 = _adapt_sql(sql)
    if "RETURNING" not in sql2.upper():
        sql2 = sql2.rstrip().rstrip(";") + " RETURNING id"
    if _is_pg():
        with _backend.cursor() as cur:
            cur.execute(sql2, args)
            r = cur.fetchone()
            return int(r["id"]) if r and r.get("id") is not None else 0
    # SQLite — RETURNING dəstəklənir (3.35+)
    cur = _backend.execute(sql2, args)
    r = cur.fetchone()
    if r is None:
        return 0
    try:
        return int(r["id"])
    except (KeyError, TypeError, IndexError):
        try:
            return int(r[0])
        except Exception:
            return 0


def _query(sql: str, args: tuple = ()) -> list[dict]:
    _init_backend()
    sql2 = _adapt_sql(sql)
    if _is_pg():
        with _backend.cursor() as cur:
            cur.execute(sql2, args)
            rows = cur.fetchall()
            return [dict(r) for r in rows]
    cur = _backend.execute(sql, args)
    if not cur:
        return []
    rows = cur.fetchall()
    out = []
    for r in rows:
        try:
            out.append(dict(r))
        except Exception:
            keys = r.keys() if hasattr(r, "keys") else []
            out.append({k: r[i] if i < len(r) else None for i, k in enumerate(keys)})
    return out


def _queryone(sql: str, args: tuple = ()) -> dict | None:
    _init_backend()
    sql2 = _adapt_sql(sql)
    if _is_pg():
        with _backend.cursor() as cur:
            cur.execute(sql2, args)
            r = cur.fetchone()
            return dict(r) if r else None
    cur = _backend.execute(sql, args)
    if not cur:
        return None
    r = cur.fetchone()
    if not r:
        return None
    try:
        return dict(r)
    except Exception:
        keys = r.keys() if hasattr(r, "keys") else []
        return {k: r[i] if i < len(r) else None for i, k in enumerate(keys)}


def _exec_script(script: str) -> None:
    _init_backend()
    if not _is_pg():
        _backend.executescript(script)
        return
    # PostgreSQL: statement-ləri ; ilə ayır
    for raw in script.split(";"):
        s = raw.strip()
        if not s:
            continue
        sql2 = _adapt_sql(s)
        try:
            with _backend.cursor() as cur:
                cur.execute(sql2)
        except Exception as e:
            msg = str(e).lower()
            if "already exists" in msg or "duplicate" in msg:
                continue
            raise


# ════════════════════════════════════════════════════════════
# Schema — hər iki backend üçün işləyən
# ════════════════════════════════════════════════════════════
SCHEMA_VERSION = 2

_SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    ts TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS thoughts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    cycle INTEGER NOT NULL,
    prompt TEXT NOT NULL,
    thinking TEXT,
    response TEXT,
    brain TEXT,
    tokens_in INTEGER DEFAULT 0,
    tokens_out INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS research (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    cycle INTEGER NOT NULL,
    query TEXT NOT NULL,
    source TEXT,
    results_json TEXT,
    summary TEXT
);

CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    cycle INTEGER NOT NULL,
    title TEXT NOT NULL,
    path TEXT NOT NULL,
    tags TEXT
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    priority INTEGER DEFAULT 0,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    cycle INTEGER NOT NULL,
    duration_ms INTEGER,
    brain TEXT,
    success INTEGER
);

CREATE INDEX IF NOT EXISTS idx_thoughts_cycle ON thoughts(cycle);
CREATE INDEX IF NOT EXISTS idx_research_cycle ON research(cycle);
CREATE INDEX IF NOT EXISTS idx_notes_cycle ON notes(cycle);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_metrics_cycle ON metrics(cycle);
"""


def _current_version() -> int:
    try:
        # Hər iki DB-də sqlite_master uyğun sorğu (PG üçün information_schema)
        if _is_pg():
            r = _queryone(
                "SELECT table_name AS n FROM information_schema.tables "
                "WHERE table_name = 'schema_version' LIMIT 1"
            )
        else:
            r = _queryone(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
            )
        if not r:
            return 0
        r2 = _queryone("SELECT version FROM schema_version LIMIT 1")
        return int(r2["version"]) if r2 else 0
    except Exception:
        return 0


def init_db() -> None:
    with _lock:
        _exec_script(_SCHEMA_DDL)
        cur = _current_version()
        if cur < SCHEMA_VERSION:
            # schema_version cədvəlinin PK'si `version` (id deyil) — INSERT OR REPLACE
            # işləmir. Ona görə UPDATE+INSERT (affected_rows 0 olarsa INSERT) istifadə edirik.
            ts = datetime.now().isoformat(timespec="seconds")
            affected = _exec("UPDATE schema_version SET version=?, ts=?", (SCHEMA_VERSION, ts))
            if affected == 0:
                _exec(
                    "INSERT INTO schema_version (version, ts) VALUES (?, ?)",
                    (SCHEMA_VERSION, ts),
                )


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ════════════════════════════════════════════════════════════
# Düşüncələr
# ════════════════════════════════════════════════════════════
def save_thought(cycle: int, prompt: str, response: str,
                 brain: str, thinking: str = "",
                 tokens_in: int = 0, tokens_out: int = 0) -> int:
    with _lock:
        return _exec_returning_id(
            """INSERT INTO thoughts
               (ts, cycle, prompt, thinking, response, brain, tokens_in, tokens_out)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (now(), cycle, prompt, thinking, response, brain, tokens_in, tokens_out),
        )


def recent_thoughts(limit: int = 5) -> list[dict]:
    return _query("SELECT * FROM thoughts ORDER BY id DESC LIMIT ?", (max(1, limit),))


def get_thought(thought_id: int) -> dict | None:
    return _queryone("SELECT * FROM thoughts WHERE id = ?", (int(thought_id),))


# ════════════════════════════════════════════════════════════
# Araşdırma
# ════════════════════════════════════════════════════════════
def save_research(cycle: int, query: str, source: str,
                  results: list | dict, summary: str = "") -> int:
    payload = json.dumps(results, ensure_ascii=False) if results else "[]"
    with _lock:
        return _exec_returning_id(
            """INSERT INTO research
               (ts, cycle, query, source, results_json, summary)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (now(), cycle, query, source, payload, summary),
        )


def recent_research(limit: int = 5) -> list[dict]:
    rows = _query("SELECT * FROM research ORDER BY id DESC LIMIT ?", (max(1, limit),))
    for r in rows:
        try:
            r["results"] = json.loads(r.pop("results_json") or "[]")
        except Exception:
            r["results"] = []
    return rows


# ════════════════════════════════════════════════════════════
# Qeydlər
# ════════════════════════════════════════════════════════════
def save_note(cycle: int, title: str, path: str, tags: str = "") -> int:
    with _lock:
        return _exec_returning_id(
            "INSERT INTO notes (ts, cycle, title, path, tags) VALUES (?, ?, ?, ?, ?)",
            (now(), cycle, title, path, tags),
        )


def list_notes(limit: int = 20) -> list[dict]:
    return _query("SELECT * FROM notes ORDER BY id DESC LIMIT ?", (max(1, limit),))


def get_note(note_id: int) -> dict | None:
    return _queryone("SELECT * FROM notes WHERE id=?", (int(note_id),))


# ════════════════════════════════════════════════════════════
# Tapşırıqlar
# ════════════════════════════════════════════════════════════
def add_task(title: str, priority: int = 0, notes: str = "") -> int:
    with _lock:
        return _exec_returning_id(
            "INSERT INTO tasks (ts, title, priority, notes) VALUES (?, ?, ?, ?)",
            (now(), title, priority, notes),
        )


def list_tasks(status: str = "open", limit: int = 20) -> list[dict]:
    return _query(
        "SELECT * FROM tasks WHERE status=? ORDER BY priority DESC, id DESC LIMIT ?",
        (status, max(1, limit)),
    )


def update_task(task_id: int, status: str) -> None:
    with _lock:
        _exec("UPDATE tasks SET status=? WHERE id=?", (status, int(task_id)))


# ════════════════════════════════════════════════════════════
# Metrika
# ════════════════════════════════════════════════════════════
def save_metric(cycle: int, duration_ms: int, brain: str, success: bool) -> None:
    with _lock:
        _exec(
            "INSERT INTO metrics (ts, cycle, duration_ms, brain, success) VALUES (?, ?, ?, ?, ?)",
            (now(), cycle, duration_ms, brain, 1 if success else 0),
        )


# ════════════════════════════════════════════════════════════
# Statistika
# ════════════════════════════════════════════════════════════
def stats() -> dict:
    def _cnt(sql, args=()):
        r = _queryone(sql, args)
        return int(r["c"]) if r and r.get("c") is not None else 0
    def _avg(sql, args=()):
        r = _queryone(sql, args)
        return int(r["a"]) if r and r.get("a") is not None else 0
    def _ratio(sql, args=()):
        r = _queryone(sql, args)
        if r and r.get("a") is not None:
            return round(float(r["a"]), 3)
        return 0

    return {
        "cycles": _cnt("SELECT COUNT(DISTINCT cycle) AS c FROM thoughts"),
        "thoughts": _cnt("SELECT COUNT(*) AS c FROM thoughts"),
        "researches": _cnt("SELECT COUNT(*) AS c FROM research"),
        "notes": _cnt("SELECT COUNT(*) AS c FROM notes"),
        "open_tasks": _cnt("SELECT COUNT(*) AS c FROM tasks WHERE status='open'"),
        "avg_duration_ms": _avg("SELECT AVG(duration_ms) AS a FROM metrics WHERE success=1"),
        "success_rate": _ratio(
            "SELECT CAST(SUM(success) AS REAL) / NULLIF(COUNT(*), 0) AS a FROM metrics"
        ),
        "backend": "postgres" if _is_pg() else "local-sqlite",
        "schema_version": SCHEMA_VERSION,
    }


if __name__ == "__main__":
    init_db()
    print(f"✓ Yaddaş quruldu: {'postgres' if _is_pg() else 'local'}")
    print("Stat:", stats())
