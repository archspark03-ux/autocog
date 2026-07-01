"""
research/searcher.py — Dərin araşdırma.
İki mənbəni birləşdirir:
  • Tavily      — /search, /extract, /research (AI-uyğun)
  • Firecrawl   — /scrape, /crawl, /extract, /agent (güclü scraper)
  • Heç biri yoxdursa — sadə HTTP istifadə edir.
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import json
import re
from typing import Any
from urllib.parse import quote_plus

import httpx

import config
from tools import logger
from research.elite_sources import elite_research, available_sources as _elite_available, ELITE_SOURCES


def _strip_html(html: str) -> str:
    """Çox sadə HTML təmizləyici (fallback)."""
    html = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.S | re.I)
    html = re.sub(r"<style[^>]*>.*?</style>", " ", html, flags=re.S | re.I)
    html = re.sub(r"<[^>]+>", " ", html)
    html = re.sub(r"\s+", " ", html)
    return html.strip()


class Researcher:
    """Çox-mənbəli araşdırmaçı."""

    def __init__(self):
        self.tavily_key = config.TAVILY["api_key"]
        self.firecrawl_key = config.FIRECRAWL["api_key"]
        self.timeout = httpx.Timeout(60.0, connect=15.0)

    @property
    def has_tavily(self) -> bool:
        return bool(self.tavily_key)

    @property
    def has_firecrawl(self) -> bool:
        return bool(self.firecrawl_key)

    def available_sources(self) -> list[str]:
        s = ["elite:" + x for x in _elite_available()]
        if self.has_tavily:
            s.append("tavily")
        if self.has_firecrawl:
            s.append("firecrawl")
        if not (s or self.has_tavily or self.has_firecrawl):
            s.append("raw-http")
        return s

    # ===== Tavily =====
    def tavily_search(self, query: str, max_results: int = 5) -> list[dict]:
        """Tavily /search — AI-uyğun axtarış."""
        if not self.has_tavily:
            return []
        try:
            r = httpx.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": self.tavily_key,
                    "query": query,
                    "max_results": max_results,
                    "search_depth": "advanced",
                    "include_answer": True,
                    "include_raw_content": False,
                },
                timeout=self.timeout,
            )
            r.raise_for_status()
            data = r.json()
            results = data.get("results", [])
            answer = data.get("answer")
            if answer:
                results.insert(0, {
                    "title": "Tavily cavabı",
                    "url": "",
                    "content": answer,
                    "source": "tavily-answer",
                })
            return results
        except Exception as e:
            logger.warn(f"Tavily xətası: {e}")
            return []

    def tavily_extract(self, urls: list[str]) -> list[dict]:
        """Tavily /extract — URL-lərdən təmiz mətn çıxar."""
        if not self.has_tavily or not urls:
            return []
        try:
            r = httpx.post(
                "https://api.tavily.com/extract",
                json={"api_key": self.tavily_key, "urls": urls[:5]},
                timeout=self.timeout,
            )
            r.raise_for_status()
            return r.json().get("results", [])
        except Exception as e:
            logger.warn(f"Tavily extract xətası: {e}")
            return []

    def tavily_research(self, query: str) -> dict:
        """Tavily /research — çox-mənbəli sintez (uzun çəkir)."""
        if not self.has_tavily:
            return {}
        try:
            r = httpx.post(
                "https://api.tavily.com/research",
                json={"api_key": self.tavily_key, "input": query},
                timeout=httpx.Timeout(180.0, connect=15.0),
            )
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.warn(f"Tavily research xətası: {e}")
            return {}

    # ===== Firecrawl =====
    def firecrawl_scrape(self, url: str) -> dict:
        """Firecrawl /scrape — tək səhifənin təmiz markdown-ı."""
        if not self.has_firecrawl:
            return {}
        try:
            r = httpx.post(
                "https://api.firecrawl.dev/v1/scrape",
                json={"url": url, "formats": ["markdown"]},
                headers={"Authorization": f"Bearer {self.firecrawl_key}"},
                timeout=self.timeout,
            )
            r.raise_for_status()
            return r.json().get("data", {})
        except Exception as e:
            logger.warn(f"Firecrawl scrape xətası: {e}")
            return {}

    def firecrawl_search(self, query: str, limit: int = 5) -> list[dict]:
        """Firecrawl /search — axtarış + scrape bir yerdə."""
        if not self.has_firecrawl:
            return []
        try:
            r = httpx.post(
                "https://api.firecrawl.dev/v1/search",
                json={"query": query, "limit": limit},
                headers={"Authorization": f"Bearer {self.firecrawl_key}"},
                timeout=self.timeout,
            )
            r.raise_for_status()
            return r.json().get("data", [])
        except Exception as e:
            logger.warn(f"Firecrawl search xətası: {e}")
            return []

    # ===== Fallback — sadə HTTP =====
    def raw_http(self, url: str) -> str:
        try:
            r = httpx.get(
                url,
                headers={"User-Agent": "Mozilla/5.0 (AvtonomBeyin/0.1)"},
                timeout=self.timeout,
                follow_redirects=True,
            )
            r.raise_for_status()
            return _strip_html(r.text)[:5000]
        except Exception as e:
            logger.warn(f"HTTP xətası ({url}): {e}")
            return ""

    # ===== ELITE mənbələr (pulsuz, key istəmir) =====
    def elite_research(self, query: str, sources: list[str] | None = None, max_results: int = 3) -> dict:
        """
        Elite mənbələrdən paralel sorğu:
        arxiv, openalex, semantic_scholar, pubmed, sec_edgar,
        worldbank, github, hackernews, wikidata, opencorporates.

        Həmişə işləyir — heç bir key tələb etmir.
        """
        logger.research(f"elite sorğu: \"{query}\" (mənbələr: {sources or 'default'})")
        out = elite_research(query, sources=sources, max_results=max_results, parallel=True)
        total = sum(s.get("count", 0) for s in out.get("sources", {}).values())
        logger.research(f"elite tapıldı: {total} nəticə ({len(out.get('sources', {}))} mənbə)")
        return out

    # ===== Yüksək səviyyəli API =====
    def research(self, query: str, deep: bool = False) -> dict:
        """
        Sorğunu araşdır. Nəticələri qaytarır.
        deep=True olduqda həm axtarış, həm də extract edilir.
        """
        logger.research(f"araşdırma başladı: \"{query}\"")
        results: list[dict[str, Any]] = []
        summary = ""
        source = "none"

        if self.has_tavily:
            source = "tavily"
            results = self.tavily_search(query, max_results=8 if deep else 5)
            # Deep mode: ilk 3 URL-ni extract et
            if deep and results:
                urls = [r["url"] for r in results if r.get("url")][:3]
                extracted = self.tavily_extract(urls)
                for ext in extracted:
                    for r in results:
                        if r.get("url") == ext.get("url"):
                            r["content"] = ext.get("raw_content", r.get("content", ""))
                            break

        elif self.has_firecrawl:
            source = "firecrawl"
            results = self.firecrawl_search(query, limit=8 if deep else 5)
            # Firecrawl artıq scrape edir, ayrıca extract lazım deyil

        else:
            # Fallback — DuckDuckGo HTML axtarışı (qeyri-rəsmi)
            source = "duckduckgo"
            try:
                r = httpx.get(
                    f"https://html.duckduckgo.com/html/?q={quote_plus(query)}",
                    headers={"User-Agent": "Mozilla/5.0"},
                    timeout=self.timeout,
                )
                # Sadə parse
                for m in re.finditer(
                    r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?'
                    r'class="result__snippet"[^>]*>(.*?)</a>',
                    r.text,
                    re.S,
                ):
                    results.append({
                        "title": _strip_html(m.group(2)),
                        "url": m.group(1),
                        "content": _strip_html(m.group(3)),
                        "source": "ddg",
                    })
                    if len(results) >= (8 if deep else 5):
                        break
            except Exception as e:
                logger.warn(f"DDG xətası: {e}")

        if results and results[0].get("source") == "tavily-answer":
            summary = results[0].get("content", "")

        logger.research(f"tapıldı: {len(results)} nəticə ({source})")
        return {
            "query": query,
            "source": source,
            "results": results,
            "summary": summary,
        }


if __name__ == "__main__":
    r = Researcher()
    print("Mövcud mənbələr:", r.available_sources())
    if r.has_tavily or r.has_firecrawl or True:
        out = r.research("GLM-4.5 Z.ai yeni versiya 2026")
        print(f"Nəticələr: {len(out['results'])}")
        for x in out["results"][:3]:
            print(f"  • {x.get('title','?')[:80]}")
            print(f"    {x.get('url','')}")
