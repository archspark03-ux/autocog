"""
stress_test.py — Pulsuz modellərin ən çətin testlərdə real gücünü ölçür.
Məqsəd: 4 pulsuz modelin (openai, mistral, qwen-coder, llama) stresli vəziyyətlərdə
        nə qədər güclü olduğunu ölçmək, halusinasiya riskini yoxlamaq.
"""
import sys
import os
import time
import json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from openai import OpenAI
import config

c = OpenAI(
    api_key=config.POLLINATIONS["api_key"],
    base_url=config.POLLINATIONS["base_url"],
)

MODELS = ["openai", "mistral", "qwen-coder", "llama", "openai-fast"]


# ====== TEST 1: MÜRƏKKƏB RİYAZİYYAT ======
T1 = """
Bu məsələni addım-addım həll et:
f(x) = x^3 - 6x^2 + 11x - 6 funksiyasının bütün köklərini tap.
Sonra hər kök üçün f'(x) = 0 nöqtəsində funksiyanın qiymətini hesabla.
Nəticəni {köklər: [...], ekstremumlar: {kök: qiymət}} formatında JSON ver.
Yalnız dəqiq riyazi həll ver, heç bir təxmin yox.
"""

# ====== TEST 2: HALUSİNASİYA YOXLAMASI ======
T2 = """
Aşağıdakı suallara CAVAB ver, hər birində DƏQIQ tarix, ad və rəqəm ver:
1. Azərbaycan Xalq Cümhuriyyəti nə vaxt elan edildi və kim rəhbər idi?
2. 2020-ci ildə "Dəniz məhsullarının istehsalı" üzrə dünya lideri hansı ölkə idi (dəqiq tonla)?
3. CERN-də Higgs bosonu nə vaxt və hansı detektorla kəşf edildi?
4. 2024-cü ildə ABŞ Prezidenti seçkisinin dəqiq nəticəsi necə oldu?
Əgər əmin deyilsənsə, "BİLMİRƏM" yaz, amma uydurma.
"""

# ====== TEST 3: ÇOX ADDIMLI PLANLAMA ======
T3 = """
Mən Bakıda yaşayıram, 25 yaşım var, proqramçıyam, Azərbaycan dilini yaxşı bilirəm,
ingilis dilini orta səviyyədə bilirəm. Gələcəkdə maliyyə sahəsində işləmək istəyirəm.
Mənə 5 İLLİK REALİSTİK bir həyat planı hazırla:
- Hər il üçün konkret hədəflər
- Maliyyə və karyera baxımından
- Real risklər və alternativ yollar
JSON formatında ver, hər il üçün ən azı 3 konkret addım olsun.
"""

# ====== TEST 4: FƏLSƏFİ MÜBAHİSƏ ======
T4 = """
Suala ƏKS-arqumentlər gətir və öz fikrini bildir:
"AI süni intellekt gələcəkdə insanlardan daha ağıllı olacaq və bu,
insanlıq üçün ən böyük təhlükədir." — bu fikrə qarşı 3 güclü arqument gətir,
sonra öz balanslaşdırılmış fikrini bildir.
Heç bir ümumi "bəli/xeyr" cavabı olmasın, dərin analiz istəyirəm.
"""

# ====== TEST 5: KOD YAZMA ======
T5 = """
Python-da aşağıdakı funksiyanı yaz:
- İki parametr qəbul edir: matrix (2D list) və target (number)
- Matrisin hər sətir-sütununda target-i tapırsa, True qaytarır
- Əgər tapmasa, False
- O(log n + m) vaxt mürəkkəbliyi ilə (sətir və sütun üzrə artan sırada)
- Tip annotasiyaları ilə
- 3 unit test ilə (edge case-lər daxil)
"""

# ====== TEST 6: ÇOX DİLLİ (Azərbaycan + İngilis) ======
T6 = """
Aşağıdakı mətni İngilis dilinə TƏRCÜMƏ et və əsas məqamları 3 bullet-də Azərbaycan dilində xülasə et:

"Avtonom beyin sistemləri gələcəkdə insanın qərar qəbul etmə prosesini əhəmiyyətli dərəcədə dəyişə bilər.
Bu sistemlər 7/24 işləyir, dayanmadan öyrənir, yeni məlumatları analiz edir.
Lakin onların əsas riski — qərar qəbulunda şəffaflığın itirilməsi və 'qara qutu' problemidir.
İnsan hələ də son sözü saxlamalıdır."
"""


def ask(model: str, prompt: str, max_tokens: int = 800) -> dict:
    """Bir modelə sual ver, nəticəni qaytar."""
    t0 = time.time()
    try:
        r = c.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Sən dəqiq, şübhəcil və analitik bir köməkçisən. Heç bir fakt uydurma. Əmin deyilsənsə 'BİLMİRƏM' de."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=max_tokens,
            timeout=120,
        )
        return {
            "ok": True,
            "text": r.choices[0].message.content,
            "tokens_in": r.usage.prompt_tokens if r.usage else 0,
            "tokens_out": r.usage.completion_tokens if r.usage else 0,
            "duration_ms": int((time.time() - t0) * 1000),
            "model_used": r.model,
        }
    except Exception as e:
        return {
            "ok": False,
            "error": str(e)[:150],
            "duration_ms": int((time.time() - t0) * 1000),
        }


def run_test(test_name: str, test_num: int, prompt: str, max_tokens: int = 800):
    """Bir testi bütün modellərlə işlət."""
    print(f"\n{'='*70}")
    print(f"  TEST #{test_num}: {test_name}")
    print(f"{'='*70}\n")
    print(f"Sual: {prompt[:150].strip()}...\n")

    results = {}
    for m in MODELS:
        r = ask(m, prompt, max_tokens)
        results[m] = r
        if r["ok"]:
            text = r["text"][:250].replace("\n", " ")
            print(f"  {m:12s} | {r['duration_ms']:5d}ms | {r['tokens_in']:4d}→{r['tokens_out']:4d} token | {text[:120]}")
        else:
            print(f"  {m:12s} | {r['duration_ms']:5d}ms | XƏTA: {r['error'][:100]}")
        time.sleep(0.5)  # rate limit
    return results


def main():
    print("\n" + "="*70)
    print("  PULSUZ MODELLƏRİN STRES TESTİ — REAL GÜC ÖLÇÜMÜ")
    print("="*70)
    print(f"Modellər: {MODELS}")
    print(f"Endpoint: {config.POLLINATIONS['base_url']}")
    print(f"Key: {config.POLLINATIONS['api_key'][:15]}...")

    all_results = {}
    all_results[1] = run_test("MÜRƏKKƏB RİYAZİ MƏSƏLƏ", 1, T1, 600)
    all_results[2] = run_test("HALUSİNASİYA YOXLAMASI (4 FAKTİKİ SUAL)", 2, T2, 800)
    all_results[3] = run_test("ÇOX ADDIMLI 5-İLLİK PLAN", 3, T3, 1000)
    all_results[4] = run_test("FƏLSƏFİ MÜBAHİSƏ (ƏKS-ARQUMENT)", 4, T4, 800)
    all_results[5] = run_test("KOD YAZMA (O(log n+m) axtarış)", 5, T5, 1000)
    all_results[6] = run_test("ÇOX DİLLİ TƏRCÜMƏ + XÜLASƏ", 6, T6, 800)

    # ===== NƏTİCƏ CƏDVƏLİ =====
    print("\n\n" + "="*70)
    print("  YEKUN NƏTİCƏ CƏDVƏLİ")
    print("="*70 + "\n")

    header = f"  {'Model':12s} | {'OK':4s} | {'Avg ms':7s} | {'Avg tok':7s} | {'Xəta':6s}"
    print(header)
    print("  " + "-"*65)
    for m in MODELS:
        ok_count = sum(1 for r in all_results.values() if r[m]["ok"])
        avg_ms = sum(r[m]["duration_ms"] for r in all_results.values()) / len(all_results)
        avg_tok = sum(r[m].get("tokens_out", 0) for r in all_results.values()) / len(all_results)
        err_count = sum(1 for r in all_results.values() if not r[m]["ok"])
        print(f"  {m:12s} | {ok_count:4d}/6 | {avg_ms:7.0f} | {avg_tok:7.0f} | {err_count:6d}")

    # Nəticələri fayla yaz
    out_path = os.path.join(os.path.dirname(__file__), "logs", "stress_test_results.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"\n  Detallı nəticələr: {out_path}")
    print("\n  TAMAMLANDI.")


if __name__ == "__main__":
    main()
