# Text2SQL System with LLM Security Audit

> **Курсовой проект** по дисциплине «Машинное обучение и нейронные сети»  
> Специальность: **6-05-0533-12 Кибербезопасность** | 3 курс | ГрГУ им. Янки Купалы  
> Автор: **Матеюк Елизавета Геннадьевна** | Руководитель: Зайкова С.А.

---

## О проекте

Система преобразования текстовых запросов на **естественном языке** в **SQL-команды** (Text2SQL) с интегрированным модулем безопасности на базе LLM.

**Ключевая особенность:** система не просто генерирует SQL, но и проверяет каждый запрос на наличие SQL-инъекций (CWE-89) перед выполнением — с помощью двухэтапного аудита: regex-паттерны + семантический анализ языковой моделью.

---

## Архитектура

```
Пользователь вводит текст
        │
        ▼
┌───────────────────┐
│  Naive Bayes      │  Классифицирует интент:
│  Classifier       │  SELECT / INSERT / UPDATE / DELETE
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│  Text-to-SQL      │  Извлекает таблицу, условия,
│  Parser           │  значения → генерирует SQL
└────────┬──────────┘
         │
         ▼
┌───────────────────────────────────┐
│       LLM Security Auditor        │
│  Этап 1 (Regex):  быстрая         │
│    проверка сигнатур атак         │
│  Этап 2 (LLM):  семантический     │
│    анализ (facebook/bart-large-   │
│    mnli, zero-shot classification)│
└────────┬──────────────────────────┘
         │  безопасно
         ▼
┌───────────────────┐
│  JSON DB Executor │  Выполняет CRUD-операции
│  (database.json)  │  на JSON-базе данных
└───────────────────┘
```

---

## Функционал

| Модуль | Описание |
|--------|----------|
| **Классификатор интентов** | Naive Bayes + TF-IDF (scikit-learn), 4 класса: SELECT / INSERT / UPDATE / DELETE |
| **Text-to-SQL парсер** | Rule-based, поддержка русского и английского языка |
| **LLM Security Auditor** | Этап 1 — 20+ regex-паттернов; Этап 2 — zero-shot BART |
| **JSON Database** | Эмуляция реляционной БД: таблицы `employees`, `departments`, `products` |
| **Визуализация** | 8 графиков метрик (Precision/Recall/F1, матрица ошибок, CV, baseline и др.) |

---

## Установка и запуск

### Требования
- Python 3.10+
- ~2 ГБ свободного места (для модели `facebook/bart-large-mnli`)

### 1. Клонировать репозиторий

```bash
git clone https://github.com/<your-username>/text2sql-security.git
cd text2sql-security
```

### 2. Создать виртуальное окружение (рекомендуется)

```bash
python -m venv .venv

# Windows:
.venv\Scripts\activate

# Linux / macOS:
source .venv/bin/activate
```

### 3. Установить зависимости

```bash
pip install -r requirements.txt
```

> Первая установка займёт несколько минут (torch ~2 ГБ).

### 4. Запустить

```bash
python main.py
```

При первом запуске модель `facebook/bart-large-mnli` (~1.6 ГБ) скачается автоматически в системный кеш HuggingFace.

---

## Использование

```
Text2SQL > Покажи всех сотрудников из Москвы
Text2SQL > Найди сотрудников с зарплатой выше 70000
Text2SQL > Добавь нового сотрудника Петров Иван в отдел ИТ из Минска
Text2SQL > Обнови зарплату сотрудника с id 2 до 85000
Text2SQL > Удалить сотрудника с id 5
Text2SQL > Show all products in Electronics category
```

### Специальные команды

| Команда | Действие |
|---------|----------|
| `demo` | Демонстрация на легитимных запросах + SQL-атаках |
| `test` | Оценка классификатора: Precision, Recall, F1, CV |
| `metrics` | Сгенерировать 8 графиков в папку `plots/` |
| `schema` | Показать структуру базы данных |
| `help` | Список команд |
| `quit` | Выход |

### Запуск без LLM (только Regex-аудит)

В файле `main.py` измените:
```python
# было:
auditor = SecurityAuditor(use_llm=True)
# стало:
auditor = SecurityAuditor(use_llm=False)
```

---

## Структура проекта

```
text2sql-security/
├── main.py                  # Главная точка входа (интерактивный CLI)
├── config.py                # Конфигурация (пути, пороги LLM)
├── database.json            # JSON-база данных (employees, departments, products)
├── requirements.txt         # Зависимости Python
│
├── modules/
│   ├── classifier.py        # Naive Bayes классификатор интентов
│   ├── parser.py            # Text-to-SQL парсер (рус + англ)
│   ├── security_auditor.py  # Двухэтапный аудит безопасности (Regex + LLM)
│   ├── executor.py          # CRUD-исполнитель для JSON-базы
│   └── visualizer.py        # Генератор 8 графиков метрик
│
├── data/
│   └── training_data.py     # Обучающие данные, тест-сет, примеры атак
│
└── plots/                   # Генерируется автоматически командой `metrics`
    ├── classification_metrics.png
    ├── confusion_matrix.png
    ├── security_distribution.png
    ├── cv_scores.png
    ├── top_features.png
    ├── class_priors.png
    ├── baseline_comparison.png
    └── query_log_scores.png
```

---

## Результаты

### Классификатор интентов (Naive Bayes)

| Класс | Precision | Recall | F1-Score |
|-------|-----------|--------|----------|
| SELECT | 1.000 | 1.000 | 1.000 |
| INSERT | 1.000 | 1.000 | 1.000 |
| UPDATE | 1.000 | 1.000 | 1.000 |
| DELETE | 1.000 | 1.000 | 1.000 |
| **Macro avg** | **1.000** | **1.000** | **1.000** |

**5-fold Cross-Validation Macro F1:** `0.8615 ± 0.0814`

### LLM Security Auditor (Regex-этап)

| Тип атаки | Обнаружено |
|-----------|-----------|
| OR tautology (`' OR '1'='1`) | ✅ |
| UNION SELECT | ✅ |
| DROP TABLE | ✅ |
| Stacked queries (`;--`) | ✅ |
| SLEEP / WAITFOR (blind injection) | ✅ |
| Comment injection (`--`, `/**/`) | ✅ |

**Detection rate: 100% (12/12 атак заблокировано)**

---

## Технологии

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)
![scikit-learn](https://img.shields.io/badge/scikit--learn-1.6-orange?logo=scikit-learn)
![HuggingFace](https://img.shields.io/badge/HuggingFace-Transformers-yellow?logo=huggingface)
![PyTorch](https://img.shields.io/badge/PyTorch-2.x-red?logo=pytorch)
![Matplotlib](https://img.shields.io/badge/Matplotlib-3.10-blue)

- **ML:** scikit-learn (MultinomialNB, TfidfVectorizer)
- **LLM:** HuggingFace Transformers — `facebook/bart-large-mnli` (zero-shot classification)
- **Визуализация:** matplotlib, seaborn
- **БД:** JSON (эмуляция реляционной СУБД)

---

## Лицензия

MIT License — свободное использование в учебных целях.
