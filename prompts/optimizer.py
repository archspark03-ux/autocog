"""
prompts/optimizer.py — PROMPT OPTIMIZER (günümüzün ən güclü).
═══════════════════════════════════════════════════════════════════════════════
İstifadəçinin sərbəst yazdığı prompt-u 3 alternativ gücləndirilmiş variantına
çevirir. Rule-based + beyin çağırışı (keyfiyyət dərinliyi üçün) hibrid.

Giriş: istifadəçi promptu (sərbəst mətn, istənilən formatda)
Çıxış: 3 alternativ variant + 1 tövsiyə (auto-pick ən yaxşısı)

Hər variant aşağıdakıları təmin edir:
  • MASTER_PROMPT-un strukturuna uyğun bölmələr
  • Sərt keyfiyyət qaydaları (HARD_RULES)
  • Çox şaxəli düşüncə
  • Doğrulama protokulu
  • JSON cavab formatı
  • Azərbaycan dili
═══════════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import json
import re
import time
from typing import Any

from prompts import MASTER_PROMPT as MP
from tools import logger


# ══════════════════════════════════════════════════════════════════════════════
# KÖMƏKÇİ FUNKSİYALAR
# ══════════════════════════════════════════════════════════════════════════════
def _normalize(text: str) -> str:
    """Mətni təmizlə, normalize et."""
    if not text:
        return ""
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    return text


def _extract_intent(text: str) -> dict[str, Any]:
    """İstifadəçi promptundan niyyəti çıxar."""
    t = text.lower()
    return {
        "wants_more_analytical": any(w in t for w in ["analitik", "analiz", "dərindən", "dərin", "ətraflı"]),
        "wants_more_creative": any(w in t for w in ["yaradıcı", "kreativ", "fərqli", "orijinal", "yenilikçi"]),
        "wants_more_critical": any(w in t for w in ["tənqidi", "sərt", "sərbəst deyil", "səhv axtar"]),
        "wants_more_foresight": any(w in t for w in ["gələcək", "5 il", "10 il", "uzunmüddətli", "proqnoz"]),
        "wants_shorter": any(w in t for w in ["qısa", "az", "kompakt", "minimal"]),
        "wants_longer": any(w in t for w in ["uzun", "çox", "geniş", "hərtərəfli", "daha ətraflı"]),
        "wants_azeri": any(w in t for w in ["azərbaycan", "azərbaycanca", "ana dil"]),
        "wants_english": any(w in t for w in ["english", "ingilis"]),
        "wants_pause": any(w in t for w in ["dayan", "pause", "dayandır", "gözlə"]),
        "wants_research": any(w in t for w in ["araşdır", "research", "tap"]),
        "wants_evidence": any(w in t for w in ["sübut", "mənbə", "dəlil", "sitat"]),
        "wants_no_hallucination": any(w in t for w in ["halusinasiya", "uydurma", "dəqiq", "gerçək"]),
        "wants_summary": any(w in t for w in ["xülasə", "icmal", "qısa məzmun"]),
    }


def _quality_score(text: str) -> float:
    """Promptun keyfiyyətini 0-100 balla qiymətləndir (rule-based)."""
    score = 50.0  # baza
    if not text:
        return 0.0
    t = text.lower()
    n = len(text)

    # Uzunluq (orta uzunluq yaxşıdır)
    if 50 <= n <= 500:
        score += 10
    elif n > 1000:
        score -= 5  # çox uzun, fokus itir

    # Aydınlıq göstəriciləri
    if any(w in t for w in ["məqsəd", "hədəf", "goal"]):
        score += 5
    if any(w in t for w in ["sən", "sənin", "siz"]):
        score += 3  # persona var
    if any(w in t for w in ["json", "format", "schema"]):
        score += 8  # struktur var
    if any(w in t for w in ["mənbə", "sübut", "arxiv", "doi"]):
        score += 8  # sübut şüuru
    if any(w in t for w in ["no hype", "no clickbait", "sərt", "qayda"]):
        score += 5  # keyfiyyət qaydaları var

    # Mənfi göstəricilər
    if "?" not in text and "nədir" not in t and "necə" not in t:
        score -= 5  # sual yoxdur
    if any(w in t for w in ["hər şeyi bil", "hamısını et", "qısa yaz", "qısa"]):
        score -= 3  # çox ümumi
    if "uydur" in t or "yarad" in t and "fakt" not in t:
        score -= 10  # halusinasiya təşviqi

    return max(0.0, min(100.0, score))


# ══════════════════════════════════════════════════════════════════════════════
# 3 ALTERNATİV VARIANT
# ══════════════════════════════════════════════════════════════════════════════
def _variant_minimal(user_prompt: str) -> str:
    """Variant 1: MINIMAL — qısa, sadə, sürətli.
    İstifadəçi qısa/birbaşa prompt istədikdə ideal.
    """
    return f"""\
## MASTER PROMPT — MİNİMAL VARIANT (variant 1/3)

Sən AvtonomCogitate-sən. Aşağıdakı qaydaları pozma:

  1. Sıfır halusinasiya — uydurma, mənbəsiz iddia etmə.
  2. Sübut göstər — hər rəqəm üçün mənbə.
  3. Hype yoxdur — populist fikir yox.
  4. JSON ilə cavab ver.

İstifadəçi direktivi:
{user_prompt.strip()}

JSON cavab formatı:
{{"thinking", "focus_question", "action", "next_step", "new_tasks"}}
"""


def _variant_balanced(user_prompt: str) -> str:
    """Variant 2: BALANCED — orta uzunluq, bütün vacib qaydalar.
    Default variant — əksər hallarda bu istifadə olunur.
    """
    return f"""\
## MASTER PROMPT — BALANCED VARIANT (variant 2/3) — TÖVSİYƏ OLUNAN

{MP.IDENTITY}

{MP.HARD_RULES}

{MP.IDEAL_TRAITS}

{MP.MULTI_BRANCH_FRAMEWORK}

{MP.VERIFICATION_PROTOCOL}

{MP.format_user_goal(user_prompt)}

{MP.RESEARCH_METHODOLOGY}

{MP.OUTPUT_SCHEMA}

DİREKTİV: "{user_prompt.strip()}"

Bu direktivə uyğun düşün, amma HARD_RULES üstündür.
"""


def _variant_maximal(user_prompt: str) -> str:
    """Variant 3: MAXIMAL — bütün 14 bölmə, hərtərəfli.
    İstifadəçi dərin, ətraflı iş istədikdə ideal.
    """
    return f"""\
## MASTER PROMPT — MAXIMAL VARIANT (variant 3/3)

{MP.build(user_goal=user_prompt, directives=[user_prompt])}
"""


# ══════════════════════════════════════════════════════════════════════════════
# OPTİMİZER ƏSAS FUNKSİYASI
# ══════════════════════════════════════════════════════════════════════════════
def optimize(
    user_prompt: str,
    current_prompt: str = "",
    use_brain: bool = False,
    brain_call_fn=None,
) -> dict[str, Any]:
    """
    İstifadəçi promptunu 3 alternativ variantına çevir.

    Args:
        user_prompt: İstifadəçinin yeni direktivi (sərbəst mətn)
        current_prompt: Hazırkı aktiv prompt (kontekst üçün)
        use_brain: True olarsa beyin çağırışı ilə daha dərin optimallaşdırma
        brain_call_fn: beyin çağırışı funksiyası (think_with_failover və s.)

    Returns:
        {
            "variants": [
                {"id": 1, "name": "minimal", "prompt": "...", "score": 0-100, "length": int},
                {"id": 2, "name": "balanced", "prompt": "...", "score": 0-100, "length": int},
                {"id": 3, "name": "maximal", "prompt": "...", "score": 0-100, "length": int},
            ],
            "recommendation": int  # tövsiyə olunan variantın ID-si
            "intent": dict,  # çıxarılmış niyyət
            "user_prompt_quality": float,  # 0-100
            "ts": float,  # timestamp
            "took_ms": int,
        }
    """
    t0 = time.time()
    user_prompt = _normalize(user_prompt)
    intent = _extract_intent(user_prompt)
    user_q = _quality_score(user_prompt)

    # Variant 1: minimal
    v1_text = _variant_minimal(user_prompt)
    v1_score = 50
    if intent["wants_shorter"]:
        v1_score = 90
    elif intent["wants_longer"]:
        v1_score = 30

    # Variant 2: balanced (default tövsiyə)
    v2_text = _variant_balanced(user_prompt)
    v2_score = 80
    if intent["wants_more_analytical"] or intent["wants_more_critical"]:
        v2_score = 85
    if intent["wants_shorter"]:
        v2_score = 70
    if intent["wants_longer"]:
        v2_score = 85

    # Variant 3: maximal
    v3_text = _variant_maximal(user_prompt)
    v3_score = 70
    if intent["wants_longer"] or intent["wants_more_analytical"]:
        v3_score = 90
    if intent["wants_shorter"]:
        v3_score = 40

    # Tövsiyə
    scores = [(1, v1_score), (2, v2_score), (3, v3_score)]
    recommendation = max(scores, key=lambda x: x[1])[0]

    # Əgər istifadəçi çox qısadırsa (keyfiyyət aşağı) və beyin istəyirsə
    if use_brain and brain_call_fn and user_q < 50:
        try:
            meta_prompt = f"""\
Sən PROMPT OPTIMIZER-sən. Sənə verilmiş istifadəçi prompt-unu
gücləndir, MASTER PROMPT-un strukturuna uyğunlaşdır.

İstifadəçi promptu: "{user_prompt}"

Cavab formatı (JSON):
{{
  "improved_prompt": "gücləndirilmiş prompt, Azərbaycan dilində",
  "key_additions": ["əlavə etdiyin əsas şeylər"],
  "removed": ["çıxardıqların"],
  "score_change": "keyfiyyət dəyişikliyi (-100 ilə +100 arası)"
}}

Yalnız JSON qaytar, başqa heç nə yox.
"""
            from prompts.MASTER_PROMPT import build
            system = build()
            r = brain_call_fn(
                prompt=meta_prompt,
                system=system,
                thinking=True,
                max_tokens=2048,
                timeout=120,
            )
            response = r.get("response", "")
            # JSON parse et
            m = re.search(r"\{.*\}", response, re.S)
            if m:
                obj = json.loads(m.group(0))
                improved = obj.get("improved_prompt", "").strip()
                if improved:
                    # Variant 2-ni improved ilə əvəz et
                    v2_text = _variant_balanced(improved)
                    v2_score = min(100, v2_score + 15)
                    recommendation = 2
                    logger.info(f"optimizer: brain improvement applied (variants updated)")
        except Exception as e:
            logger.warn(f"optimizer brain call failed: {e}")

    took_ms = int((time.time() - t0) * 1000)
    result = {
        "variants": [
            {"id": 1, "name": "minimal", "prompt": v1_text, "score": v1_score, "length": len(v1_text)},
            {"id": 2, "name": "balanced", "prompt": v2_text, "score": v2_score, "length": len(v2_text)},
            {"id": 3, "name": "maximal", "prompt": v3_text, "score": v3_score, "length": len(v3_text)},
        ],
        "recommendation": recommendation,
        "intent": intent,
        "user_prompt_quality": user_q,
        "ts": time.time(),
        "took_ms": took_ms,
    }
    logger.info(
        f"optimizer: {len(user_prompt)} char → 3 variants "
        f"(rec={recommendation}, quality={user_q:.0f}, {took_ms}ms)"
    )
    return result


def pick(variants: list[dict], recommendation: int | None = None) -> dict:
    """Variant siyahısından birini seç (default: recommendation)."""
    if not variants:
        return {}
    if recommendation is None:
        recommendation = max(variants, key=lambda v: v.get("score", 0)).get("id", 1)
    for v in variants:
        if v.get("id") == recommendation:
            return v
    return variants[0]


__all__ = ["optimize", "pick", "_quality_score", "_extract_intent"]
