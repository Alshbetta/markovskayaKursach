"""
Text2SQL System with LLM Security Audit
========================================
Курсовой проект: Применение LLM в решении задач информационной безопасности
Студент: Матеюк Елизавета Геннадьевна, 3 курс, Кибербезопасность (6-05-0533-12)
Дисциплина: Машинное обучение и нейронные сети

Архитектура:
  Ввод → Naive Bayes Classifier → Parser → Security Auditor (Regex + LLM) → Executor
"""

import os
import sys
import json

# ── UTF-8 console output on Windows ─────────────────────────────────────────
# Windows defaults to cp1251 which cannot render box-drawing characters.
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── Optional colored output ──────────────────────────────────────────────────
try:
    from colorama import Fore, Style, init as colorama_init
    colorama_init(autoreset=True)

    def c(text, color): return color + str(text) + Style.RESET_ALL
    GREEN  = lambda t: c(t, Fore.GREEN)
    RED    = lambda t: c(t, Fore.RED)
    YELLOW = lambda t: c(t, Fore.YELLOW)
    CYAN   = lambda t: c(t, Fore.CYAN)
    BLUE   = lambda t: c(t, Fore.BLUE)
    BOLD   = lambda t: c(t, Style.BRIGHT)
    GRAY   = lambda t: c(t, Fore.WHITE)
except ImportError:
    GREEN = RED = YELLOW = CYAN = BLUE = BOLD = GRAY = lambda t: str(t)

import config
from modules.classifier import IntentClassifier
from modules.parser import QueryParser
from modules.security_auditor import SecurityAuditor
from modules.executor import DatabaseExecutor
from modules.visualizer import MetricsVisualizer
from data.training_data import TEST_DATA, MALICIOUS_INPUTS, SAFE_SQL_SAMPLES


# ── Banner ───────────────────────────────────────────────────────────────────

BANNER = """

        Text2SQL System with LLM Security Audit                  
  Применение LLM в решении задач информационной безопасности     
  Матеюк Е.Г. | Кибербезопасность | 3 курс | 2026               

"""

HELP_TEXT = """
Доступные команды:
  <запрос>   — Обработать запрос на естественном языке
  metrics    — Построить графики метрик классификатора
  test       — Запустить тестирование классификатора на тест-сете
  demo       — Демонстрация на примерах (безопасные + атаки)
  schema     — Показать структуру базы данных
  help       — Эта справка
  quit       — Выход

Примеры запросов:
  Покажи всех сотрудников из Москвы
  Добавь нового сотрудника Петров Иван в отдел ИТ из Гродно
  Обнови зарплату сотрудника с id 2 до 80000
  Удалить сотрудника с id 5
"""


# ── Pretty printing helpers ──────────────────────────────────────────────────

SEP = "─" * 62

def section(title: str):
    print(CYAN(f"\n┌─ {title} {'─' * max(0, 56 - len(title))}┐"))

def section_end():
    print(CYAN("└" + "─" * 61 + "┘"))

def info(key: str, val):
    print(f"  {YELLOW(key + ':')} {val}")

def result_table(rows: list):
    if not rows:
        print(GRAY("  (нет записей)"))
        return
    keys = list(rows[0].keys())
    widths = [max(len(str(k)), max(len(str(r.get(k, ""))) for r in rows)) for k in keys]
    header = "  " + " │ ".join(str(k).ljust(w) for k, w in zip(keys, widths))
    divider = "  " + "─┼─".join("─" * w for w in widths)
    print(CYAN(header))
    print(GRAY(divider))
    for row in rows:
        line = "  " + " │ ".join(str(row.get(k, "")).ljust(w) for k, w in zip(keys, widths))
        print(line)


# ── Pipeline ─────────────────────────────────────────────────────────────────

def run_pipeline(
    user_input: str,
    classifier: IntentClassifier,
    parser: QueryParser,
    auditor: SecurityAuditor,
    executor: DatabaseExecutor,
    verbose: bool = True,
) -> dict:
    """
    Full pipeline: text → intent → parse → audit → execute.
    Returns a result dict.
    """
    # ── Step 1: Classify intent ──────────────────────────────────────────────
    intent, confidence = classifier.predict_with_confidence(user_input)

    if verbose:
        section("Шаг 1 — Классификатор намерений (Naive Bayes)")
        info("Ввод",        user_input)
        info("Интент",      BOLD(intent))
        info("Уверенность", f"{confidence * 100:.1f}%")
        proba = classifier.predict_proba(user_input)
        bar_parts = "  " + "  ".join(
            f"{k}: {GREEN('█' * int(v * 20)) if k == intent else GRAY('|' * int(v * 20))} {v:.2f}"
            for k, v in sorted(proba.items(), key=lambda x: -x[1])
        )
        print(bar_parts)
        section_end()

    # ── Step 2: Parse query ──────────────────────────────────────────────────
    pq = parser.parse(user_input, intent)

    if verbose:
        section("Шаг 2 — Семантический парсер (Text-to-SQL)")
        info("Таблица",   pq.table)
        info("Колонки",   pq.columns)
        info("Условия",   pq.conditions or "(нет)")
        info("Значения",  pq.values or "(нет)")
        info("SQL",       BOLD(pq.raw_sql))
        if pq.parse_notes:
            info("Извлечено", ", ".join(pq.parse_notes))
        section_end()

    # ── Step 3: Security audit ───────────────────────────────────────────────
    audit = auditor.audit(user_input, pq.raw_sql)

    if verbose:
        section("Шаг 3 — LLM Security Auditor (CWE-89)")

        # Stage 1 result
        s1 = audit["stage1"]
        s1_status = GREEN("БЕЗОПАСНО") if s1["safe"] else RED("УГРОЗА ОБНАРУЖЕНА")
        info("Этап 1 (Regex)", s1_status)
        if s1["detected_patterns"]:
            for pat in s1["detected_patterns"]:
                print(f"    {RED('⚠')} {pat}")

        # Stage 2 result
        # s2 can be an empty dict {} when Stage 1 already blocked the query
        # (audit() returns early and never fills stage2).
        s2 = audit["stage2"]
        if not s2:
            # Regex caught it — LLM stage was skipped entirely
            info("Этап 2 (LLM)", YELLOW("Пропущен (заблокировано на Этапе 1)"))
        elif auditor.llm_available:
            s2_status = GREEN("БЕЗОПАСНО") if s2.get("safe", True) else RED("ПОДОЗРИТЕЛЬНО")
            info("Этап 2 (LLM)",   s2_status)
            info("  Метка",        s2.get("label", "—"))
            info("  Уверенность",  f"{s2.get('confidence', 0) * 100:.1f}%")
        else:
            info("Этап 2 (LLM)", YELLOW("Модель не загружена — пропущен"))

        # Final verdict
        verdict = audit["final_verdict"]
        if verdict == "SAFE":
            info("Вердикт", GREEN("✔ БЕЗОПАСНО — запрос разрешён"))
        elif verdict == "BLOCKED_REGEX":
            info("Вердикт", RED("✘ ЗАБЛОКИРОВАНО (Regex)"))
        else:
            info("Вердикт", RED("✘ ЗАБЛОКИРОВАНО (LLM)"))
        section_end()

    # ── Step 4: Execute ──────────────────────────────────────────────────────
    exec_result = None
    if not audit["blocked"]:
        exec_result = executor.execute(pq)

        if verbose:
            section("Шаг 4 — Исполнитель (JSON Database)")
            if exec_result["success"]:
                msg = exec_result.get("message", "")
                if msg:
                    info("Статус", GREEN(msg))
                rows = exec_result.get("data", [])
                if rows:
                    info("Результат", f"{exec_result.get('affected', len(rows))} запись(ей)")
                    result_table(rows)
            else:
                info("Ошибка", RED(exec_result.get("error", "неизвестная ошибка")))
            section_end()
    else:
        if verbose:
            section("Шаг 4 — Исполнитель")
            print(RED("  ✘ Запрос заблокирован на этапе аудита безопасности."))
            print(RED("  ✘ Выполнение запрещено."))
            section_end()

    return {
        "input": user_input,
        "intent": intent,
        "confidence": confidence,
        "sql": pq.raw_sql,
        "audit": audit,
        "exec_result": exec_result,
    }


# ── Demo run ──────────────────────────────────────────────────────────────────

def run_demo(classifier, parser, auditor, executor):
    print(BOLD("\n" + "═" * 62))
    print(BOLD("  ДЕМОНСТРАЦИЯ СИСТЕМЫ"))
    print(BOLD("═" * 62))

    demo_queries = [
        "Покажи всех сотрудников из Москвы",
        "Показать сотрудников с зарплатой выше 70000",
        "Обновить зарплату сотрудника с id 1 до 82000",
    ]

    print(BOLD("\n Легитимные запросы "))
    for q in demo_queries:
        print(f"\n{BOLD('>')} {q}")
        run_pipeline(q, classifier, parser, auditor, executor, verbose=True)

    print(BOLD("\n Атаки SQL-инъекций "))
    for raw_input, attack_type in MALICIOUS_INPUTS[:6]:
        print(f"\n{BOLD('>')} {raw_input}  {GRAY(f'[{attack_type}]')}")
        run_pipeline(raw_input, classifier, parser, auditor, executor, verbose=True)


# ── Metrics & testing ─────────────────────────────────────────────────────────

def run_test_mode(classifier, auditor):
    print(BOLD("\n" + "═" * 62))
    print(BOLD("  ТЕСТИРОВАНИЕ КЛАССИФИКАТОРА"))
    print(BOLD("═" * 62))

    metrics = classifier.evaluate(TEST_DATA)

    print(f"\n{YELLOW('Метрики по классам:')}")
    header = f"  {'Класс':<10} {'Precision':>10} {'Recall':>10} {'F1-Score':>10} {'Support':>8}"
    print(CYAN(header))
    print(GRAY("  " + "─" * 52))

    for cls, m in metrics["per_class"].items():
        line = (f"  {cls:<10} {m['precision']:>10.4f} {m['recall']:>10.4f} "
                f"{m['f1']:>10.4f} {m['support']:>8}")
        print(line)

    print(GRAY("  " + "─" * 52))
    mac = metrics["macro"]
    print(
        f"  {'Macro avg':<10} {mac['precision']:>10.4f} {mac['recall']:>10.4f} "
        f"{mac['f1']:>10.4f}"
    )

    cv = classifier.cross_validate()
    print(f"\n{YELLOW('Кросс-валидация (5-fold, Macro F1):')}")
    for i, s in enumerate(cv["cv_scores"], 1):
        bar = "█" * int(s * 30)
        print(f"  Fold {i}: {GREEN(bar)} {s:.4f}")
    print(f"  {YELLOW('Среднее:')} {cv['mean_f1']:.4f}  {YELLOW('Std:')} {cv['std_f1']:.4f}")

    print(f"\n{YELLOW('Тест аудитора безопасности:')}")
    print(f"  {'Запрос':<50} {'Вердикт'}")
    print(GRAY("  " + "─" * 62))
    audit_log = []
    for raw, _ in MALICIOUS_INPUTS:
        # We only audit the raw string against a dummy SQL for test purposes
        from modules.parser import ParsedQuery
        dummy_pq = ParsedQuery(intent="SELECT", table="employees",
                               raw_sql=f"SELECT * FROM employees WHERE input='{raw}'")
        res = auditor.audit(raw, dummy_pq.raw_sql)
        verdict_str = RED("БЛОК") if res["blocked"] else GREEN("БЕЗОПАСНО")
        label = raw[:48] + ".." if len(raw) > 48 else raw
        print(f"  {label:<50} {verdict_str}")
        audit_log.append(res)
    return audit_log


def run_metrics_mode(classifier, auditor):
    import traceback
    print(BOLD("\n  Генерация графиков метрик..."))

    # Build audit log using regex-only auditor for speed & determinism.
    # LLM calls here would be slow (19+ calls) and unnecessary for metrics.
    from modules.security_auditor import SecurityAuditor as _SA
    fast_auditor = _SA(use_llm=False)

    audit_log = []
    for raw_input, _ in MALICIOUS_INPUTS:
        sql = f"SELECT * FROM employees WHERE q='{raw_input}'"
        audit_log.append(fast_auditor.audit(raw_input, sql))

    # Fix: correct variable unpacking — SAFE_SQL_SAMPLES = (sql_str, description)
    for sql_str, _ in SAFE_SQL_SAMPLES:
        audit_log.append(fast_auditor.audit("show all employees", sql_str))

    try:
        vis = MetricsVisualizer()
        paths = vis.generate_full_report(classifier, TEST_DATA, audit_log)
        print(GREEN("\n  Графики сохранены:"))
        for p in paths:
            print(f"    {p}")
    except Exception as exc:
        print(RED(f"\n  Ошибка при генерации графиков: {exc}"))
        print(traceback.format_exc())


# ── Schema display ────────────────────────────────────────────────────────────

def show_schema(executor: DatabaseExecutor):
    print(BOLD("\n  Схема базы данных (database.json):"))
    for table in executor.list_tables():
        cols = executor.table_schema(table)
        print(f"  {CYAN(table)}: {', '.join(cols)}")


# ── Main loop ─────────────────────────────────────────────────────────────────

def main():
    print(CYAN(BANNER))

    # ── Init modules ────────────────────────────────────────────────────────
    print(YELLOW("  Инициализация системы..."))
    print("  [1/4] Обучение классификатора (Naive Bayes)...")
    classifier = IntentClassifier()
    print(GREEN("       OK"))

    print("  [2/4] Инициализация парсера...")
    parser = QueryParser()
    print(GREEN("       OK"))

    print("  [3/4] Загрузка модуля безопасности (LLM)...")
    auditor = SecurityAuditor(use_llm=True)
    llm_status = GREEN("bart-large-mnli") if auditor.llm_available else YELLOW("только Regex")
    print(f"       {GREEN('OK')} — {llm_status}")

    print("  [4/4] Подключение к базе данных (JSON)...")
    executor = DatabaseExecutor(config.DB_PATH)
    print(GREEN("       OK"))

    print(GREEN("\n  Система готова к работе."))
    print(GRAY(HELP_TEXT))

    # ── REPL ────────────────────────────────────────────────────────────────
    while True:
        try:
            raw = input(BOLD("\nText2SQL > ")).strip()
        except (EOFError, KeyboardInterrupt):
            print(YELLOW("\n  Выход."))
            break

        if not raw:
            continue

        cmd = raw.lower()

        if cmd in ("quit", "exit", "q", "выход"):
            print(YELLOW("  До свидания!"))
            break

        elif cmd == "help":
            print(GRAY(HELP_TEXT))

        elif cmd == "schema":
            show_schema(executor)

        elif cmd == "demo":
            run_demo(classifier, parser, auditor, executor)

        elif cmd == "test":
            run_test_mode(classifier, auditor)

        elif cmd == "metrics":
            run_metrics_mode(classifier, auditor)

        else:
            run_pipeline(raw, classifier, parser, auditor, executor, verbose=True)


if __name__ == "__main__":
    main()