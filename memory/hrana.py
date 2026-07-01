"""
memory/hrana.py — Birbaşa Turso Hrana v2 protokolu (libsql bypass).
Niyə? `libsql 0.1.11` JWKS yoxlamasında 404 alır (Turso JWKS URL-i köhnəlib).
Bu modul sadə HTTP POST ilə Hrana v2 endpointinə bağlanır — heç bir 3rd-party
klient yoxdur, heç bir JWT yoxlaması yoxdur (server özü yoxlayır).

İstifadə:
    from memory.hrana import HranaClient
    db = HranaClient(url, token)
    db.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)")
    rows = db.query("SELECT * FROM t")
"""
from __future__ import annotations

import json
import time
from typing import Any, Iterable

import requests


class HranaError(RuntimeError):
    """Hrana server xətası."""


class HranaClient:
    """Minimal Turso / libSQL müştəri — Hrana v2 protokol üzərindən HTTP."""

    def __init__(self, url: str, token: str, timeout: float = 30.0):
        if not url.startswith("libsql://") and not url.startswith("https://"):
            raise ValueError(f"URL libsql:// və ya https:// ilə başlamalıdır: {url}")
        # libsql://avtonomcogitate-xxx.turso.io  →  https://avtonomcogitate-xxx.turso.io
        if url.startswith("libsql://"):
            url = "https://" + url[len("libsql://"):]
        self.base_url = url.rstrip("/")
        self.token = token
        self.timeout = timeout
        # Pipeline endpoint — bir neçə sorğunu bir HTTP POST-da göndərir
        self.pipeline_url = self.base_url + "/v2/pipeline"

    def _request(self, body: dict) -> dict:
        """Bir Hrana sorğusu göndər (HTTP POST)."""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
        }
        r = requests.post(
            self.pipeline_url,
            headers=headers,
            data=json.dumps(body).encode("utf-8"),
            timeout=self.timeout,
        )
        if r.status_code != 200:
            raise HranaError(
                f"HTTP {r.status_code}: {r.text[:300]}"
            )
        try:
            data = r.json()
        except Exception as e:
            raise HranaError(f"JSON parse xətası: {e}; body={r.text[:200]}")
        if "error" in data:
            raise HranaError(f"Hrana error: {data['error']}")
        return data

    def _stmt(self, sql: str, args: Iterable[Any] = ()) -> dict:
        """Hrana statement obyekti yarat (parametrli)."""
        return {
            "sql": sql,
            "want_rows": True,
            "args": [
                {"type": "integer", "value": str(a)} if isinstance(a, int)
                else {"type": "float", "value": str(a)} if isinstance(a, float)
                else {"type": "null"} if a is None
                else {"type": "text", "value": str(a)}
                for a in args
            ],
        }

    def execute(self, sql: str, args: Iterable[Any] = ()) -> dict:
        """Bir statement icra et (INSERT/UPDATE/CREATE/...). Nəticəni qaytarır."""
        body = {
            "requests": [
                {"type": "execute", "stmt": self._stmt(sql, args)},
                {"type": "close"},
            ]
        }
        t0 = time.time()
        data = self._request(body)
        ms = int((time.time() - t0) * 1000)
        # data["results"][0] = {"type": "ok", "response": {...}} və ya "error"
        results = data.get("results", [])
        if not results:
            return {"affected_rows": 0, "duration_ms": ms, "last_insert_id": None}
        first = results[0]
        if first.get("type") == "error":
            raise HranaError(f"SQL xətası: {first.get('error')}")
        resp = first.get("response", {})
        return {
            "affected_rows": resp.get("affected_row_count", 0),
            "duration_ms": ms,
            "last_insert_id": resp.get("last_insert_rowid"),
        }

    def executemany(self, sql: str, rows: list[tuple]) -> int:
        """Çoxlu statement birbaşa (pipeline). Qaytarır: cəmi affected_rows."""
        if not rows:
            return 0
        requests_body = []
        for args in rows:
            requests_body.append({"type": "execute", "stmt": self._stmt(sql, args)})
        requests_body.append({"type": "close"})
        data = self._request({"requests": requests_body})
        total = 0
        for r in data.get("results", []):
            if r.get("type") == "error":
                raise HranaError(f"SQL xətası: {r.get('error')}")
            total += r.get("response", {}).get("affected_row_count", 0)
        return total

    def query(self, sql: str, args: Iterable[Any] = ()) -> list[dict]:
        """SELECT sorğusu — hər sətir dict olaraq qaytarılır (sütun adı ilə)."""
        body = {
            "requests": [
                {"type": "execute", "stmt": self._stmt(sql, args)},
                {"type": "close"},
            ]
        }
        data = self._request(body)
        results = data.get("results", [])
        if not results:
            return []
        first = results[0]
        if first.get("type") == "error":
            raise HranaError(f"SQL xətası: {first.get('error')}")
        resp = first.get("response", {})
        cols = [c["name"] for c in resp.get("cols", [])]
        rows_raw = resp.get("rows", [])
        out: list[dict] = []
        for r in rows_raw:
            row_dict: dict = {}
            for i, col in enumerate(cols):
                v = r[i] if i < len(r) else None
                # Hrana hər dəyəri {"type":..., "value":...} formatında qaytarır
                if isinstance(v, dict):
                    t = v.get("type")
                    val = v.get("value")
                    if t == "null":
                        row_dict[col] = None
                    elif t in ("integer", "float"):
                        try:
                            row_dict[col] = int(val) if t == "integer" else float(val)
                        except (TypeError, ValueError):
                            row_dict[col] = val
                    else:
                        # text, blob (base64) və s.
                        if t == "blob" and val:
                            import base64 as _b
                            try:
                                row_dict[col] = _b.b64decode(val)
                            except Exception:
                                row_dict[col] = val
                        else:
                            row_dict[col] = val
                else:
                    row_dict[col] = v
            out.append(row_dict)
        return out

    def queryone(self, sql: str, args: Iterable[Any] = ()) -> dict | None:
        """Bir sətir qaytarır (və ya None)."""
        rows = self.query(sql, args)
        return rows[0] if rows else None

    def close(self) -> None:
        """Hrana üçün close lazım deyil (HTTP stateless), amma uyğunluq üçün."""
        return None


def make_hrana_or_sqlite(url: str, token: str, local_path: str):
    """Əgər URL+token varsa HranaClient, yoxsa lokal sqlite3 Connection qaytarır.
    Hər ikisinin API-si demək olar ki, eynidir (execute, executemany, query, queryone)."""
    if url and token:
        return HranaClient(url, token)
    # Lokal fallback
    import sqlite3
    c = sqlite3.connect(local_path, timeout=30, check_same_thread=False)
    c.row_factory = sqlite3.Row
    try:
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA synchronous=NORMAL")
        c.execute("PRAGMA foreign_keys=ON")
    except Exception:
        pass
    return c
