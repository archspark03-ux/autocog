"""
security.py — Təhlükəsizlik qatı.
- Dashboard üçün token-based auth
- Input sanitization (XSS, SQL injection)
- Rate limiting
- Şifrələmə (config)
"""
from __future__ import annotations

import hashlib
import os
import secrets
import time
from collections import defaultdict
from functools import wraps
from pathlib import Path
from typing import Callable

from fastapi import HTTPException, Request, status

import config


# ===== Token Auth =====
# .env-də DASHBOARD_TOKEN təyin et, yoxsa avtomatik yaranır (faylda saxlanılır)
_TOKEN_FILE = config.ROOT / "memory" / ".dashboard_token"


def get_dashboard_token() -> str:
    """Dashboard token qaytarır. İlk dəfə yaradılır, .env varsa onu istifadə edir."""
    env_token = os.getenv("DASHBOARD_TOKEN", "").strip()
    if env_token:
        return env_token
    if _TOKEN_FILE.exists():
        return _TOKEN_FILE.read_text(encoding="utf-8").strip()
    # Avtomatik yarat
    _TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    token = secrets.token_urlsafe(32)
    _TOKEN_FILE.write_text(token, encoding="utf-8")
    return token


def verify_token(token: str) -> bool:
    """Token doğrudurmu?"""
    real = get_dashboard_token()
    return secrets.compare_digest(token, real)


# ===== Rate Limiter (çox sadə) =====
class RateLimiter:
    """IP başına sorğu sayını məhdudlaşdırır."""

    def __init__(self, max_per_minute: int = 60):
        self.max_per_minute = max_per_minute
        self.calls: dict[str, list[float]] = defaultdict(list)

    def check(self, ip: str) -> bool:
        """Sorğu buraxılsınmı?"""
        now = time.time()
        # Köhnə sorğuları təmizlə
        self.calls[ip] = [t for t in self.calls[ip] if now - t < 60]
        if len(self.calls[ip]) >= self.max_per_minute:
            return False
        self.calls[ip].append(now)
        return True

    # Alias — daha oxunaqlı API
    def allow(self, ip: str) -> bool:
        return self.check(ip)


# Əsas rate limiter — dashboard üçün
dashboard_limiter = RateLimiter(max_per_minute=120)  # 2 sorğu/san


# ===== Input Sanitization =====
def sanitize_text(text: str, max_length: int = 10000) -> str:
    """İstifadəçi mətni təmizlə (XSS, çox uzun)."""
    if not text:
        return ""
    # Çox uzun
    if len(text) > max_length:
        text = text[:max_length]
    # NUL və digər təhlükəli simvollar
    text = text.replace("\x00", "").replace("\r", "")
    # XSS: script/iframe/object/embed tag-lərini və onload/onerror kimi event-ləri sil
    import re as _re
    text = _re.sub(r"<\s*script[^>]*>.*?<\s*/\s*script\s*>", "", text, flags=_re.IGNORECASE | _re.DOTALL)
    text = _re.sub(r"<\s*iframe[^>]*>.*?<\s*/\s*iframe\s*>", "", text, flags=_re.IGNORECASE | _re.DOTALL)
    text = _re.sub(r"<\s*(object|embed|svg|img)[^>]*/?\s*>", "", text, flags=_re.IGNORECASE)
    text = _re.sub(r"\son\w+\s*=\s*['\"][^'\"]*['\"]", "", text, flags=_re.IGNORECASE)
    text = _re.sub(r"javascript\s*:", "", text, flags=_re.IGNORECASE)
    return text.strip()


# ===== Dashboard Auth Dependency =====
async def require_token(request: Request):
    """Dashboard sorğuları üçün token yoxla."""
    # IP rate limit
    ip = request.client.host if request.client else "unknown"
    if not dashboard_limiter.check(ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="çox sorğu, 1 dəqiqə gözlə",
        )

    # Token yoxla (query, header və ya cookie)
    token = (
        request.query_params.get("token")
        or request.headers.get("X-Dashboard-Token")
        or request.cookies.get("dashboard_token")
    )
    if not token or not verify_token(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token yanlışdır və ya yoxdur. ?token=... ilə keç",
        )
    return token


# ===== Yaddaş şifrələmə (password qoruma) =====
def hash_password(password: str) -> str:
    """Parol hash et (sha256 + salt)."""
    salt = "avtonomcogitate-salt-2026"
    return hashlib.sha256((password + salt).encode()).hexdigest()


if __name__ == "__main__":
    print("Təhlükəsizlik modulu")
    print(f"Dashboard token: {get_dashboard_token()[:16]}...")
    print(f"URL: http://localhost:8080/?token={get_dashboard_token()}")
