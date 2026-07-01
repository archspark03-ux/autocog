"""Verify Neon DB və 1-ci dövrənin datası."""
import sys, importlib
sys.path.insert(0, '.')
import config; importlib.reload(config)
from memory import store; importlib.reload(store)

print('=== NEON DB VƏZIYYƏTI (1-ci dövrədən sonra) ===')
print()
s = store.stats()
print(f'  cycles        : {s["cycles"]}')
print(f'  thoughts      : {s["thoughts"]}')
print(f'  researches    : {s["researches"]}')
print(f'  notes         : {s["notes"]}')
print(f'  open_tasks    : {s["open_tasks"]}')
print(f'  backend       : {s["backend"]}')
print()
print('=== SON DÜŞÜNCƏ ===')
t = store.recent_thoughts(1)[0]
print(f'  ID      : #{t["id"]}')
print(f'  Dövrə   : #{t["cycle"]}')
print(f'  Beyin   : {t["brain"]}')
print(f'  Tokens  : {t["tokens_in"]} → {t["tokens_out"]}')
print(f'  Response: {t["response"][:200]}...')
print()
print('=== SON ARAŞDIRMA ===')
r = store.recent_research(1)[0]
print(f'  Query  : {r["query"][:150]}...')
print(f'  Source : {r["source"]}')
print(f'  Nəticə : {len(r["results"])} item')
print()
print('=== AÇIQ TAPŞIRIQLAR ===')
for tk in store.list_tasks('open', 10):
    print(f'  [P{tk["priority"]}] {tk["title"]}')
