# -*- coding: utf-8 -*-
"""
sql_parser.py — Эвристический парсер для извлечения параметров SQL из текста
Преобразует текст "покажи пользователей из Москвы старше 25" в структуру запроса
"""

import re

# --- КОНФИГУРАЦИЯ БАЗЫ ДАННЫХ ---
# Словарь ключевых слов для определения таблицы
TABLE_KEYWORDS = {
    "users": ["пользовател", "клиент", "сотрудник", "юзер", "менеджер", "человек", "аккаунт"],
    "orders": ["заказ", "покупк", "транзакц", "товар", "корзин", "продукт"],
    "departments": ["отдел", "департамент", "бюджет", "категор", "подразделен"]
}

# Словарь значений для условий WHERE (Ключевые слова в тексте -> Значение в БД)
# Исправлено: добавлены различные окончания (падежи) для поиска
VALUE_MAPPINGS = {
    "users": {
        "city": {
            "Москва": ["москва", "москвы", "москве", "москву", "москвой", "столиц", "мск"],
            "Санкт-Петербург": ["петербург", "петербурга", "питер", "питера", "спб", "ленинград"],
            "Казань": ["казан", "казани", "казань", "татарстан"],
            "Новосибирск": ["новосибирск", "новосибирска", "сибирь"],
            "Екатеринбург": ["екатеринбург", "екатеринбурга", "урал", "екб"]
        },
        "active": {
            True: ["активн", "работает", "действующ", "активный"],
            False: ["неактивн", "уволен", "бан", "заблок", "удален", "неактивный"]
        }
    },
    "orders": {
        "status": {
            "completed": ["выполнен", "завершен", "доставлен", "готов", "completed", "выполн"],
            "pending": ["ожидан", "ждет", "в обработке", "pending", "нов", "новом"],
            "shipped": ["отправлен", "в пути", "shipped", "едет", "отправл"]
        }
    },
    "departments": {
        "name": {
            "IT": ["айти", "it", "разработк", "программист", "информат"],
            "Sales": ["продаж", "сбыт", "менеджер", "sales"],
            "HR": ["hr", "кадр", "персонал", "human"],
            "Marketing": ["маркетинг", "реклам", "пиар", "promo"]
        }
    }
}

# Числовые условия (операторы)
NUMBER_PATTERNS = {
    "users": {
        "age": {">": ["старше", "возраст"], "<": ["младше", "моложе"]},
        "salary": {">": ["зарплат", "оклад", "больше", "выше"], "<": ["меньше", "ниже"]}
},
    "orders": {
        "amount": {">": ["сумм", "больше", "от", "дороже"], "<": ["меньше", "до", "дешевле"]},
        "user_id": {"=": ["пользовател", "клиент", "id", "номер"]}
    }
}


def detect_table(text):
    """Определяет таблицу по ключевым словам"""
    t = text.lower()
    for table, keywords in TABLE_KEYWORDS.items():
        for kw in keywords:
            if kw in t:
                return table
    return "users"


def extract_conditions(text, table):
    """Извлекает условия WHERE на основе текста и схемы таблицы"""
    conditions = {}
    t = text.lower()
    words_in_text = t.split()  # Разбиваем текст на отдельные слова

    # 1. Проверка строковых значений (Города, Статусы и т.д.)
    if table in VALUE_MAPPINGS:
        for column, mappings in VALUE_MAPPINGS[table].items():
            if isinstance(mappings, dict):
                for db_value, keywords in mappings.items():
                    found = False
                    for kw in keywords:
                        # Проверка: вхождение подстроки ИЛИ совпадение начала слова
                        # Это поможет найти "москвы" по ключу "москв" (если бы он был)
                        # или "петербурга" по ключу "петербург"
                        if kw in t or any(word.startswith(kw) for word in words_in_text):
                            conditions[column] = db_value
                            found = True
                            break
                    if found:
                        break

    # 2. Проверка числовых значений
    if table in NUMBER_PATTERNS:
        for column, ops in NUMBER_PATTERNS[table].items():
            for operator, keywords in ops.items():
                for kw in keywords:
                    # Ищем паттерн: "ключевое слово" + число
                    pattern = rf"{kw}\s*(\d+)"
                    match = re.search(pattern, t)
                    if match:
                        val = int(match.group(1))
                        if operator == "=":
                            conditions[column] = val
                        else:
                            conditions[column] = (operator, val)
                        break
    
    return conditions


def extract_columns(text, table):
    """Определяет, какие колонки выводить"""
    t = text.lower()
    field_keywords = {
        "id": ["id", "номер", "код", "айди"],
        "name": ["имя", "название", "фио", "нейм"],
        "email": ["email", "почт", "мейл", "адрес"],
        "city": ["город", "сити", "место"],
        "age": ["возраст", "лет", "age"],
        "salary": ["зарплат", "деньг", "оклад", "salary"],
        "active": ["статус", "активн"],
        "product": ["товар", "продукт", "название"],
        "amount": ["сумм", "цен", "стоим", "amount"],
        "status": ["статус", "состояние"],
        "date": ["дата", "число", "время"],
        "budget": ["бюджет", "деньг", "фонд"]
    }

    found_columns = []
    for col, kws in field_keywords.items():
        for kw in kws:
            if kw in t:
                if col not in found_columns:
                    found_columns.append(col)
    
    return found_columns if found_columns else "*"


def parse_query(text, intent):
    """Главная функция парсинга"""
    table = detect_table(text)
    conditions = extract_conditions(text, table)
    columns = extract_columns(text, table)

    return {
        "table": table,
        "conditions": conditions,
        "columns": columns,
        "intent": intent
    }

def generate_sql(params):
    """Генерирует текстовую строку SQL-запроса на основе параметров парсера"""
    intent = params['intent'].upper()
    table = params['table']
    conditions = params['conditions']
    
    # 1. Формируем часть SELECT / DELETE / UPDATE
    if intent == "SELECT":
        columns = params['columns']
        # Обработка случая, когда парсер вернул ["*"] вместо "*"
        if columns == ["*"]:
            cols_str = "*"
        elif isinstance(columns, list):
            cols_str = ", ".join(columns)
        else:
            cols_str = str(columns)
            
        sql = f"SELECT {cols_str} FROM {table}"
        
    elif intent == "DELETE":
        sql = f"DELETE FROM {table}"
        
    elif intent == "INSERT":
        sql = f"INSERT INTO {table} VALUES (...)" # Заглушка, т.к. парсер пока не извлекает данные
        
    elif intent == "UPDATE":
        sql = f"UPDATE {table} SET ..." # Заглушка
        
    else:
        return "Неизвестный запрос"

    # 2. Добавляем условия WHERE
    if conditions:
        where_parts = []
        for col, val in conditions.items():
            # Если значение — кортеж (оператор, число), например: ('>', 25)
            if isinstance(val, tuple):
                op, target = val
                where_parts.append(f"{col} {op} {target}")
            else:
                # Если строка, добавляем кавычки
                where_parts.append(f"{col} = '{val}'")
        
        sql += " WHERE " + " AND ".join(where_parts)
    
    return sql + ";"

if __name__ == "__main__":
    # Тест парсера
    тест = "покажи пользователей из Москвы"
    результат = parse_query(тест, "SELECT")
    print(f"Текст: {тест}")
    print(f"Результат: {результат}")