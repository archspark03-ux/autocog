"""Daemon status check."""
import sys, importlib
sys.path.insert(0, '.')
import config; importlib.reload(config)
from memory import store; importlib.reload(store)

s = store.stats()
print('=== HAZIRKI VƏZIYYƏT (Neon) ===')
for k, v in s.items():
    print(f'  {k:20s}: {v}')
print()
print('=== SON 3 DÜŞÜNCƏ ===')
for t in store.recent_thoughts(3):
    print(f'  #{t["id"]} cycle={t["cycle"]} brain={t["brain"]} tokens={t["tokens_in"]}->{t["tokens_out"]}')
    if t.get("response"):
        # show first 150 chars of response
        r = str(t["response"])[:150]
        print(f'      response: {r}...')
print()
print('=== SON 3 ARAŞDIRMA ===')
for r in store.recent_research(3):
    q = r.get("query", "")[:80]
    n = len(r.get("results", []))
    print(f'  #{r["id"]} cycle={r["cycle"]} src={r["source"]} items={n}')
    print(f'      query: {q}...')
print()
print('=== AÇIQ TAPŞIRIQLAR ===')
for tk in store.list_tasks('open', 10):
    print(f'  [P{tk["priority"]}] {tk["title"][:100]}')
