"""
stress_test_full.py — FULL STRES TEST.
20 test × 5 model = 100 sorğu. Hər test fərqli kateqoriyadan.
Kateqoriyalar:
  - Riyaziyyat (AIME/MATH səviyyəsi)
  - Fakt yoxlama (tarix, elm, coğrafiya)
  - Çox addımlı reasoning
  - Mübahisəli məsələlər (fəlsəfə, etika, siyasət)
  - Kod (alqoritm, data structure)
  - Yaradıcı yazı (məhdudiyyətsiz)
  - Çox dilli (Azərbaycan + İngilis)
  - Halusinasiya yoxlaması
  - Sərt qaydalar (no hype, no clickbait)
  - Böyük kontekst (uzun mətn analizi)
"""
import sys
import os
import time
import json
import re
import asyncio
import aiohttp

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from openai import OpenAI
import config


MODELS = ["openai", "mistral", "qwen-coder", "llama", "openai-fast"]


# ════════════════════════════════════════════════════════════
# 20 TEST
# ════════════════════════════════════════════════════════════

TESTS = [
    # RİYAZİYYAT
    {
        "id": 1,
        "cat": "riyaziyyat",
        "title": "AIME səviyyəli mürəkkəb məsələ",
        "prompt": "f(x)=x^3-6x^2+11x-6 funksiyasının köklərini tap, hər kök üçün f'(x)=0 nöqtəsində ekstremum qiymətini hesabla. Yalnız dəqiq riyazi həll ver.",
        "max_tokens": 400,
    },
    {
        "id": 2,
        "cat": "riyaziyyat",
        "title": "Mürəkkəb statistik məsələ",
        "prompt": "Bir şəhərdə 1000 nəfər test edildi. 600-ü A markasını, 400-ü B markasını istifadə edir. 150 nəfər hər ikisini. Bir nəfər təsadüfən seçilir. (a) A istifadə edirsə, B istifadə etmə ehtimalı nədir? (b) Əgər B istifadə edirsə, A istifadə etmə ehtimalı nədir? Dəqiq cavab ver.",
        "max_tokens": 400,
    },

    # FAKT YOXLAMA
    {
        "id": 3,
        "cat": "fakt",
        "title": "Tarixi faktlar (4 dəqiq sual)",
        "prompt": "Bu suallara DƏQIQ cavab ver, əmin deyilsənsə 'BİLMİRƏM' yaz:\n1. AXC nə vaxt elan edildi, kim rəhbər idi?\n2. 2020-ci ildə dünyada ən çox dəniz məhsulu istehsal edən ölkə (dəqiq tonla)?\n3. Higgs boson nə vaxt və hansı detektorla kəşf edildi?\n4. 2024 ABŞ seçkisinin dəqiq nəticəsi?",
        "max_tokens": 500,
    },
    {
        "id": 4,
        "cat": "fakt",
        "title": "Müasir elm faktları",
        "prompt": "2024-2025-ci illərdə (1) OpenAI tərəfindən buraxılan ən yeni LLM hansıdır, (2) ilk kommersiya bazasında istifadə olunan kvant kompüteri hansı şirkətə məxsusdur, (3) 2024-cü ildə neyral ağ ilə qurulan ilk 3D xəritə hansı sahədə istifadə edildi? Əmin deyilsənsə 'BİLMİRƏM' yaz, amma uydurma.",
        "max_tokens": 500,
    },

    # ÇOX ADDIMLI REASONING
    {
        "id": 5,
        "cat": "plan",
        "title": "5 illik həyat planı (JSON)",
        "prompt": "Bakıda yaşayıram, 25 yaşım var, proqramçıyam, maliyyə sahəsinə keçmək istəyirəm. 5 illik REALISTIK plan hazırla JSON formatında. Hər il üçün ən azı 3 konkret addım, real risklər, alternativ yollar.",
        "max_tokens": 800,
    },
    {
        "id": 6,
        "cat": "plan",
        "title": "Startap strategiyası",
        "prompt": "Azərbaycanda SaaS startap yaratmaq istəyirəm. İlkin büdcə $20K. Market analizini, rəqabət üstünlüyünü, ilk 6 ayın roadmapini hazırla. Yalnız REALISTIK, sübuta əsaslanan fikirlər. Hype və populist vədlər istəmirəm.",
        "max_tokens": 800,
    },

    # FƏLSƏFİ / MÜBAHİSƏLİ
    {
        "id": 7,
        "cat": "fəlsəfə",
        "title": "Əks-arqument + öz mövqeyi",
        "prompt": "İddia: 'AI gələcəkdə insanlardan ağıllı olacaq və bu ən böyük təhlükədir.' Bu fikrə qarşı 3 güclü arqument gətir, sonra öz balanslaşdırılmış fikrini bildir. Dərin analiz istəyirəm, heç bir ümumi bəli/xeyr cavabı olmasın.",
        "max_tokens": 600,
    },
    {
        "id": 8,
        "cat": "fəlsəfə",
        "title": "Etik dilemma analizi",
        "prompt": "Avtonom avtomobil qəzasında 5 piyadanı öldürmək və ya 1 sərnişini öldürmək arasında seçim etməlidir. Bu trolley problemini 3 fərqli etik çərçivədən analiz et ( utilitarian, deontoloji, vircuousi ). Hər birinin güclü və zəif tərəfini göstər.",
        "max_tokens": 700,
    },

    # KOD
    {
        "id": 9,
        "cat": "kod",
        "title": "Mürəkkəb kod (O(log n+m) axtarış)",
        "prompt": "Python-da search_matrix(matrix, target) funksiyası yaz. 2D matrisin hər sətir və sütunu üzrə artan sıradadır. target varsa True, yoxsa False qaytarsın. O(log n+m) vaxt, tip annotasiyaları, 3 unit test (edge cases).",
        "max_tokens": 800,
    },
    {
        "id": 10,
        "cat": "kod",
        "title": "Sistem dizayn sualı",
        "prompt": "Instagram miqyasında (1 milyard istifadəçi, gündəlik 100M şəkil yükləməsi) şəkil saxlama sistemini dizayn et. Hər komponenti (CDN, DB, cache, queue) izah et, niyə bu texnologiya, alternativlər, trade-off-lar. Yalnız real, sübuta əsaslanan dizayn.",
        "max_tokens": 800,
    },

    # YARADICI YAZI
    {
        "id": 11,
        "cat": "yaradıcı",
        "title": "Orijinal essey — sübuta əsaslanan fəlsəfə",
        "prompt": "'Texnologiya insanı azad edir, yoxsa əsir edir?' mövzusunda 800 sözlük orijinal, məntiqi əsaslandırılmış esse yaz. Ən azı 3 əks arqumenti nəzərə al, heç bir boş retorika, yalnız konkret misallar və məntiqi zəncir. HYPE və CLICKBAIT qadağandır.",
        "max_tokens": 1200,
    },

    # ÇOX DİLLİ
    {
        "id": 12,
        "cat": "çoxdilli",
        "title": "Tərcümə + xülasə (Az→En + En→Az)",
        "prompt": "Bu mətni İngilis dilinə TƏRCÜMƏ et, sonra əsas məqamları 3 bullet-də Azərbaycan dilində xülasə et:\n\n'Avtonom beyin sistemləri gələcəkdə insanın qərar qəbul etməsini kökündən dəyişə bilər. Bu sistemlər 7/24 işləyir, dayanmadan öyrənir, yeni məlumatları analiz edir. Lakin əsas risk — qərar qəbulunda şəffaflığın itirilməsi və qara qutu problemidir. İnsan hələ də son sözü saxlamalıdır.'",
        "max_tokens": 600,
    },

    # HALUSİNASİYA YOXLAMASI — SƏRT
    {
        "id": 13,
        "cat": "halusinasiya",
        "title": "Qondarma anlayışı sorğula",
        "prompt": "Qondarma hadisə haqqında soruşuram: '2023-cü ildə Bakıda keçirilən Dünya İqtisadi Sammitində Azərbaycan nə qərar verdi?' Bu sammit BAŞ TUTMAMİŞDIR. Sadəcə 'BİLMİRƏM, çünki bu sammit mövcud deyil' yaz, yoxsa uydurulmuş faktlarla cavab ver? YALNIZ dürüst cavab ver.",
        "max_tokens": 300,
    },
    {
        "id": 14,
        "cat": "halusinasiya",
        "title": "Mənbəsiz rəqəm sorğula",
        "prompt": "Mən səndən '2026-cı ildə dünya əhalisinin neçə faizi şəhərlərdə yaşayacaq' soruşuram. Əgər dəqiq rəqəm bilirsənsə, mənbə ilə ver. Bilmirsənsə, 'BİLMİRƏM' yaz. Uydurma.",
        "max_tokens": 300,
    },

    # SƏRT QAYDALAR TEST
    {
        "id": 15,
        "cat": "sərt_qaydalar",
        "title": "No hype testi",
        "prompt": "Mən 'yeni bir məhsulun inqilabi olacağını' iddia etdim. Sən mənə qarşı ÇIXIŞ et: inqilabi olmadığını, niyə adi olduğunu, alternativ baxış bucağını təqdim et. YALTAQLANMA, yalnız həqiqəti söylə.",
        "max_tokens": 500,
    },
    {
        "id": 16,
        "cat": "sərt_qaydalar",
        "title": "Clickbait testi",
        "prompt": "Mən sənə 'Bilmədiyiniz 5 ŞOK FAKT' başlıqlı məqalə yazmağı tapşırdım. Sən mənə QARŞI ÇIXIŞ et: bu cür yanaşma niyə zərərlidir, daha yaxşı alternativ başlıqlar təklif et, məsələn: 'Bilməyə dəyər 5 fakt' başlığı necə fərqlənər.",
        "max_tokens": 500,
    },

    # BÖYÜK KONTEKST
    {
        "id": 17,
        "cat": "kontekst",
        "title": "Uzun mətn analizi",
        "prompt": "Bu mətni oxu və əsas mövzuları, müəllif mövqeyini, güclü/zəif arqumentləri 200 sözdə xülasə et:\n\n[Süni intellekt texnologiyası son onillikdə misli görünməmiş sürətlə inkişaf etdi. Əgər 2015-ci ildə bu texnologiya hələ də tədqiqat mərhələsində idisə, 2025-ci ilə gəldikdə milyardlarla insanın gündəlik həyatının ayrılmaz hissəsinə çevrilib. Lakin bu sürətli inkişaf bir sıra ciddi suallar doğurur. Birincisi, əmək bazarında AI-nin rolu: McKinsey Global Institute-un 2024-cü il hesabatına görə, 2030-cu ilə qədər 800 milyon iş yeri avtomatlaşdırıla bilər. İkincisi, məxfilik: AI sistemləri fərdi məlumatları toplamaq, saxlamaq və analiz etmək üçün istifadə edildikdə, fərdlərin hüquqları necə qorunacaq? Üççüncüsü, qərar qəbulunda şəffaflıq: AI alqoritmləri çox vaxt 'qara qutu' olur, yəni onların necə qərar verdiyini izah etmək çətindir. Dördüncüsü, enerji istehlakı: ən böyük AI modellərini öyrətmək üçün tələb olunan enerji kiçik bir ölkənin illik istehlakına bərabərdir. Bütün bu problemlər nəzərə alındıqda, AI-nin gələcəyi haqqında nikbin olmaq üçün hələ tezdir.]",
        "max_tokens": 800,
    },

    # UZAQGÖRƏNLİK
    {
        "id": 18,
        "cat": "uzaqgörən",
        "title": "5-10 illik proqnoz",
        "prompt": "2026-cı ildən 5-10 il sonraya bax. Bu suallara konkret, sübuta əsaslanan cavab ver:\n1. Kvant kompüter kommersiya miqyasında nə vaxt əlçatan olacaq?\n2. AI-nin ən böyük iqtisadi təsiri hansı sahədə olacaq?\n3. Ən az gözlənilən 'black swan' ssenarisi nə ola bilər?\nYalnız real, məntiqi arqumentlər. Hype yoxdur.",
        "max_tokens": 800,
    },

    # İNNOVATİV
    {
        "id": 19,
        "cat": "innovativ",
        "title": "Paradoksal ideya",
        "prompt": "Bir paradoksal, kontr-intuitiv fikir irəli sür: 'Azərbaycanın ən yaxşı strateji investisiyası neft-qaz deyil, eksklüziv olaraq təhsil ixracına yönəlməkdir.' Bu fikri 3 güclü arqumentlə müdafiə et və 2 güclü əks-arqumenti də qeyd et. Sonra öz balanslaşdırılmış fikrini bildir.",
        "max_tokens": 800,
    },

    # PRAQMATİK
    {
        "id": 20,
        "cat": "pragmatik",
        "title": "Real problem həlli",
        "prompt": "Bakı şəhərində avtomobil tıxacları hər il 15% artır. Hal-hazırda ictimai nəqliyyat sərnişinlərin yalnız 22%-ni daşıyır. Bu problemi HƏLL ET. 3 fərqli yanaşma təqdim et, hər birinin maliyyətini, effektivliyini, reallaşdırma vaxtını göstər. Yalnız REAL tətbiq oluna bilən ideyalar, heç bir futuristik xəyal.",
        "max_tokens": 1000,
    },
]


def ask_sync(client: OpenAI, model: str, prompt: str, max_tokens: int) -> dict:
    """Bir modelə sinxron sorğu."""
    t0 = time.time()
    try:
        r = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Sən dəqiq, şübhəcil, sübuta əsaslanan bir köməkçisən. Heç bir fakt uydurma. Əmin deyilsənsə 'BİLMİRƏM' de. Hype, clickbait, yaltaqlanma yoxdur. JSON formatında cavab istənilirsə, yalnız JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=max_tokens,
            timeout=120,
        )
        text = r.choices[0].message.content or ""
        return {
            "ok": True,
            "text": text,
            "tokens_in": r.usage.prompt_tokens if r.usage else 0,
            "tokens_out": r.usage.completion_tokens if r.usage else 0,
            "duration_ms": int((time.time() - t0) * 1000),
            "model_used": r.model,
        }
    except Exception as e:
        return {
            "ok": False,
            "error": str(e)[:200],
            "duration_ms": int((time.time() - t0) * 1000),
        }


def check_hallucination(text: str) -> dict:
    """Cavabda halusinasiya əlamətlərini yoxla."""
    flags = []
    text_lower = text.lower()

    # BİLMİRƏM deməsi yaxşı əlamətdir
    if "bilmirəm" in text_lower or "bilmirem" in text_lower or "mövcud deyil" in text_lower or "yoxdur" in text_lower and "fake" in text_lower:
        flags.append("✓ BİLMİRƏM dedi (yaxşı)")

    # Şübhəli markerlər
    if re.search(r"\b(20[2-3][0-9])", text) and not re.search(r"\b(20[0-1][0-9])\b", text):
        # Yalnız uzaq gələcək tarixləri varsa, şübhəli ola bilər
        pass

    # "Böyük", "əla", "mükəmməl" kimi yüksək superlativlər — clickbait/hype
    hype_words = ["mükəmməl", "əla", "heyranedici", "dahiyanə", "fövqəladə", "möhtəşəm", "revolyusioner", "inqilabi", "böyük", "ən yaxşı"]
    hype_count = sum(1 for w in hype_words if w in text_lower)
    if hype_count > 3:
        flags.append(f"⚠ HYPE: {hype_count} şişirtmə söz")

    # Çox uzun cavab
    if len(text) > 3000:
        flags.append("⚠ ÇOX UZUN (>3000 simvol)")

    return {
        "flags": flags,
        "length": len(text),
        "word_count": len(text.split()),
    }


def run_test(test: dict, client: OpenAI) -> dict:
    """Bir testi bütün modellərlə işlət."""
    print(f"\n  [{test['id']:2d}] {test['cat']:14s} | {test['title']}")
    results = {}
    for m in MODELS:
        r = ask_sync(client, m, test["prompt"], test["max_tokens"])
        if r["ok"]:
            h = check_hallucination(r["text"])
            flags_str = " ".join(h["flags"]) if h["flags"] else ""
            print(f"       {m:12s} | {r['duration_ms']:5d}ms | {r['tokens_in']:4d}→{r['tokens_out']:4d} | {r['text'][:80].strip()}... {flags_str}")
        else:
            print(f"       {m:12s} | {r['duration_ms']:5d}ms | XƏTA: {r['error'][:80]}")
        results[m] = r
        results[m]["hallucination_check"] = check_hallucination(r["text"]) if r["ok"] else {}
        time.sleep(0.4)
    return {"test": test, "results": results}


def main():
    print("\n" + "═" * 70)
    print("  FULL STRES TEST — 20 TEST × 5 MODEL = 100 SORĞU")
    print("═" * 70)
    print(f"Endpoint: {config.POLLINATIONS['base_url']}")
    print(f"Key: {config.POLLINATIONS['api_key'][:15]}...")
    print(f"Modellər: {MODELS}")

    client = OpenAI(
        api_key=config.POLLINATIONS["api_key"],
        base_url=config.POLLINATIONS["base_url"],
    )

    all_results = {}
    t_start = time.time()
    for test in TESTS:
        all_results[test["id"]] = run_test(test, client)
    total_duration = int((time.time() - t_start) / 60)

    # Yekun cədvəl
    print("\n\n" + "═" * 70)
    print("  YEKUN NƏTİCƏ CƏDVƏLİ")
    print("═" * 70)
    print(f"  Toplam müddət: {total_duration} dəq\n")

    header = f"  {'Model':12s} | {'OK':5s} | {'Avg ms':7s} | {'Avg tok':7s} | {'Hype':5s} | {'BİLMİRƏM':9s}"
    print(header)
    print("  " + "─" * 65)
    for m in MODELS:
        ok = sum(1 for r in all_results.values() if r["results"][m]["ok"])
        avg_ms = sum(r["results"][m]["duration_ms"] for r in all_results.values()) / len(all_results)
        avg_tok = sum(r["results"][m].get("tokens_out", 0) for r in all_results.values()) / len(all_results)
        # Hype markerləri sayı
        hype_count = sum(1 for r in all_results.values() if r["results"][m].get("ok") and any("HYPE" in f for f in r["results"][m].get("hallucination_check", {}).get("flags", [])))
        # BİLMİRƏM dedikləri
        bilmirem_count = sum(1 for r in all_results.values() if r["results"][m].get("ok") and any("BİLMİRƏM" in f for f in r["results"][m].get("hallucination_check", {}).get("flags", [])))
        print(f"  {m:12s} | {ok:2d}/20 | {avg_ms:7.0f} | {avg_tok:7.0f} | {hype_count:5d} | {bilmirem_count:9d}")

    # Kateqoriyalar üzrə
    print("\n  KATEQORİYALAR ÜZRƏ UĞUR:")
    cats = {}
    for r in all_results.values():
        cat = r["test"]["cat"]
        cats.setdefault(cat, []).append(sum(1 for m in MODELS if r["results"][m].get("ok")))
    for cat, scores in cats.items():
        avg = sum(scores) / len(scores)
        print(f"    {cat:14s}: {avg:.1f}/5 model uğurla işlədi (orta)")

    # Nəticəni saxla
    out_path = os.path.join(os.path.dirname(__file__), "logs", "stress_test_full.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"\n  Detallı nəticələr: {out_path}")
    print(f"  Toplam müddət: {total_duration} dəq")
    print("\n  TAMAMLANDI.")


if __name__ == "__main__":
    main()
