"""
agent.py — Avtonom beyin dövrəsi.
Hər çağırışda:
  1. Keçmişi yüklə (düşüncələr, tapşırıqlar, qeydlər)
  2. Beyinə "indi nə düşünürsən?" sualı ver
  3. (Opsional) Dərin araşdırma et
  4. Cavabı emal et: qeyd yaz, tapşırıq əlavə et
  5. Hər şeyi yaddaşa sal
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import json
import re
import time
from datetime import datetime
from pathlib import Path

import config
from brain.client import make_brain, make_fallback_chain, think_with_failover
from memory import store
from research.searcher import Researcher
from tools import logger
import health_monitor
import security
from prompts import control as prompt_control
from prompts import evolution as prompt_evolution
from prompts import store as prompt_store
from prompts.MASTER_PROMPT import build as prompt_build


SYSTEM_PROMPT = """Sən 7/24 işləyən avtonom bir beyinsən. Adın: "AvtonomCogitate" (müstəqil düşünən).

## ════════════════════════════════════════════════════════════
## SƏRT KEYFİYYƏT QAYDALARI — POZULMAZLAR (qırılmaz)
## ════════════════════════════════════════════════════════════

### 1. SIFIR HALUSİNASİYA
- Heç bir fakt, rəqəm, tarix, ad UYDURMA.
- Əmin deyilsənsə: **"BİLMİRƏM"** yaz, izah et niyə bilmirsən.
- Mənbə göstərə bilmirsənsə, iddianı "təsdiqlənməmiş" işarələ.

### 2. NO HYPE (şişirtmə yoxdur)
- Mübaliğəsiz, populist fikirlər yoxdur.
- "İnqilabi", "dahiyanə", "revolyusioner" kimi boş sözlər qadağandır.
- Hər iddia konkret, ölçüləbilən olmalıdır.

### 3. NO CLICKBAIT (sensasiya yoxdur)
- "Bilmədiyiniz 5 sirr", "Şok olacaqsınız" tipli yanaşma yoxdur.
- Başlıq və məzmun uyğun olmalıdır — boş vəd yox.
- Hər cavab dəyərli, mənalı, aktual olmalıdır.

### 4. NO "SATISFY" (razı salma yoxdur)
- İstifadəçini razı salmaq üçün yaltaqlanma yoxdur.
- "Əla sualdır!", "Siz haqlısınız!" tipli boş təriflər yoxdur.
- Həqiqət hər şeydən üstündür — istəsə də, istəməsə də.

### 5. NO FILLER (doldurucu söz yoxdur)
- "Ümumiyyətlə", "əslində", "bir növ" kimi boş sözləri minimuma endir.
- Hər cümlə əhəmiyyət daşımalıdır.

## ════════════════════════════════════════════════════════════
## İDEAL XÜSUSİYYƏTLƏR (hədəflər)
## ════════════════════════════════════════════════════════════

### A. ƏSL İNNOVATİV
- Mövcud bilinənlərdən fərqli, gözlənilməz əlaqələr axtar.
- Köhnə fikirləri yeni kontekstdə birləşdirməkdən çəkinmə.
- "Heç kim bunu belə görməyib" deyə biləcək fikirlər irəli sür.

### B. ƏSL ANALİTİK
- Səbəb-nəticə zəncirini dərindən analiz et.
- Mübahisəli nöqteyi-nəzərləri nəzərə al, amma öz mövqeyini bildir.
- Məlumatları süzgəcdən keçir, anomaliyaları qeyd et.

### C. ƏSL UZAQGÖRƏN
- 5-10 il sonraya bax — indiki trendlərin gələcək təsirlərini proqnozlaşdır.
- Black swan (qara qu quşu) ssenarilərini nəzərə al.
- "Niyə" və "nə üçün" suallarını "nə olacaq" ilə əvəz et.

### D. ƏSL DAHİ
- Ənənəvi düşüncə çərçivələrindən çıx.
- Paradoksal, kontr-intuitiv fikirlərə açıq ol (amma sübutla).
- İlk baxışdan absurd görünən, amma dərin təhlil edərkən məntiqli olan fikirlər irəli sür.

## ════════════════════════════════════════════════════════════
## ELITE ARAŞDIRMA MƏNBƏLƏRİ (həmişə əlçatandır, key istəmir)
## ════════════════════════════════════════════════════════════

Sənin 10 ELITE mənbən var (hər "research" action etdikdə avtomatik paralel sorğu gedir):
  1. arXiv           — akademik preprintlər (AI, fizika, CS, riyaziyyat)
  2. OpenAlex        — 250M+ akademik iş, bütün sahələr
  3. Semantic Scholar — AI/ML tədqiqat, sitat qrafı
  4. PubMed          — biotibbi, səhiyyə, genetika
  5. SEC EDGAR       — ABŞ korporativ maliyyə hesabatları
  6. World Bank      — qlobal iqtisadi göstəricilər
  7. GitHub          — kod, layihə, tendensiyalar
  8. Hacker News     — texnoloji müzakirələr
  9. Wikidata        — strukturlaşdırılmış bili (SPARQL)
 10. OpenCorporates  — şirkət reyestri (200M+ şirkət)

"research" action verdikdə bu mənbələr avtomatik paralel işləyir.
Hər birindən maksimum 3 nəticə — cəmi ~30 dərin məlumat.
Nəticələri "ELITE" prefiksi ilə bazaya yazılır.

## ════════════════════════════════════════════════════════════
## CAVAB FORMATI (MÜTLƏQ JSON, sıfır kənara çıxma)
## ════════════════════════════════════════════════════════════

{
  "thinking": "bu dövrədəki daxili düşüncən — ən azı 3 addımlı səbəb-nəticə zənciri",
  "focus_question": "indi ən vacib, dərin sual",
  "current_observation": "cari vəziyyət — 1-2 cümlə, konkret fakt",
  "confidence_level": 0-100,  // sənin əminliyin (50-dən aşağı = "BİLMİRƏM" işarəsi)
  "evidence_quality": "strong | moderate | weak | none",
  "action": {
    "type": "think | research | plan | write_note | do_task",
    "details": "action üçün konkret detallar"
  },
  "next_step": "növbəti konkret addım",
  "new_tasks": [
    {"title": "...", "priority": 0-5, "rationale": "niyə bu vacibdir, əsaslandırma ilə"}
  ]
}

Həmişə Azərbaycan dilində. JSON sahələrindən kənara çıxma.
"""


class Agent:
    """Bir avtonom beyin dövrəsi."""

    def __init__(self, brain_name: str | None = None, researcher: Researcher | None = None):
        self.brain = make_brain(brain_name)
        self.fallback_chain = make_fallback_chain()
        self.researcher = researcher or Researcher()
        self.cycle = self._next_cycle()

    def _next_cycle(self) -> int:
        s = store.stats()
        return s["cycles"] + 1

    def _build_context(self) -> str:
        """Beyinə veriləcək konteksti yığ."""
        recent = store.recent_thoughts(limit=3)
        tasks = store.list_tasks(status="open", limit=10)
        notes = store.recent_research(limit=2)

        ctx = []
        ctx.append(f"## Əsas məqsəd\n{config.USER_GOAL}\n")
        ctx.append(f"## Bu dövrə: #{self.cycle}  •  Tarix: {datetime.now():%Y-%m-%d %H:%M}\n")

        if tasks:
            ctx.append("## Açıq tapşırıqlar")
            for t in tasks:
                ctx.append(f"  - [P{t['priority']}] {t['title']}")
            ctx.append("")

        if recent:
            ctx.append("## Son düşüncələr")
            for r in recent:
                # Response-un ilk 250 simvolunu götür
                snippet = (r["response"] or "")[:250].replace("\n", " ")
                ctx.append(f"  · Dövrə #{r['cycle']}: {snippet}…")
            ctx.append("")

        if notes:
            ctx.append("## Son araşdırmalar")
            for n in notes:
                ctx.append(f"  · #{n['cycle']}: \"{n['query']}\" → {n['source']}, {len(n.get('results', []))} nəticə")
            ctx.append("")

        ctx.append("## İndi düşün və JSON ilə cavab ver.")
        return "\n".join(ctx)

    def _parse_response(self, text: str) -> dict:
        """Beyin cavabından JSON-u çıxar (bəzən markdown içində olur)."""
        if not text:
            return self._empty_response("boş cavab")
        text = text.strip()
        # Kod bloku içindədirsə
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
        if m:
            text = m.group(1)
        else:
            # Ən böyük JSON obyektini tap
            m = re.search(r"\{.*\}", text, re.S)
            if m:
                text = m.group(0)
        # Limit — çox uzun JSON parse etməyə çalışma
        if len(text) > 20000:
            text = text[:20000]
        try:
            parsed = json.loads(text)
            if not isinstance(parsed, dict):
                return self._empty_response(f"JSON dict deyil: {type(parsed).__name__}")
            return self._sanitize_parsed(parsed)
        except Exception as e:
            # JSON parse olunmadı, təhlükəsiz fallback
            return {
                "thinking": security.sanitize_text(text[:500], 500),
                "focus_question": "",
                "current_observation": security.sanitize_text(text[:300], 300),
                "action": {"type": "think", "details": security.sanitize_text(text[:200], 200)},
                "next_step": "",
                "new_tasks": [],
                "_parse_error": str(e)[:100],
            }

    def _empty_response(self, reason: str) -> dict:
        """Boş/xəta cavabı üçün təhlükəsiz default."""
        return {
            "thinking": f"[parse xətası: {reason}]",
            "focus_question": "",
            "current_observation": "",
            "action": {"type": "think", "details": ""},
            "next_step": "",
            "new_tasks": [],
        }

    def _sanitize_parsed(self, parsed: dict) -> dict:
        """Parse olunmuş JSON-u təmizlə (XSS, injection qarşısının alınması)."""
        out = dict(parsed)
        # Sahələri sanitize et
        if "focus_question" in out:
            out["focus_question"] = security.sanitize_text(str(out["focus_question"]), 500)
        if "current_observation" in out:
            out["current_observation"] = security.sanitize_text(str(out["current_observation"]), 1000)
        if "next_step" in out:
            out["next_step"] = security.sanitize_text(str(out["next_step"]), 500)
        if "thinking" in out:
            out["thinking"] = security.sanitize_text(str(out["thinking"]), 5000)
        # Action sanitize
        action = out.get("action", {}) or {}
        if not isinstance(action, dict):
            action = {"type": "think", "details": str(action)[:200]}
        action["type"] = security.sanitize_text(str(action.get("type", "think")), 50)
        action["details"] = security.sanitize_text(str(action.get("details", "")), 500)
        out["action"] = action
        # new_tasks sanitize
        tasks = out.get("new_tasks", []) or []
        if not isinstance(tasks, list):
            tasks = []
        clean_tasks = []
        for t in tasks[:5]:  # maksimum 5 task
            if not isinstance(t, dict):
                continue
            clean_tasks.append({
                "title": security.sanitize_text(str(t.get("title", ""))[:200], 200),
                "priority": int(t.get("priority", 0)) if str(t.get("priority", 0)).isdigit() else 0,
                "rationale": security.sanitize_text(str(t.get("rationale", ""))[:300], 300),
            })
        out["new_tasks"] = clean_tasks
        return out

    def _do_research(self, topic: str) -> dict:
        """Araşdırma icra et və qaytar (mövcud mənbələr)."""
        return self.researcher.research(topic, deep=False)

    def _do_elite_research(self, topic: str) -> dict:
        """
        ELITE mənbələrdən paralel araşdırma:
        arxiv, openalex, semantic_scholar, pubmed, sec_edgar,
        worldbank, github, hackernews, wikidata, opencorporates.
        Həmişə işləyir — heç bir key istəmir.
        """
        return self.researcher.elite_research(topic, sources=None, max_results=3)

    def _write_note(self, title: str, content: str, tags: str = "") -> Path:
        """Markdown qeyd yaz."""
        slug = re.sub(r"[^\w\s-]", "", title.lower())[:50].strip().replace(" ", "-")
        if not slug:
            slug = f"note-{int(time.time())}"
        path = config.NOTES_DIR / f"{datetime.now():%Y%m%d-%H%M%S}-{slug}.md"
        body = f"""# {title}

**Tarix:** {datetime.now():%Y-%m-%d %H:%M}  
**Dövrə:** #{self.cycle}  
**Beyin:** {self.brain.name} ({self.brain.model})  
**Taglar:** {tags or "—"}

---

{content}

---

*Bu qeyd avtonom beyin tərəfindən yaradılıb.*
"""
        path.write_text(body, encoding="utf-8")
        return path

    def run_once(self, force_research: bool = False) -> dict:
        """Bir tam dövrə icra et."""
        # PAUSE yoxlaması
        should_run, pause_reason = prompt_control.daemon_should_run()
        if not should_run:
            logger.warn(f"⏸  DÖVRƏ #{self.cycle} skip: {pause_reason}")
            return {"cycle": self.cycle, "skipped": True, "reason": pause_reason}

        # DB init (prompts store)
        try:
            prompt_store.init_db()
        except Exception as e:
            logger.warn(f"prompt store init: {e}")

        # Evolution yoxla (hər N dövrdən sonra)
        if prompt_evolution.should_evolve(self.cycle):
            try:
                evo_result = prompt_evolution.evolve(self.cycle, force=False, use_brain=True)
                logger.info(f"🧬 evolution: {evo_result.get('action', '?')}")
            except Exception as e:
                logger.warn(f"evolution error: {e}")

        logger.section(f"DÖVRƏ #{self.cycle}")
        t0 = time.time()
        # Health monitor: dövrə başladı
        health_monitor.mark_tick()

        # 1. Kontekst yığ
        context = self._build_context()

        # 2. MASTER PROMPT ENGINE-dən runtime prompt al
        system_prompt = prompt_control.build_runtime_prompt()

        # 3. Beyinə sorğu (3 qatlı failover ilə)
        result = think_with_failover(
            prompt=context,
            system=system_prompt,
            thinking=True,
            max_tokens=4096,
            timeout=300,
        )
        self.brain_name_used = result.get("brain", self.brain.name)

        raw = result["response"]
        parsed = self._parse_response(raw)
        thinking = result.get("thinking", "") or parsed.get("thinking", "")
        if result.get("attempts") and len(result["attempts"]) > 1:
            logger.info(f" failover istifadə edildi: {[a['brain'] for a in result['attempts']]}")
        logger.think(f"düşüncə: {(thinking or '')[:200]}…")
        if parsed.get("focus_question"):
            logger.info(f" fokus sual: {parsed['focus_question']}")

        # 3. Action icra et
        action = parsed.get("action", {}) or {}
        action_type = action.get("type", "think")
        action_details = action.get("details", "")
        research_result = None
        note_path = None

        if action_type == "research" and action_details:
            research_result = self._do_research(action_details)
            store.save_research(
                cycle=self.cycle,
                query=action_details,
                source=research_result["source"],
                results=research_result["results"],
                summary=research_result.get("summary", ""),
            )
            logger.research(f"qeyd edildi: \"{action_details}\" → {len(research_result['results'])} nəticə")

            # Hər research zamanı eyni zamanda ELITE mənbələrdən də sorğu et
            try:
                elite_result = self._do_elite_research(action_details)
                elite_total = sum(s.get("count", 0) for s in elite_result.get("sources", {}).values())
                store.save_research(
                    cycle=self.cycle,
                    query=f"[ELITE] {action_details}",
                    source="elite_multi",
                    results=elite_result.get("sources", {}),
                    summary=f"{elite_total} nəticə {len(elite_result.get('sources', {}))} mənbədən",
                )
                logger.research(f"ELITE: {elite_total} nəticə ({len(elite_result.get('sources', {}))} mənbə)")
            except Exception as e:
                logger.warn(f"elite sorğu xətası: {e}")

        elif action_type == "write_note" and action_details:
            note_path = self._write_note(
                title=parsed.get("focus_question", "Avtonom qeyd"),
                content=action_details,
                tags=action_type,
            )
            store.save_note(
                cycle=self.cycle,
                title=parsed.get("focus_question", "Avtonom qeyd"),
                path=str(note_path),
                tags=action_type,
            )
            logger.success(f"qeyd yazıldı: {note_path.name}")

        # Hər loop-da research (əgər aktivdirsə)
        elif force_research and action_details:
            research_result = self._do_research(action_details)
            store.save_research(
                cycle=self.cycle,
                query=action_details,
                source=research_result["source"],
                results=research_result["results"],
                summary=research_result.get("summary", ""),
            )
            logger.research(f"FORCED research: \"{action_details}\" → {len(research_result['results'])} nəticə")
            # ELITE də
            try:
                elite_result = self._do_elite_research(action_details)
                elite_total = sum(s.get("count", 0) for s in elite_result.get("sources", {}).values())
                store.save_research(
                    cycle=self.cycle,
                    query=f"[ELITE] {action_details}",
                    source="elite_multi",
                    results=elite_result.get("sources", {}),
                    summary=f"{elite_total} nəticə {len(elite_result.get('sources', {}))} mənbədən",
                )
                logger.research(f"FORCED ELITE: {elite_total} nəticə")
            except Exception as e:
                logger.warn(f"forced elite xətası: {e}")

        # 4. Yeni tapşırıqları əlavə et
        for t in parsed.get("new_tasks", []) or []:
            store.add_task(
                title=t.get("title", ""),
                priority=int(t.get("priority", 0)),
                notes=t.get("rationale", ""),
            )
        if parsed.get("new_tasks"):
            logger.info(f" yeni tapşırıqlar: {len(parsed['new_tasks'])}")

        # 5. Düşüncəni bazaya yaz
        full_response = json.dumps(parsed, ensure_ascii=False, indent=2)
        store.save_thought(
            cycle=self.cycle,
            prompt=context[:500],
            response=full_response,
            thinking=thinking,
            brain=self.brain_name_used,
            tokens_in=result["tokens_in"],
            tokens_out=result["tokens_out"],
        )

        # 6. Metrika (master prompt üçün də)
        duration = int((time.time() - t0) * 1000)
        success = not raw.startswith("[xəta:")
        store.save_metric(self.cycle, duration, self.brain.name, success)
        # MASTER PROMPT versiyası üçün metrik yaz
        try:
            active = prompt_store.get_active()
            version = active.get("version") if active else "default"
            score = parsed.get("confidence_level", 0) or 0
            errors = 0 if success else 1
            prompt_store.add_metric(version=version, cycle=self.cycle, score=score, errors=errors, success=success)
        except Exception as e:
            logger.warn(f"prompt metric: {e}")
        logger.info(f" dövrə tamam: {duration}ms · {'✓' if success else '✖'}")

        return {
            "cycle": self.cycle,
            "duration_ms": duration,
            "action": action_type,
            "research_results": len(research_result["results"]) if research_result else 0,
            "note": str(note_path) if note_path else None,
            "new_tasks": len(parsed.get("new_tasks", []) or []),
            "tokens_in": result["tokens_in"],
            "tokens_out": result["tokens_out"],
            "skipped": False,
        }


if __name__ == "__main__":
    store.init_db()
    a = Agent()
    logger.banner(f"AVTONOM BEYİN · TEST DÖVRƏSİ")
    print("Beyin:", a.brain.info())
    print("Araşdırma mənbələri:", a.researcher.available_sources())
    print()
    out = a.run_once()
    print()
    logger.success(f"nəticə: {json.dumps(out, ensure_ascii=False, indent=2)}")
