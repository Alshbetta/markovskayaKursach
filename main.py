# -*- coding: utf-8 -*-
"""
main.py — Главный файл запуска пайплайна
Курсовая работа: Классификация SQL-запросов (Наивный Байес)
"""
import random
import os
import sys
from dataset import DATASET, КЛАССЫ
from preprocessor import tokenize_text
from classifier import NaiveBayesClassifier, compute_confusion_matrix
from query_executor import JSONDatabase
from sql_parser import parse_query, generate_sql

# Импорты для графиков
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib import rcParams

def extract_table_from_query(text):
    """
    Простая эвристика для определения таблицы из текстового запроса.
    Возвращает имя таблицы из database.json или 'users' по умолчанию.
    """
    t = text.lower()
    if any(w in t for w in ["заказ", "ордер", "покупк", "транзакц", "корзин"]):
        return "orders"
    if any(w in t for w in ["отдел", "департамент", "категор", "бюджет"]):
        return "departments"
    # По умолчанию возвращаем users
    return "users"

# Настройка графиков
rcParams["font.family"] = "DejaVu Sans"
rcParams["axes.spines.top"] = False
rcParams["axes.spines.right"] = False

ЦВЕТА = {
    "SELECT": "#3182ce",
    "INSERT": "#38a169",
    "UPDATE": "#d69e2e",
    "DELETE": "#e53e3e",
}
ПАПКА = "graphs"

def create_graphs_folder():
    """Создание папки для сохранения графиков"""
    if not os.path.exists(ПАПКА):
        os.makedirs(ПАПКА)
    print(f"   Папка для графиков: '{ПАПКА}/'")

def save_plot(filename, title):
    """Сохранение текущего графика в PNG"""
    путь = os.path.join(ПАПКА, filename)
    plt.savefig(путь, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close()
    print(f"   Сохранён: {путь}")

# ============================================================================
# ГРАФИКИ
# ============================================================================

def plot_class_distribution():
    """График 1 — Распределение классов"""
    по = {к: 0 for к in КЛАССЫ}
    for _, к in DATASET:
        по[к] += 1
    
    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(КЛАССЫ, [по[к] for к in КЛАССЫ],
                  color=[ЦВЕТА[к] for к in КЛАССЫ], width=0.5,
                  edgecolor="white", linewidth=1.5)
    
    for b in bars:
        ax.text(b.get_x() + b.get_width()/2, b.get_height() + 0.3,
                str(int(b.get_height())), ha="center", fontsize=13, fontweight="bold")
    
    ax.set_title("График 1: Распределение классов в датасете", fontsize=14, fontweight="bold", pad=12)
    ax.set_xlabel("Класс SQL-запроса", fontsize=12)
    ax.set_ylabel("Количество примеров", fontsize=12)
    ax.set_ylim(0, max(по.values()) + 5)
    
    save_plot("01_распределение_датасета.png", "Распределение классов")

def plot_top_words(model_dict):
    """График 2 — Топ-5 слов для каждого класса"""
    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    fig.suptitle("График 2: Топ-5 ключевых слов по классам", fontsize=14, fontweight="bold")
    
    for ax, класс in zip(axes.flatten(), КЛАССЫ):
        топ = sorted(model_dict["счётчик_слов"][класс].items(),
                     key=lambda x: x[1], reverse=True)[:5]
        слова = [п[0] for п in топ][::-1]
        частоты = [п[1] for п in топ][::-1]
        
        bars = ax.barh(слова, частоты, color=ЦВЕТА[класс], edgecolor="white")
        for bar, ч in zip(bars, частоты):
            ax.text(bar.get_width() + 0.05, bar.get_y() + bar.get_height()/2,
                    str(ч), va="center", fontsize=11, fontweight="bold")
        
        ax.set_title(класс, fontsize=13, fontweight="bold", color=ЦВЕТА[класс])
        ax.set_xlabel("Частота", fontsize=10)
    
    plt.tight_layout()
    save_plot("02_топ_слов_по_классам.png", "Топ слов по классам")

def plot_confusion_matrix(results):
    """График 3 — Матрица ошибок"""
    m = compute_confusion_matrix(results, КЛАССЫ)
    
    fig, ax = plt.subplots(figsize=(7, 6))
    for i, и in enumerate(КЛАССЫ):
        for j, п in enumerate(КЛАССЫ):
            зн = m[и][п]
            диаг = (i == j)
            цвет = "#c6f6d5" if диаг else ("#fff5f5" if зн > 0 else "#f7fafc")
            ax.add_patch(plt.Rectangle([j-0.5, i-0.5], 1, 1, color=цвет))
            
            цт = "#22543d" if диаг else ("#c53030" if зн > 0 else "#cbd5e0")
            ax.text(j, i, str(зн), ha="center", va="center",
                    fontsize=18, fontweight="bold", color=цт)
    
    ax.set_xticks(range(len(КЛАССЫ)))
    ax.set_yticks(range(len(КЛАССЫ)))
    ax.set_xticklabels(КЛАССЫ, fontsize=12)
    ax.set_yticklabels(КЛАССЫ, fontsize=12)
    ax.set_title("График 3: Матрица ошибок", fontsize=13, fontweight="bold", pad=15)
    
    plt.tight_layout()
    save_plot("03_матрица_ошибок.png", "Матрица ошибок")

def plot_class_accuracy(results):
    """График 4 — Точность по классам"""
    детали = {к: {"верно": 0, "всего": 0} for к in КЛАССЫ}
    for р in results:
        детали[р["истинный"]]["всего"] += 1
        if р["верно"]:
            детали[р["истинный"]]["верно"] += 1
    
    точности = [
        детали[к]["верно"] / детали[к]["всего"] * 100 if детали[к]["всего"] else 0
        for к in КЛАССЫ
    ]
    
    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(КЛАССЫ, точности, color=[ЦВЕТА[к] for к in КЛАССЫ],
                  width=0.5, edgecolor="white", linewidth=1.5)
    
    for b, т in zip(bars, точности):
        ax.text(b.get_x()+b.get_width()/2, т+1,
                f"{т:.0f}%", ha="center", fontsize=13, fontweight="bold")
    
    ax.set_title("График 4: Точность по каждому классу", fontsize=13, fontweight="bold", pad=12)
    ax.set_ylabel("Точность (%)", fontsize=12)
    ax.set_ylim(0, 115)
    
    save_plot("04_точность_по_классам.png", "Точность по классам")

def plot_classification_example(classifier, text):
    """График 7 — Пример классификации"""
    # Используем объект классификатора для вызова метода predict
    победитель, оценки = classifier.predict(text)
    значения = [оценки[к] for к in КЛАССЫ]
    
    fig, ax = plt.subplots(figsize=(9, 5))
    цвета_b = [ЦВЕТА[к] if к == победитель else "#cbd5e0" for к in КЛАССЫ]
    bars = ax.bar(КЛАССЫ, значения, color=цвета_b, width=0.5, edgecolor="white", linewidth=1.5)
    
    for b, з in zip(bars, значения):
        ax.text(b.get_x()+b.get_width()/2, з+0.1,
                f"{з:.2f}", ha="center", fontsize=11, fontweight="bold")
    
    ax.set_title(f'График 7: Оценки классификатора\n«{text}»',
                 fontsize=13, fontweight="bold", pad=12)
    ax.set_ylabel("log score", fontsize=11)
    
    save_plot("07_пример_классификации.png", "Пример классификации")

# ============================================================================
# ГЛАВНАЯ ФУНКЦИЯ
# ============================================================================

def main():
    print("\n" + "="*70)
    print(" КУРСОВАЯ РАБОТА: Классификация SQL-запросов")
    print(" Метод: Наивный Байесовский классификатор (NLP, метод №14)")
    print(" Направление: Применение LLM в задачах информационной безопасности")
    print("="*70)
    
    # Создание папки для графиков
    create_graphs_folder()
    
    # Инициализация базы данных
    print("\n Инициализация JSON базы данных...")
    db = JSONDatabase("database.json")
    db.show_table("users")
    
    # ШАГ 1: Датасет
    print("\n" + "="*60)
    print(" ШАГ 1: ДАТАСЕТ")
    print("="*60)
    по = {к: 0 for к in КЛАССЫ}
    for _, к in DATASET:
        по[к] += 1
    print(f"Всего примеров: {len(DATASET)}")
    for к in КЛАССЫ:
        print(f"  {к:10} — {по[к]} примеров")
    
    plot_class_distribution()
    
    # ШАГ 2: Разбивка на обучающую/тестовую
    print("\n" + "="*60)
    print(" ШАГ 2: РАЗБИВКА ДАННЫХ (80% / 20%)")
    print("="*60)
    random.seed(42)
    данные = DATASET[:]
    random.shuffle(данные)
    граница = int(len(данные) * 0.8)
    обучающая = данные[:граница]
    тестовая = данные[граница:]
    print(f"Обучающая: {len(обучающая)} примеров")
    print(f"Тестовая:  {len(тестовая)} примеров")
    
    # ШАГ 3: Обучение модели
    print("\n" + "="*60)
    print(" ШАГ 3: ОБУЧЕНИЕ МОДЕЛИ")
    print("="*60)
    model = NaiveBayesClassifier(alpha=0.1)
    model.train(обучающая, verbose=True)
    
    plot_top_words(model.model)
    
    # ШАГ 4: Пример классификации
    print("\n" + "="*60)
    print(" ШАГ 4: ПРИМЕР КЛАССИФИКАЦИИ")
    print("="*60)
    пример = "покажи всех пользователей из Москвы"
    класс, оценки = model.predict(пример, verbose=True)
    # Передаём объект model, а не model.model
    plot_classification_example(model, пример)
    
    # ШАГ 5: Оценка на тестовой выборке
    print("\n" + "="*60)
    print(" ШАГ 5: ОЦЕНКА КАЧЕСТВА")
    print("="*60)
    точность, результаты = model.evaluate(тестовая)
    верно = sum(р["верно"] for р in результаты)
    print(f"\nТочность (Accuracy): {точность:.1%} ({верно}/{len(результаты)})")
    
    plot_confusion_matrix(результаты)
    plot_class_accuracy(результаты)
    
    # ШАГ 5.5: Детальный анализ ошибок и подбор alpha
    print("\n" + "= "*60)
    print(" ШАГ 5.5: АНАЛИЗ ОШИБОК И ПОДБОР ПАРАМЕТРОВ ")
    print("= "*60)

    # 1. Показываем ошибочные предсказания
    ошибки = [р for р in результаты if not р["верно"]]
    if ошибки:
        print(f"\n❌ Найдено ошибок: {len(ошибки)} из {len(результаты)}")
        for i, р in enumerate(ошибки[:5], 1):  # Показываем первые 5
            print(f"\n  {i}. Текст: «{р['текст']}»")
            print(f"     Истинный: {р['истинный']}, Предсказан: {р['предсказание']}")

    # 2. Подбор лучшего alpha
    print("\n🔬 Подбор оптимального alpha...")
    лучший_alpha = 1.0
    лучшая_точность = точность

    for a in [0.1, 0.3, 0.5, 0.7, 1.0, 1.5, 2.0]:
        тест_модель = NaiveBayesClassifier(alpha=a)
        тест_модель.train(обучающая, verbose=False)
        тест_точность, _ = тест_модель.evaluate(тестовая)
        статус = "← ЛУЧШИЙ" if тест_точность > лучшая_точность else ""
        print(f"  alpha={a:.1f} → точность={тест_точность:.1%} {статус}")
        if тест_точность > лучшая_точность:
            лучшая_точность = тест_точность
            лучший_alpha = a

    print(f"\n✅ Рекомендация: используйте alpha={лучший_alpha}")

        # ШАГ 6: Демонстрация с реальной БД (Умный парсинг)
    print("\n" + "="*60)
    print(" ШАГ 6: РАБОТА С РЕАЛЬНОЙ БАЗОЙ ДАННЫХ (Smart Parse)")
    print("="*60)
    
    # Тестовые запросы разной сложности
    тестовые_запросы = [
        "покажи всех пользователей из Москвы",              # Простой WHERE
        "покажи заказы со статусом выполнен",               # Другая таблица
        "найди сотрудников с зарплатой больше 70000",       # Числовое условие >
        "выведи бюджет отдела IT",                          # Конкретные колонки
        #"удали неактивных пользователей",                   # DELETE с условием
    ]
    
    for текст in тестовые_запросы:
        print(f"\n Запрос: «{текст}»")
        print("-" * 60)
        
        # 1. Классификация интента (Naive Bayes)
        класс, _ = model.predict(текст)
        print(f"    Интент (Naive Bayes): {класс}")
        
        # 2. Парсинг параметров (Rule-Based)
        params = parse_query(текст, класс)
        print(f"    SQL: {generate_sql(params)}")
        print(f"    Таблица: {params['table']}")
        print(f"    Условия: {params['conditions']}")
        print(f"    Колонки: {params['columns']}")
        
        # 3. Выполнение
        if класс == "SELECT":
            results = db.execute_select(
                params['table'], 
                conditions=params['conditions'],
                columns=params['columns']
            )
            print(f"    Найдено записей: {len(results)}")
            for r in results:
                print(f"      {r}")
        
        elif класс == "DELETE":
            # Для DELETE условия важны!
            if params['conditions']:
                count = db.execute_delete(params['table'], params['conditions'])
                print(f"    Удалено записей: {count}")
            else:
                print("     Удаление без условий заблокировано системой безопасности!")
    
    # Показать лог изменений
    db.show_changes_log()
    
        # ИНТЕРАКТИВНЫЙ РЕЖИМ
    print("\n" + "="*60)
    print(" ИНТЕРАКТИВНЫЙ РЕЖИМ (Попробуйте сложные запросы)")
    print("="*60)
    print("Примеры: 'покажи заказы из Москвы', 'найти сотрудников старше 30 лет'")
    print("Введите запрос (или 'выход')\n")
    
    while True:
        try:
            текст = input(" Ваш запрос: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n Выход.")
            break
        
        if текст.lower() in ("выход", "exit", "q"):
            print(" Выход.")
            break

        if текст.lower() in ("восстановить", "restore", "откат", "undo"):
            db.restore_latest()
            continue

        if not текст: continue
        
        # 1. Классификация
        класс, оценки = model.predict(текст, verbose=True)
        plot_classification_example(model, текст)
        
        # 2. Парсинг
        params = parse_query(текст, класс)
        
        sql_query = generate_sql(params)
        print(f"\n   Сгенерированный SQL: {sql_query}") 

        ответ = input(f"\n Класс: {класс}, Таблица: {params['table']}. Выполнить? (y/n): ").strip().lower()
        
        if ответ == 'y':
            if класс == "SELECT":
                # Используем парсер для извлечения таблицы и условий
                params = parse_query(текст, класс)
                print(f"    Таблица: {params['table']}")
                print(f"    Условия: {params['conditions']}")
                
                results = db.execute_select(
                    params['table'],
                    conditions=params['conditions'],  # ← Передаём условия!
                    columns=params['columns']
                )
                print(f" Результаты: {len(results)} записей")
                for r in results:
                    print(f"   {r}")
            elif класс == "INSERT":
                print("     INSERT требует точных данных. Эмуляция добавления...")
                # Тут можно доработать парсер для INSERT, но пока заглушка
            elif класс == "UPDATE":
                 print("     UPDATE требует точных данных. Эмуляция изменения...")
            elif класс == "DELETE":
                if params['conditions']:
                    db.execute_delete(params['table'], params['conditions'])
                else:
                    print("    Удаление всей таблицы запрещено!")
    
    print("\n" + "="*60)
    print(" ВСЕ ГРАФИКИ СОХРАНЕНЫ В ПАПКУ 'graphs/'")
    print("="*60)
    for г in [
        "01_распределение_датасета.png",
        "02_топ_слов_по_классам.png",
        "03_матрица_ошибок.png",
        "04_точность_по_классам.png",
        "07_пример_классификации.png",
    ]:
        print(f"   graphs/{г}")
    

if __name__ == "__main__":
    main()