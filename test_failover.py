"""Failover test - 3 qatlı zəncir testi."""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from brain.client import make_fallback_chain, think_with_failover

print("=" * 60)
print("  3 QATLI FAILOVER TESTI")
print("=" * 60)

chain = make_fallback_chain()
print("\nFAILOVER ZƏNCIRI (prioritet sırası ilə):")
for i, b in enumerate(chain, 1):
    print(f"  {i}. {b.name:14s} -> {b.model}")

print("\n" + "-" * 60)
print("TEST 1: Sadə sual (Groq gözlənilir)")
print("-" * 60)
t0 = time.time()
r = think_with_failover("2+2 neçədir? Qısa cavab ver.", thinking=False, max_tokens=40)
ms = int((time.time() - t0) * 1000)
print(f"CAVAB    : {r['response'][:100].strip()}")
print(f"Beyin    : {r.get('brain')}")
print(f"Vaxt     : {ms}ms")
print(f"Tokenlər : {r.get('tokens_in')} -> {r.get('tokens_out')}")
for a in r.get("attempts", []):
    print(f"  Attempt: {a['brain']:12s} ok={a.get('ok')} {a.get('duration_ms', 0)}ms")

print("\n" + "-" * 60)
print("TEST 2: Dərin fikir sorğusu")
print("-" * 60)
t0 = time.time()
r = think_with_failover(
    "7/24 işləyən AI beynin ən böyük üstünlüyü nədir? 2-3 cümlədə cavab ver.",
    thinking=True,
    max_tokens=300,
)
ms = int((time.time() - t0) * 1000)
print(f"CAVAB    : {r['response'][:400].strip()}")
print(f"Beyin    : {r.get('brain')}")
print(f"Vaxt     : {ms}ms")
print(f"Tokenlər : {r.get('tokens_in')} -> {r.get('tokens_out')}")

print("\n" + "-" * 60)
print("TEST 3: Mürəkkəb plan sorğusu")
print("-" * 60)
t0 = time.time()
r = think_with_failover(
    "Mən Bakıda yaşayıram, 25 yaşım var, proqramçıyam. Maliyyə sahəsinə keçmək istəyirəm. "
    "3 il üçün qısa plan hazırla, JSON formatında.",
    thinking=True,
    max_tokens=800,
)
ms = int((time.time() - t0) * 1000)
print(f"CAVAB    : {r['response'][:600].strip()}")
print(f"Beyin    : {r.get('brain')}")
print(f"Vaxt     : {ms}ms")
print(f"Tokenlər : {r.get('tokens_in')} -> {r.get('tokens_out')}")

print("\n" + "=" * 60)
print("  TAMAMLANDI")
print("=" * 60)
