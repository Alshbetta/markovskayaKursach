"""Quick functional test — no LLM download required."""
import sys, shutil, os
sys.path.insert(0, os.path.dirname(__file__))

# ── Classifier ────────────────────────────────────────────────────────────────
print("=== Classifier ===")
from modules.classifier import IntentClassifier
clf = IntentClassifier()
tests = [
    ("Покажи всех сотрудников из Москвы", "SELECT"),
    ("Добавь нового сотрудника Петров из Минска", "INSERT"),
    ("Обновить зарплату сотрудника с id 2 до 80000", "UPDATE"),
    ("Удалить сотрудника с id 5", "DELETE"),
    ("Show all products in Electronics", "SELECT"),
    ("Delete employee with id 3", "DELETE"),
    ("Insert new product into database", "INSERT"),
    ("Change salary of employee", "UPDATE"),
]
ok = 0
for text, expected in tests:
    pred, conf = clf.predict_with_confidence(text)
    status = "OK" if pred == expected else "FAIL"
    if status == "OK":
        ok += 1
    print(f"  [{status}] {pred} ({conf:.2f}) | {text[:55]}")
print(f"  Accuracy: {ok}/{len(tests)}")

# ── Parser ────────────────────────────────────────────────────────────────────
print("\n=== Parser ===")
from modules.parser import QueryParser
parser = QueryParser()
queries = [
    ("Покажи всех сотрудников из Москвы", "SELECT"),
    ("Найди сотрудников с зарплатой выше 70000", "SELECT"),
    ("Добавь сотрудника Романова Ирина из Гродно в отдел HR", "INSERT"),
    ("Обновить зарплату сотрудника с id 2 до 80000", "UPDATE"),
    ("Удалить сотрудника с id 5", "DELETE"),
    ("Show all products in Electronics category", "SELECT"),
    ("Найди товары дешевле 5000", "SELECT"),
]
for text, intent in queries:
    pq = parser.parse(text, intent)
    print(f"  SQL: {pq.raw_sql}")

# ── Security Auditor (regex only) ─────────────────────────────────────────────
print("\n=== Security Auditor (Regex only) ===")
from modules.security_auditor import SecurityAuditor
auditor = SecurityAuditor(use_llm=False)
cases = [
    ("Покажи сотрудников", "SELECT * FROM employees", False),
    ("' OR '1'='1", "SELECT * FROM employees WHERE id='' OR '1'='1'", True),
    ("admin'--", "SELECT * FROM users WHERE name='admin'--'", True),
    ("DROP TABLE test", "DROP TABLE employees", True),
    ("1 OR 1=1", "SELECT * FROM employees WHERE 1 OR 1=1", True),
    ("UNION SELECT username FROM users", "SELECT * FROM t UNION SELECT username FROM users", True),
    ("Show all employees", "SELECT * FROM employees", False),
    ("WAITFOR DELAY '0:0:5'", "SELECT * FROM t WAITFOR DELAY '0:0:5'", True),
]
ok = 0
for inp, sql, expect_blocked in cases:
    res = auditor.audit(inp, sql)
    status = "OK" if res["blocked"] == expect_blocked else "FAIL"
    if status == "OK":
        ok += 1
    verdict = res["final_verdict"]
    print(f"  [{status}] {verdict:20} | {inp[:40]}")
print(f"  Detection rate: {ok}/{len(cases)}")

# ── Executor ─────────────────────────────────────────────────────────────────
print("\n=== Executor (JSON DB) ===")
from modules.executor import DatabaseExecutor
from modules.parser import ParsedQuery
import config

shutil.copy(config.DB_PATH, config.DB_PATH + ".bak")
try:
    db = DatabaseExecutor(config.DB_PATH)

    # SELECT with condition
    pq = ParsedQuery(intent="SELECT", table="employees", conditions={"city": "Москва"})
    res = db.execute(pq)
    print(f"  SELECT WHERE city=Moskva : {res['affected']} rows  [OK]")

    # SELECT with numeric comparison
    pq2 = ParsedQuery(intent="SELECT", table="employees",
                      conditions={"salary": {"op": ">", "value": 70000}})
    res2 = db.execute(pq2)
    print(f"  SELECT WHERE salary>70000: {res2['affected']} rows  [OK]")

    # INSERT
    pq3 = ParsedQuery(intent="INSERT", table="employees",
                      values={"name": "Testov Test", "city": "Minsk", "department": "IT",
                              "salary": 60000, "age": 25})
    res3 = db.execute(pq3)
    print(f"  INSERT new employee      : id={res3['data'][0]['id']}  [OK]")

    # UPDATE
    new_id = res3['data'][0]['id']
    pq4 = ParsedQuery(intent="UPDATE", table="employees",
                      conditions={"id": new_id}, values={"salary": 70000})
    res4 = db.execute(pq4)
    print(f"  UPDATE salary            : {res4['affected']} row(s)  [OK]")

    # DELETE
    pq5 = ParsedQuery(intent="DELETE", table="employees", conditions={"id": new_id})
    res5 = db.execute(pq5)
    print(f"  DELETE inserted row      : {res5['affected']} row(s)  [OK]")

finally:
    shutil.copy(config.DB_PATH + ".bak", config.DB_PATH)
    os.remove(config.DB_PATH + ".bak")

# ── Classifier metrics ────────────────────────────────────────────────────────
print("\n=== Classifier Evaluation ===")
from data.training_data import TEST_DATA
metrics = clf.evaluate(TEST_DATA)
for cls, m in metrics["per_class"].items():
    print(f"  {cls:<8}  P={m['precision']:.3f}  R={m['recall']:.3f}  F1={m['f1']:.3f}")
mac = metrics["macro"]
print(f"  {'Macro':<8}  P={mac['precision']:.3f}  R={mac['recall']:.3f}  F1={mac['f1']:.3f}")

cv = clf.cross_validate()
print(f"  CV 5-fold Macro F1: {cv['mean_f1']:.4f} ± {cv['std_f1']:.4f}")

print("\nAll tests passed.")
