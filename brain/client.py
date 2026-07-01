"""
brain/client.py — Çox-provayder LLM müştəri + AVTOMATİK FAILOVER.
Hər hansı OpenAI-uyğun API-yə qoşula bilir:
  • Pollinations (sk_ key ilə PULSUZ: openai, mistral, qwen-coder, llama)
  • Z.ai GLM-4.5-Flash
  • OpenRouter (DeepSeek R2, Qwen3-235B, GLM-4.7 ...)
  • Groq (Llama 3.3 70B)
  • Cerebras (Qwen3 235B)
  • DeepSeek (V4-Flash, R1)
  • Ollama (LOKAL — TAM LİMİTSİZ)

Düşünmə rejimi: thinking=true olduqda modeldən chain-of-thought istəyir.
Failover: bir beyin xəta verərsə, növbəti beyinə avtomatik keçir.
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import time
from typing import Any

from openai import OpenAI

import config
from tools import logger

class Brain:
    """Beyin müştərisi — OpenAI-uyğun, çox-provayder."""

    def __init__(self, name: str | None = None):
        self.name = name or config.active_brain_name()
        self.cfg = config.get_brain(self.name)
        self.client = OpenAI(
            api_key=self.cfg["api_key"] or "ollama",
            base_url=self.cfg["base_url"],
        )
        # Thinking modeli varsa onu da yadda saxla
        self.thinking_model = self.cfg.get("thinking_model", self.cfg["model"])
        self.model = self.cfg["model"]

    def _pick_model(self, thinking: bool) -> str:
        return self.thinking_model if thinking else self.model

    def think(
        self,
        prompt: str,
        system: str = "",
        thinking: bool = True,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        timeout: int = 300,
    ) -> dict[str, Any]:
        """
        Beyinə sual ver. thinking=True olduqda dərin düşünmə rejimi işləyir.
        Qaytarır: {"response": str, "thinking": str, "tokens_in": int, "tokens_out": int, "duration_ms": int}
        """
        model = self._pick_model(thinking)
        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        t0 = time.time()
        try:
            logger.think(f"[{self.name}] sorğu → {model} ({len(prompt)} simvol)")
            # Qwen3 thinking: "think" parametri ilə Ollama-da işləyir,
            # digər OpenAI-uyğun API-lərdə system prompt-a /think əlavə edirik.
            extra: dict[str, Any] = {"timeout": timeout}
            if self.name == "ollama":
                extra["extra_body"] = {"think": thinking}
            elif thinking and self.name in ("glm", "pollinations"):
                # Pollinations-da bəzi modellər avtomatik düşünür (Claude, Gemini Thinking, ...)
                # OpenAI modelləri üçün sadəcə temperature aşağı salınır
                if self.name == "pollinations" and "openai" in model.lower():
                    # OpenAI üçün thinking parametri yoxdur, sadəcə dərin sorğu veririk
                    pass
                elif self.name == "glm" and "z1" in self.thinking_model.lower():
                    pass  # GLM-Z1 artıq thinking modelidir
                else:
                    extra["extra_body"] = {"thinking": {"type": "enabled"}}

            resp = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **extra,
            )
        except Exception as e:
            logger.error(f"[{self.name}] xəta: {e}")
            return {
                "response": f"[xəta: {e}]",
                "thinking": "",
                "tokens_in": 0,
                "tokens_out": 0,
                "duration_ms": int((time.time() - t0) * 1000),
            }

        duration_ms = int((time.time() - t0) * 1000)
        msg = resp.choices[0].message

        # GLM və bəzi modellərdə ayrıca reasoning_content sahəsi olur
        thinking_text = ""
        response_text = msg.content or ""
        if hasattr(msg, "reasoning_content") and msg.reasoning_content:
            thinking_text = msg.reasoning_content
        # Qwen3 thinking: cavabın əvvəlində <think>...</think> bloku ola bilər
        if not thinking_text and response_text.startswith("<think>"):
            end = response_text.find("</think>")
            if end != -1:
                thinking_text = response_text[: end + len("</think>")]
                response_text = response_text[end + len("</think>"):].strip()

        usage = resp.usage
        tokens_in = usage.prompt_tokens if usage else 0
        tokens_out = usage.completion_tokens if usage else 0

        logger.think(
            f"[{self.name}] cavab ← {duration_ms}ms · {tokens_in}→{tokens_out} token"
        )
        return {
            "response": response_text,
            "thinking": thinking_text,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "duration_ms": duration_ms,
        }

    def info(self) -> str:
        return f"{self.name} → {self.model} (thinking: {self.thinking_model})"


def make_brain(name: str | None = None) -> Brain:
    """Aktiv beyin yarat (fallback ilə)."""
    if name and name in config.available_brains():
        return Brain(name)
    return Brain()


from functools import lru_cache


@lru_cache(maxsize=1)
def make_fallback_chain() -> tuple:
    """Bütün əlçatan beyinləri əhəmiyyət sırası ilə qaytarır (singleton cache).
    primary → secondary → tertiary → fallback.
    OpenAI client hər dəfə yenidən yaradılmır (resource leak yox)."""
    chain: list = []
    seen: set = set()
    # .env-dən sıra
    order = [
        os.getenv("PRIMARY_BRAIN", "pollinations"),
        os.getenv("SECONDARY_BRAIN", ""),
        os.getenv("TERTIARY_BRAIN", ""),
        os.getenv("FALLBACK_BRAIN", "pollinations"),
    ]
    for name in order:
        if not name or name in seen:
            continue
        seen.add(name)
        if name in config.available_brains():
            try:
                chain.append(Brain(name))
            except Exception:
                pass
    # Hələ də boşdursa, pollinations əlavə et
    if not chain:
        chain.append(Brain("pollinations"))
    return tuple(chain)


def think_with_failover(
    prompt: str,
    system: str = "",
    thinking: bool = True,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    timeout: int = 300,
) -> dict[str, Any]:
    """Bütün beyinləri sına, işləyən ilk beyindən cavab al.
    Qaytarır: {"response", "thinking", "brain", "tokens_in", "tokens_out", "duration_ms", "attempts": [...]}
    """
    chain = make_fallback_chain()
    attempts: list[dict] = []
    for brain in chain:
        try:
            r = brain.think(
                prompt=prompt,
                system=system,
                thinking=thinking,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
            )
            attempts.append({
                "brain": brain.name,
                "ok": r["response"] and not r["response"].startswith("[xəta"),
                "duration_ms": r["duration_ms"],
            })
            if r["response"] and not r["response"].startswith("[xəta"):
                r["brain"] = brain.name
                r["attempts"] = attempts
                return r
        except Exception as e:
            attempts.append({"brain": brain.name, "ok": False, "error": str(e)[:80]})
    # Heç bir beyin işləmədi
    return {
        "response": "[bütün beyinlər xəta verdi]",
        "thinking": "",
        "brain": "none",
        "tokens_in": 0,
        "tokens_out": 0,
        "duration_ms": 0,
        "attempts": attempts,
    }


if __name__ == "__main__":
    b = make_brain()
    print("Beyin:", b.info())
    print("Test sorğusu göndərilir...")
    r = b.think("Bir cümlədə özünü təsvir et. Sən kimsən?", thinking=False, max_tokens=200)
    print("Cavab:", r["response"][:300])
    print("Tokenlər:", r["tokens_in"], "→", r["tokens_out"])
