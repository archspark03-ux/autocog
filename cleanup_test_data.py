"""Test datasını Neon DB-dən təmizlə — yeni beyin loop-u üçün hazırlama."""
import sys, importlib
sys.path.insert(0, '.')
import config; importlib.reload(config)
from memory import store; importlib.reload(store)

print("=== TEST DATASINI TƏMIZLƏ (Neon) ===")
for table in ['thoughts', 'research', 'notes', 'tasks', 'metrics']:
    affected = store._exec(f'DELETE FROM {table}')
    print(f'  DELETE FROM {table:12s} -> {affected} sətir silindi')

# Sequence-ləri sıfırla
try:
    cur = store._backend.cursor()
    for seq in ['thoughts_id_seq', 'research_id_seq', 'notes_id_seq', 'tasks_id_seq', 'metrics_id_seq']:
        try:
            cur.execute(f'ALTER SEQUENCE {seq} RESTART WITH 1')
            print(f'  RESET {seq}')
        except Exception as e:
            print(f'  [skip] {seq}: {e}')
    store._backend.commit()
    cur.close()
except Exception as e:
    print(f'  [info] sequence reset: {e}')

# schema_version-u da saxla
print('\n=== YEKUN ===')
s = store.stats()
print(f'  thoughts    : {s["thoughts"]}')
print(f'  research    : {s["researches"]}')
print(f'  notes       : {s["notes"]}')
print(f'  open_tasks  : {s["open_tasks"]}')
print(f'  schema ver  : {s["schema_version"]}')
print()
print('OK Neon DB temizlendi, beyin loop-u ucun hazirdir')
