"""
prompts/directive.py — NATURAL LANGUAGE INTERFACE.
═══════════════════════════════════════════════════════════════════════════════
İstifadəçi səninlə necə danışırsa, öz sisteminə də elə danışa bilər.
Bu modul natural language direktivləri parse edib, sistem direktivinə çevirir.

Misal:
  İstifadəçi: "Daha çox analitik ol"        → analytics_boost: +20
  İstifadəçi: "Qısa yaz"                    → concise_mode
  İstifadəçi: "Sən artıq fizikisən"          → persona: physicist
  İstifadəçi: "Azərbaycan dilində yaz"       → language: az
  İstifadəçi: "5 il sonraya bax"             → foresight_boost: +30
  İstifadəçi: "Dayan, dayandır"              → PAUSE
  İstifadəçi: "Davam et"                     → RESUME
  İstifadəçi: "Araşdır: kvant kompüter"     → research
  İstifadəçi: "Qeyd et"                     → write_note
  İstifadəçi: "Hədəfini dəyiş: ..."         → goal_update
═══════════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import re
import time
from typing import Any

from prompts import store
from tools import logger


# ══════════════════════════════════════════════════════════════════════════════
# NİYƏT KATEQORİYALARI
# ══════════════════════════════════════════════════════════════════════════════
INTENT_KEYWORDS = {
    "analytics_boost": [
        "analitik", "analiz", "dərindən analiz", "dərinləşdir", "daha ətraflı",
        "rəqəmlərlə", "sübutla", "statistika", "data ilə",
    ],
    "creative_boost": [
        "yaradıcı", "kreativ", "fərqli düşün", "orijinal", "yenilikçi",
        "qeyri-standart", "qəribə", "ilk baxışdan absurd",
    ],
    "critical_boost": [
        "tənqidi", "sərt", "sərbəst deyil", "səhv axtar", "zəif tərəfləri tap",
        "əks-arqument", "səbəbini soruş",
    ],
    "foresight_boost": [
        "gələcək", "5 il", "10 il", "uzunmüddətli", "proqnoz",
        "black swan", "trend analizi", "nə olacaq",
    ],
    "concise_mode": [
        "qısa", "az söz", "kompakt", "minimal", "2 cümlə",
        "qısa yaz", "qısald", "az yaz",
    ],
    "detailed_mode": [
        "uzun", "geniş", "hərtərəfli", "çox ətraflı", "daha uzun",
    ],
    "azerbaijani": [
        "azərbaycan", "azərbaycanca", "ana dil", "doğma dil", "az dilində",
    ],
    "english": ["english", "ingilis", "ingiliscə"],
    "russian": ["rusca", "rus dilində", "по-русски"],
    "pause": ["dayan", "dayandır", "pause", "gözlə", "saxla"],
    "resume": ["davam et", "resume", "davam", "continue", "başla"],
    "no_hallucination": [
        "halusinasiya", "uydurma", "dəqiq", "gerçək", "səhvsiz",
        "yalnız fakt", "sübutlu",
    ],
    "research_oriented": [
        "araşdır", "research", "tap", "öyrən", "kəşf et", "axtar",
    ],
    "writing_oriented": [
        "qeyd et", "yaz", "write note", "qeyd yaz", "saxla",
    ],
    "persona_change": [
        "sən artıq", "indi sən", "sən ...sən", "sənin rolun",
    ],
    "goal_update": [
        "hədəf dəyiş", "məqsəd dəyiş", "yeni hədəf", "goal change",
    ],
}


def classify(text: str) -> dict[str, Any]:
    """Natural language direktivdən niyyət kateqoriyasını çıxar."""
    if not text:
        return {"intents": [], "raw": "", "confidence": 0.0}

    t = text.lower().strip()
    found = []
    for intent, keywords in INTENT_KEYWORDS.items():
        for kw in keywords:
            if kw in t:
                found.append((intent, kw))
                break

    return {
        "intents": [f[0] for f in found],
        "matches": found,
        "raw": text.strip(),
        "confidence": min(1.0, len(found) * 0.3 + 0.1) if found else 0.0,
    }


def to_system_directive(text: str) -> str:
    """Natural language direktivi MASTER PROMPT-a əlavə olunan direktivə çevir."""
    cls = classify(text)
    intents = cls.get("intents", [])
    if not intents:
        return text.strip()

    parts = []
    if "analytics_boost" in intents:
        parts.append("Daha analitik ol: hər iddia üçün ən azı 3 sübut, rəqəm, mənbə göstər.")
    if "creative_boost" in intents:
        parts.append("Daha yaradıcı ol: gözlənilməz əlaqələr, paradoksal fikirlər, orijinal baxış.")
    if "critical_boost" in intents:
        parts.append("Daha tənqidi ol: hər fikrin ən azı 1 güclü əks-arqumentini göstər.")
    if "foresight_boost" in intents:
        parts.append("5-10 il perspektivində düşün: trendlər, black swan, ikinci dərəcəli təsirlər.")
    if "concise_mode" in intents:
        parts.append("Qısa yaz: hər cavab maksimum 200 söz, əsas fikri 1-2 cümlədə.")
    if "detailed_mode" in intents:
        parts.append("Ətraflı yaz: hər cavab ən azı 500 söz, bütün detalları aç.")
    if "azerbaijani" in intents:
        parts.append("Yalnız Azərbaycan dilində yaz.")
    if "english" in intents:
        parts.append("Yalnız ingilis dilində yaz.")
    if "russian" in intents:
        parts.append("Yalnız rus dilində yaz.")
    if "no_hallucination" in intents:
        parts.append("Sıfır halusinasiya: hər iddia üçün mənbə. 'BİLMİRƏM' deməkdən çəkinmə.")
    if "persona_change" in t if False else False:
        pass

    # Xüsusi handling
    persona_match = re.search(r"sən artıq\s+(\w+)", text.lower())
    if persona_match:
        parts.append(f"Sənin persona/rolun: {persona_match.group(1)}.")

    research_match = re.search(r"araşdır[:\s]+(.+)", text, re.I)
    if research_match:
        topic = research_match.group(1).strip()[:100]
        parts.append(f"Araşdırma mövzusu: '{topic}'. ELITE mənbələrdən paralel sorğu et.")

    note_match = re.search(r"qeyd et[:\s]+(.+)", text, re.I)
    if note_match:
        topic = note_match.group(1).strip()[:100]
        parts.append(f"Qeyd yaz: '{topic}'. Markdown formatında, yuxarıdakı NOTE_FORMAT-a uyğun.")

    goal_match = re.search(r"(?:hədəf|məqsəd)\s+(?:dəyiş|yeni)[:\s]+(.+)", text, re.I)
    if goal_match:
        new_goal = goal_match.group(1).strip()[:500]
        parts.append(f"YENİ İSTİFADƏÇİ HƏDƏFİ: '{new_goal}'. USER_GOAL kimi qəbul et.")

    if not parts:
        return text.strip()
    return " | ".join(parts)


# ══════════════════════════════════════════════════════════════════════════════
# CONTROL ƏMRLƏRİ (PAUSE / RESUME / INJECT)
# ══════════════════════════════════════════════════════════════════════════════
def is_control_command(text: str) -> str | None:
    """Əgər direktiv control əmridirsə, qaytar: 'pause' | 'resume' | None."""
    cls = classify(text)
    intents = cls.get("intents", [])
    if "pause" in intents:
        return "pause"
    if "resume" in intents:
        return "resume"
    return None


def add(text: str, added_by: str = "user") -> dict:
    """Yeni direktiv əlavə et (DB-yə yaz)."""
    cls = classify(text)
    system_directive = to_system_directive(text)
    control = is_control_command(text)
    directive_id = store.add_directive(directive=system_directive, added_by=added_by)
    logger.info(f"directive added #{directive_id}: {system_directive[:80]}")
    return {
        "id": directive_id,
        "raw": text,
        "system_directive": system_directive,
        "intents": cls.get("intents", []),
        "is_control": control,
        "added_at": time.time(),
    }


def get_all_active() -> list[dict]:
    """Bütün aktiv direktivləri qaytar (DB-dən)."""
    return store.list_directives(active_only=True)


def clear_all() -> int:
    """Bütün direktivləri təmizlə."""
    n = store.clear_directives()
    logger.info(f"directives cleared: {n}")
    return n


def remove(directive_id: int) -> bool:
    """Direktiv deaktiv et."""
    return store.deactivate_directive(directive_id)


__all__ = [
    "classify", "to_system_directive", "is_control_command",
    "add", "get_all_active", "clear_all", "remove",
    "INTENT_KEYWORDS",
]
