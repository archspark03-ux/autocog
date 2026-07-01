"""
prompts/store.py — MASTER PROMPT DB (persistent yaddaş).
═══════════════════════════════════════════════════════════════════════════════
Dual backend: lokal SQLite (default) və ya Neon PostgreSQL (config DATABASE_URL).
Cədvəllər:
  • prompt_versions  — bütün prompt versiyaları (tarixçə)
  • prompt_active    — hazırda aktiv olan prompt (id, content, version)
  • prompt_directives — runtime direktivlər
  • prompt_metrics   — performans ölçüləri (hər dövrə üçün)
  • prompt_state     — control state (paused, last_action, etc.)
═══════════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import config

_lock = threading.RLock()

_backend_kind = "local"
_backend = None


def _init_backend():
    """Backend-i initialize et (SQLite və ya PostgreSQL)."""
    global _backend_kind, _backend
    if _backend is not None:
        return
    pg_dsn = os.getenv("DATABASE_URL", "").strip()
    if pg_dsn:
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor
            if "sslmode" not in pg_dsn:
                sep = "&" if "?" in pg_dsn else "?"
                pg_dsn = f"{pg_dsn}{sep}sslmode=require"
            _backend = psycopg2.connect(pg_dsn, cursor_factory=RealDictCursor, connect_timeout=10)
            _backend.autocommit = True
            _backend_kind = "postgres"
        except Exception as e:
            print(f"prompts/store: postgres bağlantı xətası, SQLite-ə keçir: {e}")
            _backend = None
    if _backend is None:
        db_path = config.MEMORY_DB.parent / "prompts.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        c = sqlite3.connect(str(db_path), timeout=30, check_same_thread=False, isolation_level=None)
        c.row_factory = sqlite3.Row
        try:
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("PRAGMA synchronous=NORMAL")
        except Exception:
            pass
        _backend = c
        _backend_kind = "local"


def _is_pg() -> bool:
    _init_backend()
    return _backend_kind == "postgres"


def _q(sql: str) -> str:
    """SQLite `?` → PostgreSQL `%s`."""
    if _is_pg():
        return sql.replace("?", "%s")
    return sql


def _exec(sql: str, args: tuple = ()) -> None:
    with _lock:
        _init_backend()
        cur = _backend.cursor()
        cur.execute(_q(sql), args)
        cur.close()


def _fetchone(sql: str, args: tuple = ()) -> dict | None:
    with _lock:
        _init_backend()
        cur = _backend.cursor()
        cur.execute(_q(sql), args)
        if _is_pg():
            r = cur.fetchone()
            cur.close()
            return dict(r) if r else None
        r = cur.fetchone()
        cur.close()
        return dict(r) if r else None


def _fetchall(sql: str, args: tuple = ()) -> list[dict]:
    with _lock:
        _init_backend()
        cur = _backend.cursor()
        cur.execute(_q(sql), args)
        if _is_pg():
            rows = cur.fetchall()
            cur.close()
            return [dict(r) for r in rows]
        rows = cur.fetchall()
        cur.close()
        return [dict(r) for r in rows]


# ══════════════════════════════════════════════════════════════════════════════
# SCHEMA
# ══════════════════════════════════════════════════════════════════════════════
def init_db() -> None:
    """Bütün cədvəlləri yarat (yoxdursa)."""
    _init_backend()
    if _is_pg():
        stmts = [
            """CREATE TABLE IF NOT EXISTS prompt_versions (
                id SERIAL PRIMARY KEY,
                version TEXT UNIQUE NOT NULL,
                content TEXT NOT NULL,
                source TEXT,
                score REAL,
                is_active BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT
            )""",
            """CREATE TABLE IF NOT EXISTS prompt_active (
                id INTEGER PRIMARY KEY,
                version TEXT NOT NULL,
                content TEXT NOT NULL,
                directives TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            """CREATE TABLE IF NOT EXISTS prompt_directives (
                id SERIAL PRIMARY KEY,
                directive TEXT NOT NULL,
                added_by TEXT,
                active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            """CREATE TABLE IF NOT EXISTS prompt_metrics (
                id SERIAL PRIMARY KEY,
                version TEXT NOT NULL,
                cycle INTEGER,
                score REAL,
                errors INTEGER DEFAULT 0,
                success BOOLEAN,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            """CREATE TABLE IF NOT EXISTS prompt_state (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
        ]
    else:
        stmts = [
            """CREATE TABLE IF NOT EXISTS prompt_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version TEXT UNIQUE NOT NULL,
                content TEXT NOT NULL,
                source TEXT,
                score REAL,
                is_active INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT
            )""",
            """CREATE TABLE IF NOT EXISTS prompt_active (
                id INTEGER PRIMARY KEY,
                version TEXT NOT NULL,
                content TEXT NOT NULL,
                directives TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            """CREATE TABLE IF NOT EXISTS prompt_directives (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                directive TEXT NOT NULL,
                added_by TEXT,
                active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            """CREATE TABLE IF NOT EXISTS prompt_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version TEXT NOT NULL,
                cycle INTEGER,
                score REAL,
                errors INTEGER DEFAULT 0,
                success INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            """CREATE TABLE IF NOT EXISTS prompt_state (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
        ]
    for s in stmts:
        _exec(s)


# ══════════════════════════════════════════════════════════════════════════════
# VERSİYALAMA
# ══════════════════════════════════════════════════════════════════════════════
def save_version(content: str, source: str = "system", score: float | None = None,
                 metadata: dict | None = None, activate: bool = False) -> str:
    """Yeni versiya saxla, qaytar: version (məs. v2.0.1-1700000000)."""
    init_db()
    version = f"v{int(time.time())}"
    meta_str = json.dumps(metadata or {}, ensure_ascii=False)
    with _lock:
        _init_backend()
        if activate:
            _exec("UPDATE prompt_versions SET is_active = FALSE")
        _exec(
            "INSERT INTO prompt_versions (version, content, source, score, is_active, metadata) VALUES (?, ?, ?, ?, ?, ?)",
            (version, content, source, score, bool(activate), meta_str),
        )
        if activate:
            _set_active(version, content)
    return version


def _set_active(version: str, content: str, directives: list[str] | None = None) -> None:
    """Aktiv prompt təyin et."""
    init_db()
    directives_json = json.dumps(directives or [], ensure_ascii=False)
    if _is_pg():
        _exec("DELETE FROM prompt_active WHERE id = 1")
        _exec(
            "INSERT INTO prompt_active (id, version, content, directives, updated_at) VALUES (1, ?, ?, ?, CURRENT_TIMESTAMP)",
            (version, content, directives_json),
        )
    else:
        _exec("DELETE FROM prompt_active WHERE id = 1")
        _exec(
            "INSERT INTO prompt_active (id, version, content, directives, updated_at) VALUES (1, ?, ?, ?, CURRENT_TIMESTAMP)",
            (version, content, directives_json),
        )


def activate_version(version: str) -> bool:
    """Mövcud versiyanı aktivləşdir."""
    init_db()
    r = _fetchone("SELECT version, content FROM prompt_versions WHERE version = ?", (version,))
    if not r:
        return False
    with _lock:
        _exec("UPDATE prompt_versions SET is_active = FALSE")
        _exec("UPDATE prompt_versions SET is_active = TRUE WHERE version = ?", (version,))
        _set_active(r["version"], r["content"])
    return True


def get_active() -> dict | None:
    """Aktiv prompt qaytar."""
    init_db()
    r = _fetchone("SELECT * FROM prompt_active WHERE id = 1")
    if not r:
        return None
    if r.get("directives"):
        try:
            r["directives_list"] = json.loads(r["directives"])
        except Exception:
            r["directives_list"] = []
    else:
        r["directives_list"] = []
    return r


# ══════════════════════════════════════════════════════════════════════════════
# DİREKTİVLƏR
# ══════════════════════════════════════════════════════════════════════════════
def add_directive(directive: str, added_by: str = "user") -> int:
    """Yeni direktiv əlavə et."""
    init_db()
    _exec(
        "INSERT INTO prompt_directives (directive, added_by) VALUES (?, ?)",
        (directive.strip(), added_by),
    )
    r = _fetchone("SELECT last_insert_rowid() AS id" if not _is_pg() else "SELECT lastval() AS id")
    return int(r["id"]) if r else 0


def list_directives(active_only: bool = True) -> list[dict]:
    init_db()
    if active_only:
        r = _fetchall(
            "SELECT * FROM prompt_directives WHERE active = TRUE ORDER BY id DESC"
        )
    else:
        r = _fetchall("SELECT * FROM prompt_directives ORDER BY id DESC")
    return r


def deactivate_directive(directive_id: int) -> bool:
    init_db()
    _exec("UPDATE prompt_directives SET active = FALSE WHERE id = ?", (directive_id,))
    return True


def clear_directives() -> int:
    """Bütün direktivləri deaktiv et, qaytar: say."""
    init_db()
    r = _fetchall("SELECT id FROM prompt_directives WHERE active = TRUE")
    for row in r:
        _exec("UPDATE prompt_directives SET active = FALSE WHERE id = ?", (row["id"],))
    return len(r)


# ══════════════════════════════════════════════════════════════════════════════
# METRİKLƏR
# ══════════════════════════════════════════════════════════════════════════════
def add_metric(version: str, cycle: int, score: float, errors: int = 0, success: bool = True) -> None:
    init_db()
    _exec(
        "INSERT INTO prompt_metrics (version, cycle, score, errors, success) VALUES (?, ?, ?, ?, ?)",
        (version, cycle, score, errors, bool(success)),
    )


def get_metrics(version: str | None = None, limit: int = 50) -> list[dict]:
    init_db()
    if version:
        return _fetchall(
            "SELECT * FROM prompt_metrics WHERE version = ? ORDER BY id DESC LIMIT ?",
            (version, limit),
        )
    return _fetchall("SELECT * FROM prompt_metrics ORDER BY id DESC LIMIT ?", (limit,))


def version_stats() -> list[dict]:
    init_db()
    if _is_pg():
        return _fetchall(
            """SELECT version, COUNT(*) AS n, AVG(score) AS avg_score,
                      SUM(errors) AS total_errors,
                      SUM(CASE WHEN success THEN 1 ELSE 0 END) AS successes
               FROM prompt_metrics GROUP BY version ORDER BY avg_score DESC NULLS LAST"""
        )
    return _fetchall(
        """SELECT version, COUNT(*) AS n, AVG(score) AS avg_score,
                  SUM(errors) AS total_errors, SUM(success) AS successes
           FROM prompt_metrics GROUP BY version ORDER BY avg_score DESC"""
    )


# ══════════════════════════════════════════════════════════════════════════════
# STATE (control üçün: paused, last_action, etc.)
# ══════════════════════════════════════════════════════════════════════════════
def set_state(key: str, value: Any) -> None:
    init_db()
    v = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    if _is_pg():
        _exec(
            """INSERT INTO prompt_state (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = CURRENT_TIMESTAMP""",
            (key, v),
        )
    else:
        _exec(
            """INSERT INTO prompt_state (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP""",
            (key, v),
        )


def get_state(key: str, default: Any = None) -> Any:
    init_db()
    r = _fetchone("SELECT value FROM prompt_state WHERE key = ?", (key,))
    if not r:
        return default
    v = r.get("value", "")
    if not v:
        return default
    try:
        return json.loads(v)
    except Exception:
        return v


def get_all_state() -> dict:
    init_db()
    rows = _fetchall("SELECT key, value, updated_at FROM prompt_state")
    out = {}
    for r in rows:
        v = r.get("value", "")
        try:
            out[r["key"]] = json.loads(v)
        except Exception:
            out[r["key"]] = v
    return out


# ══════════════════════════════════════════════════════════════════════════════
# TARİXÇƏ
# ══════════════════════════════════════════════════════════════════════════════
def list_versions(limit: int = 20) -> list[dict]:
    init_db()
    return _fetchall("SELECT * FROM prompt_versions ORDER BY id DESC LIMIT ?", (limit,))


def get_version(version: str) -> dict | None:
    init_db()
    return _fetchone("SELECT * FROM prompt_versions WHERE version = ?", (version,))


__all__ = [
    "init_db",
    "save_version", "activate_version", "get_active",
    "add_directive", "list_directives", "deactivate_directive", "clear_directives",
    "add_metric", "get_metrics", "version_stats",
    "set_state", "get_state", "get_all_state",
    "list_versions", "get_version",
]
