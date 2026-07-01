"""
prompts/evolution.py — SELF-IMPROVEMENT LOOP.
═══════════════════════════════════════════════════════════════════════════════
Hər N=20 dövrdən sonra sistem öz performansını analiz edir, zəif tərəflərini
müəyyən edir, prompt-un özünü təkmilləşdirir. A/B test ilə təhlükəsiz.

Addımlar:
  1) Son N dövrənin metrics-lərini topla
  2) Ən yaxşı və ən pis nümunələri tap
  3) Zəif tərəfləri analiz et (hansı sahədə çatışmazlıq var?)
  4) Optimizer ilə yeni variantlar yarat
  5) Beyin çağırışı ilə dərin analiz (hansı dəyişiklik kömək edər?)
  6) A/B test: köhnə ilə yeni variantı müqayisə et
  7) Uğurlu olarsa, yeni variantı aktivləşdir
  8) DB-yə yaz (tarixçə)
═══════════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import re
import time
from datetime import datetime
from typing import Any

from prompts import store, optimizer, control, MASTER_PROMPT as MP
from tools import logger


# ══════════════════════════════════════════════════════════════════════════════
# KONFİQURASİYA
# ══════════════════════════════════════════════════════════════════════════════
EVOLUTION_INTERVAL = 20  # hər 20 dövrdən sonra
MIN_SAMPLES_FOR_EVOLUTION = 5  # minimum 5 sample lazımdır
PERFORMANCE_THRESHOLD = 0.7  # 70%-dən aşağı olarsa evolve et


# ══════════════════════════════════════════════════════════════════════════════
# PERFORMANS ANALİZİ
# ══════════════════════════════════════════════════════════════════════════════
def analyze_recent_performance(version: str | None = None, limit: int = EVOLUTION_INTERVAL) -> dict:
    """Son N dövrənin performansını analiz et."""
    metrics = store.get_metrics(version=version, limit=limit)
    if not metrics:
        return {
            "samples": 0,
            "avg_score": 0.0,
            "total_errors": 0,
            "success_rate": 0.0,
            "needs_evolution": False,
        }
    n = len(metrics)
    scores = [float(m.get("score", 0) or 0) for m in metrics]
    errors = sum(int(m.get("errors", 0) or 0) for m in metrics)
    successes = sum(1 for m in metrics if m.get("success"))
    avg = sum(scores) / n if n else 0
    success_rate = successes / n if n else 0
    return {
        "samples": n,
        "avg_score": avg,
        "min_score": min(scores) if scores else 0,
        "max_score": max(scores) if scores else 0,
        "total_errors": errors,
        "success_rate": success_rate,
        "needs_evolution": (n >= MIN_SAMPLES_FOR_EVOLUTION) and (avg < PERFORMANCE_THRESHOLD * 100 or success_rate < 0.7),
    }


def identify_weaknesses(metrics: list[dict]) -> list[str]:
    """Zəif tərəfləri müəyyən et."""
    weaknesses = []
    if not metrics:
        return ["heç bir metric yoxdur"]
    # Error analizi
    high_error = [m for m in metrics if int(m.get("errors", 0) or 0) > 2]
    if high_error:
        weaknesses.append(f"{len(high_error)} dövrdə yüksək xəta sayı (>2)")
    # Low score analizi
    low_score = [m for m in metrics if float(m.get("score", 0) or 0) < 50]
    if low_score:
        weaknesses.append(f"{len(low_score)} dövrdə aşağı score (<50)")
    # Failure analizi
    failures = [m for m in metrics if not m.get("success")]
    if failures:
        weaknesses.append(f"{len(failures)} uğursuz dövrə")
    if not weaknesses:
        weaknesses.append("gözəl görünür, amma dərin analiz lazımdır")
    return weaknesses


# ══════════════════════════════════════════════════════════════════════════════
# YENİ VARIANT YARAT (öyrənmə ilə)
# ══════════════════════════════════════════════════════════════════════════════
def generate_evolved_prompt(
    current_prompt: str,
    weaknesses: list[str],
    brain_fn=None,
) -> str | None:
    """Cari prompt + zəif tərəflər əsasında yeni variant yarat."""
    if not brain_fn:
        try:
            from brain.client import think_with_failover
            brain_fn = think_with_failover
        except Exception:
            return None
    meta_prompt = f"""\
Sən PROMPT EVOLUTION ENGINE-sən. Sənə verilmiş hazırkı MASTER PROMPT-un
zəif tərəfləri var. Bu zəif tərəfləri aradan qaldırmaq üçün promptu
TƏKMİLLƏŞDİR.

## ZƏİF TƏRƏFLƏR
{chr(10).join('- ' + w for w in weaknesses)}

## HAZIRKI PROMPT (ixtisarla, ilk 3000 simvol)
{current_prompt[:3000]}

## QAYDALAR
1. Sərt keyfiyyət qaydalarını (HARD_RULES) SAXLA, dəyişmə.
2. İdeal xüsusiyyətləri (IDEAL_TRAITS) SAXLA, gücləndir.
3. Yalnız zəif tərəfləri həll edən ƏLAVƏLƏR et.
4. Prompt-un ümumi strukturunu POZMA.
5. Azərbaycan dilində yaz.

## CAVAB FORMATI (JSON, başqa heç nə yox)
{{
  "improved_prompt": "təkmilləşdirilmiş TAM PROMPT mətni",
  "key_changes": ["dəyişiklik 1", "dəyişiklik 2", "dəyişiklik 3"],
  "addresses_weaknesses": ["həll olunan zəif tərəf 1", "..."],
  "expected_improvement": "gözlənilən təkmilləşmə (qısa)"
}}
"""
    try:
        r = brain_fn(
            prompt=meta_prompt,
            system=current_prompt[:4000],  # özünü kontekst olaraq istifadə et
            thinking=True,
            max_tokens=8000,
            timeout=300,
        )
        response = r.get("response", "")
        m = re.search(r"\{.*\}", response, re.S)
        if m:
            import json
            obj = json.loads(m.group(0))
            improved = obj.get("improved_prompt", "").strip()
            if improved and len(improved) > 1000:
                return improved
    except Exception as e:
        logger.warn(f"evolution: brain call failed: {e}")
    return None


# ══════════════════════════════════════════════════════════════════════════════
# A/B TEST
# ══════════════════════════════════════════════════════════════════════════════
def ab_test(new_prompt: str, current_prompt: str, test_metric: str = "length") -> dict:
    """Yeni variantın köhnədən daha yaxşı olub-olmadığını yoxla (sürətli test)."""
    # Sadə heuristik: uzunluq müqayisəsi + açar sözlərin olması
    score_new = 0
    score_old = 0
    required_sections = [
        "SƏRT KEYFİYYƏT", "HARD_RULES", "ŞƏXSİYYƏT", "DÜŞÜNCƏ",
        "DOĞRULAMA", "JSON", "Alternativ", "tənqid",
    ]
    for sec in required_sections:
        if sec.lower() in new_prompt.lower():
            score_new += 10
        if sec.lower() in current_prompt.lower():
            score_old += 10
    # Uzunluq balansı
    if 5000 <= len(new_prompt) <= 30000:
        score_new += 30
    if 5000 <= len(current_prompt) <= 30000:
        score_old += 30
    return {
        "score_new": score_new,
        "score_old": score_old,
        "winner": "new" if score_new > score_old else "old" if score_old > score_new else "tie",
        "diff": score_new - score_old,
    }


# ══════════════════════════════════════════════════════════════════════════════
# ƏSAS EVOLUTION FUNKSİYASI
# ══════════════════════════════════════════════════════════════════════════════
def evolve(
    cycle: int,
    force: bool = False,
    use_brain: bool = True,
) -> dict:
    """
    Self-improvement loop. Hər N dövrdən sonra çağırılır.
    force=True olarsa, N saymadan işlədir.
    """
    store.init_db()
    last = store.get_state("last_evolution_at")
    last_cycle = int(last) if last and str(last).isdigit() else 0
    if not force and (cycle - last_cycle) < EVOLUTION_INTERVAL:
        return {"action": "skip", "reason": f"too soon (last={last_cycle}, current={cycle})"}

    logger.info(f"🧬 EVOLUTION başladı (cycle={cycle})")

    # 1) Performans analizi
    a = store.get_active()
    current_version = a.get("version") if a else None
    current_prompt = (a.get("content") if a else None) or MP.build()
    perf = analyze_recent_performance(version=current_version, limit=EVOLUTION_INTERVAL)

    if not force and not perf["needs_evolution"]:
        store.set_state("last_evolution_at", cycle)
        store.set_state("evolution_count", int(store.get_state("evolution_count", 0)) + 1)
        logger.info(f"🧬 evolution skip: performans kafidir (avg={perf['avg_score']:.1f}, success={perf['success_rate']:.2f})")
        return {"action": "skip", "reason": "performance ok", "perf": perf}

    # 2) Zəif tərəfləri
    metrics = store.get_metrics(version=current_version, limit=EVOLUTION_INTERVAL)
    weaknesses = identify_weaknesses(metrics)

    # 3) Yeni variant
    new_prompt = None
    method = "rule_based"
    if use_brain:
        new_prompt = generate_evolved_prompt(current_prompt, weaknesses)
        if new_prompt:
            method = "brain_evolved"

    if not new_prompt:
        # Fallback: optimizer ilə "boost" prompt yarat
        opt = optimizer.optimize(
            user_prompt=f"Bu zəif tərəfləri həll et: {'; '.join(weaknesses)}",
            current_prompt=current_prompt,
        )
        picked = optimizer.pick(opt["variants"], opt["recommendation"])
        new_prompt = picked["prompt"]
        method = "optimizer_fallback"

    # 4) A/B test
    ab = ab_test(new_prompt, current_prompt)
    if ab["winner"] != "new" and not force:
        store.set_state("last_evolution_at", cycle)
        store.set_state("evolution_count", int(store.get_state("evolution_count", 0)) + 1)
        logger.info(f"🧬 evolution: yeni variant A/B testdə keçmədi (score_new={ab['score_new']}, old={ab['score_old']})")
        return {
            "action": "reject",
            "reason": "A/B test failed",
            "ab": ab,
            "weaknesses": weaknesses,
            "perf": perf,
        }

    # 5) Saxla + aktivləşdir
    new_version = store.save_version(
        content=new_prompt,
        source=f"evolution:{method}",
        score=float(ab["score_new"]),
        metadata={
            "weaknesses": weaknesses,
            "perf_before": perf,
            "ab": ab,
            "cycle": cycle,
        },
        activate=True,
    )

    store.set_state("last_evolution_at", cycle)
    store.set_state("evolution_count", int(store.get_state("evolution_count", 0)) + 1)
    logger.success(f"🧬 EVOLUTION OK: v{new_version} (method={method}, weaknesses={len(weaknesses)})")

    return {
        "action": "evolved",
        "new_version": new_version,
        "method": method,
        "weaknesses": weaknesses,
        "perf_before": perf,
        "ab": ab,
        "cycle": cycle,
        "at": time.time(),
        "at_human": datetime.now().isoformat(timespec="seconds"),
    }


def should_evolve(cycle: int) -> bool:
    """Evolution vaxtıdırmı?"""
    if cycle <= 0:
        return False
    if cycle % EVOLUTION_INTERVAL != 0:
        return False
    return True


__all__ = [
    "evolve", "should_evolve",
    "analyze_recent_performance", "identify_weaknesses",
    "generate_evolved_prompt", "ab_test",
    "EVOLUTION_INTERVAL", "MIN_SAMPLES_FOR_EVOLUTION", "PERFORMANCE_THRESHOLD",
]
