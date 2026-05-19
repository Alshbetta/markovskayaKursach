# -*- coding: utf-8 -*-
"""
sql_parser.py — Эвристический парсер для извлечения параметров SQL из текста
"""
import re

TABLE_KEYWORDS = {
    "users": ["пользовател", "клиент", "сотрудник", "юзер", "менеджер", "человек", "аккаунт"],
    "orders": ["заказ", "покупк", "транзакц", "товар", "корзин", "продукт"],
    "departments": ["отдел", "департамент", "бюджет", "категор", "подразделен"]
}

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
    t = text.lower()
    for table, keywords in TABLE_KEYWORDS.items():
        for kw in keywords:
            if kw in t:
                return table
    return "users"

def extract_conditions(text, table):
    conditions = {}
    t = text.lower()
    words_in_text = t.split()
    if table in VALUE_MAPPINGS:
        for column, mappings in VALUE_MAPPINGS[table].items():
            if isinstance(mappings, dict):
                for db_value, keywords in mappings.items():
                    found = False
                    for kw in keywords:
                        if kw in t or any(word.startswith(kw) for word in words_in_text):
                            conditions[column] = db_value
                            found = True
                            break
                    if found:
                        break
    if table in NUMBER_PATTERNS:
        for column, ops in NUMBER_PATTERNS[table].items():
            for operator, keywords in ops.items():
                for kw in keywords:
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
    return found_columns if found_columns else ["*"]

def parse_query(text, intent):
    table = detect_table(text)
    conditions = extract_conditions(text, table)
    columns = extract_columns(text, table)
    return {"table": table, "conditions": conditions, "columns": columns, "intent": intent}

if __name__ == "__main__":
    тест = "покажи пользователей из Москвы"
    результат = parse_query(тест, "SELECT")
    print(f"Текст: {тест}")
    print(f"Результат: {результат}")