"""
config.py — Bütün konfiqurasiya burada.
Pulsuz limitsiz modellərin siyahısı (2026-06-30 tarixinə qədər).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import os
from pathlib import Path
from dotenv import load_dotenv

# .env faylını yüklə
ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

# ===== YOLLAR =====
MEMORY_DB = ROOT / "memory" / "brain.db"
NOTES_DIR = ROOT / "notes"
LOGS_DIR = ROOT / "logs"
NOTES_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# ===== EXTERNAL DB (Neon PostgreSQL) — 7/24 persistent storage =====
# Boşdursa → lokal SQLite (memory/brain.db)
# Doludursa → remote PostgreSQL (Neon.tech free tier: 0.5GB, auto-suspend)
# Format: postgresql://user:password@host/dbname?sslmode=require
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
USE_REMOTE_DB = bool(DATABASE_URL)
# Konsistent log fayl adı (gündəlik rotasiya üçün)
LOG_FILE = LOGS_DIR / "brain.log"

# ===== BİRİNCİ DƏRƏCƏLİ BEYİN — PULSUZ LİMİTSİZ =====
# Pollinations.ai — AÇIQ endpoint (text.pollinations.ai/openai) və ya
# sk_ key ilə gen.pollinations.ai/v1 (55+ modeldən bəziləri pulsuz işləyir)
#  - Açıq modellər (heç bir key): openai, openai-fast
#  - sk_ key ilə pulsuz: openai, mistral, qwen-coder, llama
#  - pk_ key ilə saatlıq 1 Pollen: claude-opus-4.7, gpt-5.4, gemini-search, perplexity-deep
POLLINATIONS = {
    "name": "Pollinations.ai (AÇIQ + sk_ key ilə 4 pulsuz model + pk_ ilə 55+)",
    "api_key": os.getenv("POLLINATIONS_API_KEY", "anonymous"),
    "base_url": os.getenv(
        "POLLINATIONS_BASE_URL",
        "https://gen.pollinations.ai/v1" if os.getenv("POLLINATIONS_API_KEY") and os.getenv("POLLINATIONS_API_KEY") != "anonymous" else "https://text.pollinations.ai/openai",
    ),
    "model": os.getenv("POLLINATIONS_MODEL", "openai"),  # ən etibarlı, hər yerdə işləyir
    "thinking_model": os.getenv("POLLINATIONS_THINKING_MODEL", "openai"),
    "free_tier": "Açıq: limitsiz (openai, openai-fast). sk_ key ilə: openai/mistral/qwen-coder/llama pulsuz, digər modellər Pollen tələb edir",
    "signup": "Açıq: heç bir qeydiyyat. Key üçün: https://enter.pollinations.ai/",
    "supports_thinking": True,
}

# Z.ai (Zhipu AI) - Çin platforması (backup, key lazımdır)
GLM = {
    "name": "Z.ai (Zhipu) — GLM-4.5-Flash + GLM-Z1-Air",
    "api_key": os.getenv("GLM_API_KEY", ""),
    "base_url": os.getenv("GLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4"),
    "model": os.getenv("GLM_MODEL", "glm-4.5-flash"),
    "thinking_model": os.getenv("GLM_THINKING_MODEL", "glm-z1-air"),
    "free_tier": "Pulsuz limitsiz (qeydiyyat, kart istəmir)",
    "signup": "https://bigmodel.cn/",
    "supports_thinking": True,
}

# ===== BACKUP BEYİNLƏR =====
# OpenRouter — 35+ pulsuz model bir yerdən
OPENROUTER = {
    "name": "OpenRouter (DeepSeek R2, Qwen3-235B, GLM-4.7, Llama 4)",
    "api_key": os.getenv("OPENROUTER_API_KEY", ""),
    "base_url": os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
    "model": "deepseek/deepseek-r2:free",
    "free_tier": "20 RPM, 50-200 RPD",
    "signup": "https://openrouter.ai/",
}

GROQ = {
    "name": "Groq (Llama 3.3 70B, Qwen3 32B — ultra-sürətli)",
    "api_key": os.getenv("GROQ_API_KEY", ""),
    "base_url": os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
    "model": "llama-3.3-70b-versatile",
    "free_tier": "30 RPM, 14400 RPD",
    "signup": "https://console.groq.com/",
}

CEREBRAS = {
    "name": "Cerebras (Qwen3 235B, Llama 3.3 70B — ən sürətli)",
    "api_key": os.getenv("CEREBRAS_API_KEY", ""),
    "base_url": os.getenv("CEREBRAS_BASE_URL", "https://api.cerebras.ai/v1"),
    "model": "qwen-3-235b-a22b-instruct-2507",
    "free_tier": "1M token/gün pulsuz",
    "signup": "https://cloud.cerebras.ai/",
}

DEEPSEEK = {
    "name": "DeepSeek (V4-Flash, R1 — çox ucuz, güclü)",
    "api_key": os.getenv("DEEPSEEK_API_KEY", ""),
    "base_url": os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    "model": "deepseek-chat",
    "thinking_model": "deepseek-reasoner",
    "free_tier": "5M pulsuz token + sonra $0.14/M",
    "signup": "https://platform.deepseek.com/",
}

OLLAMA = {
    "name": "Ollama (LOKAL — TAM LİMİTSİZ, offlayn)",
    "api_key": "ollama",  # lokal olduğu üçün
    "base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
    "model": os.getenv("OLLAMA_MODEL", "qwen3:8b"),
    "thinking_model": os.getenv("OLLAMA_THINKING_MODEL", "qwen3:14b"),
    "free_tier": "Tam limitsiz (sənin kompüterin)",
    "signup": "https://ollama.com/download",
}

# ===== ARAŞDIRMA ALƏTLƏRİ =====
TAVILY = {
    "name": "Tavily (AI agent-lər üçün web search + research)",
    "api_key": os.getenv("TAVILY_API_KEY", ""),
    "free_tier": "1000 credit/ay pulsuz",
    "signup": "https://app.tavily.com/",
}

FIRECRAWL = {
    "name": "Firecrawl (extract/crawl/agent — ən güclü scraper)",
    "api_key": os.getenv("FIRECRAWL_API_KEY", ""),
    "free_tier": "500 credit pulsuz",
    "signup": "https://firecrawl.dev/",
}

# ===== DAVRANIS =====
PRIMARY_BRAIN = os.getenv("PRIMARY_BRAIN", "pollinations")  # default: heç bir key istəmir
FALLBACK_BRAIN = os.getenv("FALLBACK_BRAIN", "pollinations")
DEEP_RESEARCH_EVERY_LOOP = os.getenv("DEEP_RESEARCH_EVERY_LOOP", "false").lower() == "true"
LOOP_INTERVAL_SECONDS = int(os.getenv("LOOP_INTERVAL_SECONDS", "300"))
USER_GOAL = os.getenv(
    "USER_GOAL",
    "Davamlı şəkildə düşün, araşdır, öyrən və qeydlər yaz. Mən olmayanda da inkişaf et.",
)

# Pollinations.ai dərin araşdırma modelləri
RESEARCH_MODEL = os.getenv("RESEARCH_MODEL", "gemini-search")  # built-in search ilə
DEEP_RESEARCH_MODEL = os.getenv("DEEP_RESEARCH_MODEL", "perplexity-deep")  # ən dərin

# Bütün beyinləri bir yerdə saxlamaq üçün lüğət
BRAINS = {
    "pollinations": POLLINATIONS,  # default — heç bir key istəmir
    "glm": GLM,
    "openrouter": OPENROUTER,
    "groq": GROQ,
    "cerebras": CEREBRAS,
    "deepseek": DEEPSEEK,
    "ollama": OLLAMA,
}


def get_brain(name: str) -> dict:
    """Verilmiş adda beyin konfiqurasiyasını qaytarır."""
    if name not in BRAINS:
        raise ValueError(f"Bilinməyən beyin: {name}. Mövcud: {list(BRAINS.keys())}")
    return BRAINS[name]


def available_brains() -> list[str]:
    """İstifadə üçün əlçatan beyinləri qaytarır.
    Pollinations həmişə 'var' (heç bir key istəmir)."""
    avail = ["pollinations"]  # default — həmişə işləyir
    for name, cfg in BRAINS.items():
        if name == "pollinations":
            continue
        if name == "ollama":
            avail.append(name)
        elif cfg.get("api_key"):
            avail.append(name)
    return avail


def active_brain_name() -> str:
    """İstifadə üçün aktiv beyin (əsas və ya fallback)."""
    if PRIMARY_BRAIN in available_brains():
        return PRIMARY_BRAIN
    if FALLBACK_BRAIN in available_brains():
        return FALLBACK_BRAIN
    return "pollinations"  # heç bir key yoxdursa belə işləyir (heç bir key istəmir)


def is_research_available() -> bool:
    """Tavily, Firecrawl və ya Pollinations (həmişə var)."""
    return True  # Pollinations həmişə var (gemini-search, perplexity-deep)


if __name__ == "__main__":
    print("🧠  AVTONOM BEYİN — KONFİQURASİYA")
    print("=" * 60)
    print(f"Əsas beyin : {PRIMARY_BRAIN}")
    print(f"Fallback   : {FALLBACK_BRAIN}")
    print(f"Aktiv      : {active_brain_name()}")
    print(f"Loop       : hər {LOOP_INTERVAL_SECONDS} saniyə")
    print(f"Araşdırma  : {'var' if is_research_available() else 'yoxdur'}")
    print("-" * 60)
    print("Mövcud beyinlər:")
    for name in available_brains():
        b = BRAINS[name]
        marker = " ⭐" if name == "pollinations" else ""
        print(f"  ✅ {name:12s} — {b['name']}{marker}")
        print(f"      Model: {b['model']}")
        print(f"      Pulsuz: {b['free_tier']}")
    print("-" * 60)
    print("Qeydiyyat linkləri (PULSUZ):")
    for name, b in BRAINS.items():
        print(f"  • {name:12s} → {b['signup']}")
    print(f"  • Tavily      → {TAVILY['signup']}")
    print(f"  • Firecrawl   → {FIRECRAWL['signup']}")
