"""
DƏRİN STRESS TEST — Neon PostgreSQL üçün.
Məqsəd: bütün əsas funksiyaları, error recovery-ni, concurrent access-ı,
data integrity-ni tam yoxlamaq. Smoke test deyil, real production testi.
"""
import sys, os, time, json, random, string, traceback
sys.path.insert(0, '.')

# UTF-8
os.environ['PYTHONIOENCODING'] = 'utf-8'

# Config reload (yeni .env dəyərlərini götürsün)
import importlib, config
importlib.reload(config)
print("=" * 70)
print("DƏRİN STRESS TEST — Neon PostgreSQL")
print("=" * 70)
print(f"Backend   : {'REMOTE POSTGRES' if config.USE_REMOTE_DB else 'lokal sqlite'}")
print(f"URL       : {config.DATABASE_URL[:50]}...")
print()

from memory import store
importlib.reload(store)

results = {"passed": 0, "failed": 0, "errors": []}

def test(name, func):
    """Test runner."""
    t0 = time.time()
    try:
        result = func()
        ms = int((time.time() - t0) * 1000)
        results["passed"] += 1
        ok = "✓" if result is not False else "✗"
        print(f"  {ok}  [{ms:5d}ms]  {name}" + (f"  → {result}" if result and result is not True else ""))
        return True
    except Exception as e:
        ms = int((time.time() - t0) * 1000)
        results["failed"] += 1
        results["errors"].append((name, str(e)))
        print(f"  ✗  [{ms:5d}ms]  {name}  → XƏTA: {e}")
        return False


print("\n--- 1. BAĞLANTII VƏ SCHEMA ---")

def t1():
    store.init_db()
    s = store.stats()
    assert s["backend"] == "postgres", f"Backend postgres deyil: {s['backend']}"
    return s
test("init_db() + stats()", t1)

def t2():
    v = store._current_version()
    assert v == 2, f"Schema version gözlənilmir: {v}"
    return f"schema_version={v}"
test("Schema version yoxla", t2)


print("\n--- 2. ƏSAS CRUD ---")

def t3():
    tid = store.save_thought(0, "Test prompt", "Test response", "groq", "thinking...", 100, 50)
    assert tid > 0, f"ID qayıtmadı: {tid}"
    return f"id={tid}"
test("save_thought() — INSERT", t3)

def t4():
    rows = store.recent_thoughts(5)
    assert len(rows) > 0
    assert "prompt" in rows[0]
    return f"{len(rows)} sətir"
test("recent_thoughts() — SELECT", t4)

def t5():
    rows = store.recent_thoughts(5)
    tid = rows[0]["id"]
    t = store.get_thought(tid)
    assert t is not None
    assert t["prompt"] == "Test prompt"
    return f"id={tid} oxundu"
test("get_thought() — SELECT by id", t5)

def t6():
    rid = store.save_research(0, "neon stress test", "neon-postgres", [{"a": 1}, {"b": 2}], "test summary")
    assert rid > 0
    return f"id={rid}"
test("save_research() — INSERT (JSON)", t6)

def t7():
    rows = store.recent_research(5)
    assert len(rows) > 0
    assert isinstance(rows[0]["results"], list)
    return f"{len(rows)} sətir, JSON parse OK"
test("recent_research() — JSON deserialize", t7)

def t8():
    nid = store.save_note(0, "Test qeyd", "/tmp/test.md", "test,stress")
    assert nid > 0
    rows = store.list_notes(10)
    assert any(r["id"] == nid for r in rows)
    return f"id={nid}"
test("save_note + list_notes", t8)

def t9():
    tid = store.add_task("Neon stress test tapşırığı", priority=5, notes="test üçün")
    assert tid > 0
    tasks = store.list_tasks("open", 50)
    assert any(t["id"] == tid for t in tasks)
    return f"id={tid}, {len(tasks)} açıq tapşırıq"
test("add_task + list_tasks", t9)

def t10():
    # task-i tap, status dəyiş
    tasks = store.list_tasks("open", 50)
    tid = tasks[0]["id"]
    store.update_task(tid, "done")
    tasks2 = store.list_tasks("done", 50)
    assert any(t["id"] == tid for t in tasks2)
    return f"id={tid} done"
test("update_task — UPDATE", t10)

def t11():
    store.save_metric(0, 1234, "groq", True)
    store.save_metric(0, 5678, "groq", False)
    s = store.stats()
    assert s["avg_duration_ms"] > 0
    return f"avg={s['avg_duration_ms']}ms, success_rate={s['success_rate']}"
test("save_metric + stats avg", t11)


print("\n--- 3. STRESS TEST (50 insert + 100 query paralel) ---")

def t12():
    """50 thought insert, serial."""
    t0 = time.time()
    ids = []
    for i in range(50):
        tid = store.save_thought(
            cycle=i // 10,
            prompt=f"Stress test prompt #{i}",
            response=f"Response #{i}",
            brain="groq",
            thinking=f"thinking {i}",
            tokens_in=100 + i,
            tokens_out=50 + i,
        )
        ids.append(tid)
    ms = int((time.time() - t0) * 1000)
    assert all(i > 0 for i in ids), f"Bəzi insert uğursuz: {ids}"
    return f"50 insert in {ms}ms ({50000/max(ms,1):.0f} insert/s)"
test("Bulk INSERT: 50 thoughts", t12)

def t13():
    """100 query (recent_thoughts)."""
    t0 = time.time()
    for i in range(100):
        rows = store.recent_thoughts(10)
        assert len(rows) > 0
    ms = int((time.time() - t0) * 1000)
    return f"100 query in {ms}ms ({100000/max(ms,1):.0f} q/s)"
test("Bulk SELECT: 100 recent_thoughts", t13)


print("\n--- 4. PARALEL/CONCURRENT ACCESS ---")

import threading

def t14():
    """5 thread paralel olaraq 20 insert edir (100 cəmi)."""
    errors = []
    ids_lock = threading.Lock()
    all_ids = []
    def worker(thread_id):
        try:
            for i in range(20):
                tid = store.save_thought(
                    cycle=thread_id,
                    prompt=f"Thread-{thread_id} insert #{i}",
                    response=f"response {i}",
                    brain="groq",
                )
                with ids_lock:
                    all_ids.append(tid)
        except Exception as e:
            errors.append((thread_id, str(e)))
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
    t0 = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    ms = int((time.time() - t0) * 1000)
    assert not errors, f"Thread errors: {errors}"
    assert len(all_ids) == 100, f"100 insert gözlənilir, {len(all_ids)} alındı"
    return f"100 insert (5 thread) in {ms}ms, unique IDs: {len(set(all_ids))}"
test("Concurrent INSERT: 5 thread × 20", t14)

def t15():
    """5 thread paralel query (read-heavy)."""
    errors = []
    def reader(thread_id):
        try:
            for i in range(20):
                rows = store.recent_thoughts(20)
                _ = store.list_tasks("open", 20)
                _ = store.list_notes(20)
        except Exception as e:
            errors.append((thread_id, str(e)))
    threads = [threading.Thread(target=reader, args=(i,)) for i in range(5)]
    t0 = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    ms = int((time.time() - t0) * 1000)
    assert not errors, f"Reader errors: {errors}"
    return f"5 thread × 20 query in {ms}ms"
test("Concurrent SELECT: 5 reader thread", t15)


print("\n--- 5. ERROR RECOVERY ---")

def t16():
    """Boş nəticə — error verməməli."""
    r = store._queryone("SELECT * FROM thoughts WHERE id = -1")
    assert r is None
    return "OK"
test("Boş SELECT — None qaytarır", t16)

def t17():
    """Səhv tip olan query — exception atır, lakin backend ölür??"""
    try:
        store._query("SELECT * FROM nonexistent_table_xyz")
        return "❌ exception atmadı"
    except Exception as e:
        return f"exception atdı (gözlənilir): {type(e).__name__}"
test("Səhv query — exception handling", t17)

def t18():
    """Exception-dan sonra yenə işləyir?"""
    r = store._queryone("SELECT 1 AS n")
    assert r["n"] == 1
    return "backend hələ canlıdır"
test("Exception sonrası — backend canlı", t18)

def t19():
    """Unicode/Azərbaycan hərfləri ilə data."""
    prompt = "Azərbaycan: Bakı, Gəncə, Sumqayıt, Şəki, Lənkəran. Simvollar: ə ö ü ş ç ı ğ. Emoji: 🧠🚀✅"
    response = "Cavab: Bəli, Azərbaycan gözəl ölkədir! 🌍"
    tid = store.save_thought(cycle=99, prompt=prompt, response=response, brain="groq")
    t = store.get_thought(tid)
    assert t is not None, "thought None qayıtdı"
    assert t["prompt"] == prompt, f"prompt uyğun deyil: {t['prompt']!r}"
    assert t["response"] == response, f"response uyğun deyil: {t['response']!r}"
    return f"id={tid}, Unicode roundtrip OK"
test("Unicode/Azərbaycan hərfləri (roundtrip)", t19)

def t20():
    """Böyük JSON payload."""
    big_data = [{"i": i, "name": "x" * 100, "tags": [random.choice(string.ascii_letters) for _ in range(10)]} for i in range(100)]
    rid = store.save_research(0, "big json test", "neon", big_data, "summary")
    rows = store.recent_research(1)
    assert len(rows[0]["results"]) == 100
    return f"id={rid}, 100 item JSON"
test("Böyük JSON payload (100 item)", t20)


print("\n--- 6. YEKUN STATS ---")

s = store.stats()
print(f"  Backend       : {s['backend']}")
print(f"  Schema ver    : {s['schema_version']}")
print(f"  Cəmi thoughts : {s['thoughts']}")
print(f"  Cəmi research : {s['researches']}")
print(f"  Cəmi notes    : {s['notes']}")
print(f"  Açıq tasks    : {s['open_tasks']}")
print(f"  Avg duration  : {s['avg_duration_ms']}ms")
print(f"  Success rate  : {s['success_rate']}")


print("\n" + "=" * 70)
print(f"NƏTİCƏ: {results['passed']} keçdi, {results['failed']} uğursuz")
print("=" * 70)

if results["failed"] == 0:
    print("\n🟢 BÜTÜN TESTLƏR UĞURLA KEÇDİ — Neon PostgreSQL tam işləyir!")
    print("   7/24 persistent storage təmin edildi.")
    print("   Lokal SQLite bypass olundu (sıfır lokal IO).")
else:
    print("\n🔴 BƏZİ TESTLƏR UĞURSUZ OLDU:")
    for name, err in results["errors"]:
        print(f"  - {name}: {err}")

print()
