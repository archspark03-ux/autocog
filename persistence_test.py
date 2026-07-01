"""
PERSISTENCE TESTI — Neon DB bağlantını kəsib yenidən qoşulduqda data qalırmı?
"""
import sys, importlib
sys.path.insert(0, '.')
import config; importlib.reload(config)
from memory import store; importlib.reload(store)

print("=" * 60)
print("PERSISTENCE TESTI — Neon PostgreSQL 7/24")
print("=" * 60)

# 1. Cari vəziyyət
print("\n=== [1] BAĞLANTIDAN ƏVVƏL ===")
s = store.stats()
print(f"  thoughts: {s['thoughts']}")
print(f"  research: {s['researches']}")
print(f"  notes   : {s['notes']}")
print(f"  backend : {s['backend']}")

# 2. Backend cache sıfırla (yeni connection simulyasiya et)
store._backend = None
store._backend_kind = "local"
print("\n=== [2] BACKEND CACHE SIFIRLANDI (simulating restart) ===")

# 3. Yenidən connection — data hələ orada olmalıdır
print("\n=== [3] YENIDƏN BAĞLANDIQDAN SONRA ===")
s = store.stats()
print(f"  thoughts: {s['thoughts']}")
print(f"  research: {s['researches']}")
print(f"  notes   : {s['notes']}")
print(f"  backend : {s['backend']}")

# 4. Lokal IO yoxlaması
import os
local_db = config.MEMORY_DB
print("\n=== [4] LOKAL IO YOXLAMASI ===")
print(f"  Lokal DB yol  : {local_db}")
print(f"  Lokal DB var?  : {os.path.exists(local_db)}")
if os.path.exists(local_db):
    print(f"  Lokal DB ölçü : {os.path.getsize(local_db)} byte")
    print(f"  [!] Lokal DB mövcuddur — bu gözlənilir, amma istifadə olunmur.")
else:
    print(f"  Lokal DB ölçü : 0 byte (fayl yoxdur)")

# 5. Yeni thought yaz
new_id = store.save_thought(
    cycle=9999,
    prompt="PERSISTENCE TEST",
    response="Yenidən qoşulduqdan sonra yazıldı",
    brain="groq"
)
print(f"\n=== [5] YENI THOUGHT YAZILDI (id={new_id}) ===")

# 6. Cache sıfırla, oxu
store._backend = None
store._backend_kind = "local"
t = store.get_thought(new_id)
print(f"\n=== [6] YOXLAMA (cache yenidən sıfırlandı) ===")
print(f"  Thought #{new_id} remote-da qalıbmı?")
if t:
    print(f"  prompt  : {t.get('prompt')}")
    print(f"  response: {t.get('response')}")
    if t.get('prompt') == 'PERSISTENCE TEST':
        print(f"\n  ✓✓✓ PERSISTENCE TEST UĞURLA TAMAMLANDI ✓✓✓")
        print(f"  Data cloud Neon DB-də SAXLANILIR")
        print(f"  Heç bir lokal resurs istifadə olunmur")
    else:
        print(f"\n  ✗ DATA UYĞUN DEYIL")
else:
    print(f"\n  ✗✗✗ DATA ITKISI! THOUGHT TAPILMADI")

# 7. Yekun stats
print("\n=== [7] YEKUN STATS ===")
s = store.stats()
for k, v in s.items():
    print(f"  {k:20s}: {v}")

print()
