"""
prompts/control.py — CONTROL MEXANİZMİ (PAUSE/INJECT/RESUME/STATUS).
═══════════════════════════════════════════════════════════════════════════════
İstifadəçi sistemi PAUSE edib, yeni prompt daxil edib, RESUME edə bilər.
State DB-də saxlanılır (daemon hər dövrədə yoxlayır).

Əmrlər:
  pause(reason)     — daemonu dayandır
  resume()          — davam etdir
  inject(prompt)    — yeni prompt daxil et (optimizer-dən keçir)
  set_goal(goal)    — USER_GOAL dəyiş
  status()          — cari vəziyyəti göstər
  history(limit)    — son versiyalar
═══════════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Any

import config
from prompts import store, optimizer, directive, MASTER_PROMPT as MP
from tools import logger


# ══════════════════════════════════════════════════════════════════════════════
# STATE KEYS
# ══════════════════════════════════════════════════════════════════════════════
K_PAUSED = "paused"
K_PAUSED_AT = "paused_at"
K_PAUSED_REASON = "paused_reason"
K_INJECTED_PROMPT = "injected_prompt"
K_INJECTED_AT = "injected_at"
K_INJECTED_BY = "injected_by"
K_CURRENT_GOAL = "current_goal"
K_LAST_OPTIMIZE = "last_optimize_at"
K_LAST_EVOLUTION = "last_evolution_at"
K_EVOLUTION_COUNT = "evolution_count"


# ══════════════════════════════════════════════════════════════════════════════
# PAUSE / RESUME
# ══════════════════════════════════════════════════════════════════════════════
def pause(reason: str = "") -> dict:
    """Daemonu dayandır."""
    store.init_db()
    store.set_state(K_PAUSED, True)
    store.set_state(K_PAUSED_AT, time.time())
    store.set_state(K_PAUSED_REASON, reason)
    logger.warn(f"⏸  PAUSE: {reason or 'no reason'}")
    return {
        "action": "pause",
        "paused": True,
        "reason": reason,
        "at": time.time(),
        "at_human": datetime.now().isoformat(timespec="seconds"),
    }


def resume() -> dict:
    """Daemonu davam etdir."""
    store.init_db()
    was_paused = is_paused()
    store.set_state(K_PAUSED, False)
    store.set_state(K_PAUSED_AT, None)
    store.set_state(K_PAUSED_REASON, None)
    logger.success(f"▶  RESUME (was_paused={was_paused})")
    return {
        "action": "resume",
        "paused": False,
        "was_paused": was_paused,
        "at": time.time(),
        "at_human": datetime.now().isoformat(timespec="seconds"),
    }


def is_paused() -> bool:
    """Hazırda PAUSE olunubmu?"""
    return bool(store.get_state(K_PAUSED, False))


# ══════════════════════════════════════════════════════════════════════════════
# INJECT — yeni prompt daxil et
# ══════════════════════════════════════════════════════════════════════════════
def inject(
    user_prompt: str,
    by: str = "user",
    activate: bool = True,
    use_brain: bool = False,
) -> dict:
    """
    Yeni prompt daxil et:
      1. Optimizer-dən keçir (3 variant)
      2. Ən yaxşısını seç (auto-pick)
      3. DB-yə yaz
      4. Aktivləşdir (default)
    """
    store.init_db()
    logger.info(f"💉 INJECT: {user_prompt[:100]}")
    store.set_state(K_INJECTED_PROMPT, user_prompt)
    store.set_state(K_INJECTED_AT, time.time())
    store.set_state(K_INJECTED_BY, by)
    store.set_state(K_LAST_OPTIMIZE, time.time())

    # Optimizer çağır
    brain_fn = None
    if use_brain:
        try:
            from brain.client import think_with_failover
            brain_fn = think_with_failover
        except Exception:
            pass

    opt = optimizer.optimize(
        user_prompt=user_prompt,
        current_prompt=(get_active_prompt_text() or ""),
        use_brain=use_brain,
        brain_call_fn=brain_fn,
    )

    picked = optimizer.pick(opt["variants"], opt["recommendation"])
    version = store.save_version(
        content=picked["prompt"],
        source=f"inject:{by}",
        score=picked["score"],
        metadata={
            "user_prompt": user_prompt,
            "variants": [{"id": v["id"], "name": v["name"], "score": v["score"]} for v in opt["variants"]],
            "intent": opt["intent"],
            "user_prompt_quality": opt["user_prompt_quality"],
        },
        activate=activate,
    )

    # Direktiv kimi də əlavə et
    directive.add(user_prompt, added_by=by)

    logger.success(f"✓ INJECT ok: version={version}, variant={picked['name']}, score={picked['score']}")
    return {
        "action": "inject",
        "version": version,
        "variant_used": picked["name"],
        "variant_score": picked["score"],
        "all_variants": opt["variants"],
        "recommendation": opt["recommendation"],
        "user_prompt_quality": opt["user_prompt_quality"],
        "activated": activate,
        "at": time.time(),
        "at_human": datetime.now().isoformat(timespec="seconds"),
    }


# ══════════════════════════════════════════════════════════════════════════════
# SET_GOAL
# ══════════════════════════════════════════════════════════════════════════════
def set_goal(goal: str) -> dict:
    """USER_GOAL dəyiş."""
    store.init_db()
    store.set_state(K_CURRENT_GOAL, goal)
    logger.info(f"🎯 GOAL: {goal[:120]}")
    return {
        "action": "set_goal",
        "goal": goal,
        "at": time.time(),
        "at_human": datetime.now().isoformat(timespec="seconds"),
    }


def get_goal() -> str:
    """Hazırkı USER_GOAL (override və ya config)."""
    g = store.get_state(K_CURRENT_GOAL, None)
    if g:
        return g
    return config.USER_GOAL


# ══════════════════════════════════════════════════════════════════════════════
# AKTİV PROMPT
# ══════════════════════════════════════════════════════════════════════════════
def get_active_prompt_text() -> str | None:
    """Aktiv prompt mətni (DB-dən və ya default)."""
    a = store.get_active()
    if a and a.get("content"):
        return a["content"]
    return MP.build(user_goal=get_goal(), directives=[])


def build_runtime_prompt() -> str:
    """Runtime üçün tam prompt qur:
      - Aktiv prompt (DB-dən)
      - + İstifadəçi direktivləri
      - + USER_GOAL
      - + Əgər aktiv prompt yoxdursa, default MASTER
    """
    a = store.get_active()
    if a and a.get("content"):
        base = a["content"]
    else:
        base = MP.build(user_goal=get_goal(), directives=[])

    # Direktivləri əlavə et
    dirs = store.list_directives(active_only=True)
    if dirs:
        dir_text = "\n".join(f"  - {d['directive']}" for d in dirs)
        base = base + f"\n\n## DİNAMİK DİREKTİVLƏR (DB-dən, runtime)\n\n{dir_text}\n"

    # USER_GOAL override
    custom_goal = get_goal()
    if custom_goal and custom_goal != config.USER_GOAL:
        base = base + f"\n\n## CARİ İSTİFADƏÇİ HƏDƏFİ (override)\n\n{custom_goal}\n"

    return base


# ══════════════════════════════════════════════════════════════════════════════
# STATUS
# ══════════════════════════════════════════════════════════════════════════════
def status() -> dict:
    """Cari vəziyyət."""
    store.init_db()
    a = store.get_active()
    paused = is_paused()
    return {
        "paused": paused,
        "paused_at": store.get_state(K_PAUSED_AT),
        "paused_reason": store.get_state(K_PAUSED_REASON),
        "active_version": a.get("version") if a else None,
        "active_length": len(a["content"]) if a and a.get("content") else 0,
        "active_directives_count": len(a.get("directives_list", [])) if a else 0,
        "current_goal": get_goal(),
        "current_goal_override": store.get_state(K_CURRENT_GOAL) is not None,
        "last_optimize_at": store.get_state(K_LAST_OPTIMIZE),
        "last_evolution_at": store.get_state(K_LAST_EVOLUTION),
        "evolution_count": store.get_state(K_EVOLUTION_COUNT, 0),
        "injected_prompt": (store.get_state(K_INJECTED_PROMPT) or "")[:200],
        "ts": time.time(),
        "ts_human": datetime.now().isoformat(timespec="seconds"),
    }


def history(limit: int = 10) -> list[dict]:
    """Son versiyalar."""
    return store.list_versions(limit=limit)


def directives() -> list[dict]:
    """Aktiv direktivlər."""
    return store.list_directives(active_only=True)


# ══════════════════════════════════════════════════════════════════════════════
# DAEMON CHECK (hər dövrədə çağırılır)
# ══════════════════════════════════════════════════════════════════════════════
def daemon_should_run() -> tuple[bool, str]:
    """Daemon işləməli mi? (False, səbəb)"""
    if is_paused():
        reason = store.get_state(K_PAUSED_REASON, "no reason")
        return False, f"paused: {reason}"
    return True, ""


__all__ = [
    "pause", "resume", "is_paused", "inject",
    "set_goal", "get_goal",
    "get_active_prompt_text", "build_runtime_prompt",
    "status", "history", "directives",
    "daemon_should_run",
    "K_PAUSED", "K_PAUSED_AT", "K_PAUSED_REASON",
    "K_INJECTED_PROMPT", "K_INJECTED_AT", "K_INJECTED_BY",
    "K_CURRENT_GOAL", "K_LAST_OPTIMIZE", "K_LAST_EVOLUTION",
]
