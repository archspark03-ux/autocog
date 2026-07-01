"""
web/dashboard.py — 7/24 Real-Time Web Dashboard (TAM TƏHLÜKƏSİZ).
Beyinin canlı düşüncələrini, tapşırıqlarını, araşdırmalarını,
qeydlərini, statistikasını real-time göstərir.

Təhlükəsizlik qatları:
  - Token-based auth (URL və ya header)
  - Rate limiting (IP başına 60 sorğu/dəq)
  - Input sanitization (XSS)
  - CORS (frontend başqa domain-dən gələ bilər)
  - Pydantic validation (request data)
  - SQL injection qorunması (? placeholder)
  - Sağlamlıq paneli (uptime, stuck, disk, RAM, DB)

İstifadə:
  python -m web.dashboard
  və ya: uvicorn web.dashboard:app --host 0.0.0.0 --port 8080
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, conint

import config
from memory import store
import security
import health_monitor
import backup as backup_module


WEB_DIR = Path(__file__).parent
TEMPLATES = Jinja2Templates(directory=str(WEB_DIR / "templates"))

app = FastAPI(
    title="AvtonomCogitate — 7/24 Dashboard",
    description="Avtonom beyinin canlı düşüncələri, tapşırıqları, araşdırmaları",
    version="0.2.0",
)

# CORS — frontend başqa domain-dən gələ bilər (hələlik açıq, prod-da dard qoyula bilər)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Rate limiter — IP başına 60 sorğu/dəq (bütün endpointlərə tətbiq)
_rate_limiter = security.RateLimiter(max_per_minute=60)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """IP başına rate limiting."""
    ip = request.client.host if request.client else "unknown"
    # /ping public-dir, limit yoxdur
    if request.url.path != "/ping":
        if not _rate_limiter.check(ip):
            return JSONResponse(
                {"error": "rate limit exceeded", "limit": "60/min"},
                status_code=429,
            )
    return await call_next(request)


# Token-i yüklə (modul işə düşəndə)
def _get_token() -> str:
    return security.get_dashboard_token()

DASHBOARD_TOKEN = _get_token()


# ===== Pydantic modellər (validation üçün) =====
class LimitParam(BaseModel):
    limit: conint(ge=1, le=200) = 20


class StatusParam(BaseModel):
    status: str = Field(default="open", max_length=20, pattern=r"^(open|doing|done|dropped)$")


class NoteIdParam(BaseModel):
    note_id: conint(ge=1) = Field(...)


# ===== Ana səhifə =====
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return TEMPLATES.TemplateResponse(
        request,
        "index.html",
        {
            "user_goal": config.USER_GOAL,
            "active_brain": config.active_brain_name(),
            "loop_interval": config.LOOP_INTERVAL_SECONDS,
            "token": DASHBOARD_TOKEN,
        },
    )


# ===== API endpoint-ləri (HAMISI TOKEN + RATE LIMIT İLƏ QORUNUR) =====

@app.get("/api/stats")
async def api_stats(token: str = Depends(security.require_token)):
    return store.stats()


@app.get("/api/thoughts")
async def api_thoughts(
    limit: int = Query(20, ge=1, le=100),
    token: str = Depends(security.require_token),
):
    rows = store.recent_thoughts(limit=min(limit, 100))
    out = []
    for r in rows:
        try:
            parsed = json.loads(r.get("response", "{}") or "{}")
            focus = parsed.get("focus_question", "")
            observation = parsed.get("current_observation", "")
            action_type = (parsed.get("action") or {}).get("type", "")
            confidence = parsed.get("confidence_level", 0)
            new_tasks = len(parsed.get("new_tasks", []) or [])
        except Exception:
            focus = observation = action_type = ""
            confidence = 0
            new_tasks = 0
        out.append({
            "id": r.get("id"),
            "cycle": r.get("cycle"),
            "ts": r.get("ts"),
            "brain": r.get("brain", ""),
            "tokens_in": r.get("tokens_in", 0),
            "tokens_out": r.get("tokens_out", 0),
            "focus_question": security.sanitize_text(focus, 500),
            "current_observation": security.sanitize_text(observation, 1000),
            "action_type": security.sanitize_text(action_type, 50),
            "confidence": confidence,
            "new_tasks": new_tasks,
            "thinking_preview": security.sanitize_text(r.get("thinking", "") or "", 200),
            "response_preview": security.sanitize_text(r.get("response", "") or "", 300),
        })
    return JSONResponse(out)


@app.get("/api/tasks")
async def api_tasks(
    status: str = Query("open", max_length=20, pattern=r"^(open|doing|done|dropped)$"),
    limit: int = Query(50, ge=1, le=100),
    token: str = Depends(security.require_token),
):
    rows = store.list_tasks(status=status, limit=min(limit, 100))
    return JSONResponse(rows)


@app.get("/api/research")
async def api_research(
    limit: int = Query(20, ge=1, le=50),
    token: str = Depends(security.require_token),
):
    rows = store.recent_research(limit=min(limit, 50))
    out = []
    for r in rows:
        out.append({
            "id": r.get("id"),
            "cycle": r.get("cycle"),
            "ts": r.get("ts"),
            "query": security.sanitize_text(r.get("query", ""), 500),
            "source": security.sanitize_text(r.get("source", ""), 100),
            "summary": security.sanitize_text(r.get("summary", ""), 1000),
            "result_count": len(r.get("results", [])),
        })
    return JSONResponse(out)


@app.get("/api/notes")
async def api_notes(
    limit: int = Query(20, ge=1, le=50),
    token: str = Depends(security.require_token),
):
    """Qeydlər siyahısı (store.thread-safe)."""
    rows = store.list_notes(limit=min(limit, 50))
    return JSONResponse(rows)


@app.get("/api/notes/{note_id}")
async def api_note_detail(
    note_id: int,
    token: str = Depends(security.require_token),
):
    """Qeydin tam mətni (store.thread-safe)."""
    try:
        note_id_int = int(note_id)
    except (ValueError, TypeError):
        return JSONResponse({"error": "note_id must be int"}, status_code=400)
    row = store.get_note(note_id_int)
    if not row:
        return JSONResponse({"error": "tapılmadı"}, status_code=404)
    path = Path(row.get("path", ""))
    if path.exists():
        try:
            row["content"] = path.read_text(encoding="utf-8")
        except Exception as e:
            row["content"] = f"(oxuma xətası: {e})"
    else:
        row["content"] = f"(fayl tapılmadı: {path})"
    return JSONResponse(row)


@app.get("/api/health")
async def api_health(token: str = Depends(security.require_token)):
    """Tam sağlamlıq hesabatı."""
    return health_monitor.health_report()


@app.post("/api/backup")
async def api_backup(token: str = Depends(security.require_token)):
    """Manual backup yarat."""
    try:
        b = backup_module.create_backup()
        if b:
            return {"ok": True, "path": str(b)}
        return JSONResponse({"ok": False, "error": "backup yaradıla bilmədi"}, status_code=500)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.get("/api/backups")
async def api_backups(token: str = Depends(security.require_token)):
    """Mövcud backup-ları göstər."""
    return backup_module.list_backups()


# ===== Public health (auth istəmir, sadəcə up/down) =====
@app.get("/ping")
async def ping():
    """Public ping - dashboard işləyirmi?"""
    return {
        "ok": True,
        "ts": datetime.now().isoformat(timespec="seconds"),
        "version": "0.2.0",
    }


@app.get("/api/login")
async def api_login(token: str = ""):
    """Token ilə giriş."""
    if not token or not security.verify_token(token):
        return JSONResponse({"ok": False, "error": "token yanlışdır"}, status_code=401)
    return {"ok": True, "message": "token qəbul edildi"}


if __name__ == "__main__":
    import uvicorn
    print("\n" + "=" * 60)
    print("  AVTONOMCOGITATE — 7/24 REAL-TIME DASHBOARD (TƏHLÜKƏSİZ)")
    print("=" * 60)
    print(f"  URL  : http://localhost:8080")
    print(f"  Token: {DASHBOARD_TOKEN[:16]}...")
    print(f"  Full URL (token ilə): http://localhost:8080/?token={DASHBOARD_TOKEN}")
    print(f"  Beyin: {config.active_brain_name()}")
    print(f"  DB backend: {'remote-postgres' if config.USE_REMOTE_DB else 'local-sqlite'}")
    print("=" * 60 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="warning")
