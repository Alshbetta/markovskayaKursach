# sql_parser.py — Парсер Text2SQL: извлечение сущностей и генерация SQL

import re
from dataset import ENTITY_KEYWORDS


class SQLParser:
    """
    Парсер для преобразования текстового запроса в SQL-команду.
    Извлекает: таблицу, условия, колонки, значения для INSERT/UPDATE.
    """

    def __init__(self):
        self.table_keywords = ENTITY_KEYWORDS["tables"]
        self.condition_keywords = ENTITY_KEYWORDS["conditions"]

    def _detect_table(self, text: str) -> str:
        """Определяет таблицу по ключевым словам в тексте."""
        text_lower = text.lower()
        for keyword, table in self.table_keywords.items():
            if keyword in text_lower:
                return table
        # Дефолтная таблица
        return "employees"

    def _detect_conditions(self, text: str) -> list[str]:
        """Извлекает условия WHERE из текста."""
        text_lower = text.lower()
        conditions = []

        for phrase, condition in self.condition_keywords.items():
            if phrase in text_lower:
                conditions.append(condition)

        # Числовые условия (цена, зарплата, возраст, id)
        price_match = re.search(r'дороже\s+(\d+)', text_lower)
        if price_match:
            conditions.append(f"price > {price_match.group(1)}")

        salary_match = re.search(r'зарплат[а-я]*\s+больше\s+(\d+)', text_lower)
        if salary_match:
            conditions.append(f"salary > {salary_match.group(1)}")

        age_match = re.search(r'возраст[а-я]*\s+больше\s+(\d+)', text_lower)
        if age_match:
            conditions.append(f"age > {age_match.group(1)}")

        id_match = re.search(r'\bс\s+id\s+(\d+)\b|\bid\s*[=:]\s*(\d+)', text_lower)
        if id_match:
            id_val = id_match.group(1) or id_match.group(2)
            conditions.append(f"id = {id_val}")

        # Поиск имени (для UPDATE/DELETE)
        name_match = re.search(r'(?:пользователя|сотрудника|клиента)\s+([а-яёА-ЯЁ][а-яё]+)', text)
        if name_match:
            conditions.append(f"name LIKE '%{name_match.group(1)}%'")

        return conditions

    def _extract_insert_values(self, text: str, table: str) -> dict:
        """Извлекает значения для INSERT из текста."""
        values = {}

        # Имя
        name_match = re.search(
            r'(?:добавь|зарегистрируй|создай).*?(?:сотрудника|пользователя|клиента)?\s+([А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)?)',
            text
        )
        if name_match:
            values["name"] = name_match.group(1).strip()
        else:
            values["name"] = "Новый Пользователь"

        # Город
        city_match = re.search(r'из\s+([А-ЯЁ][а-яё\-]+)', text)
        if city_match:
            values["city"] = city_match.group(1)

        # Email
        email_match = re.search(r'[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}', text)
        if email_match:
            values["email"] = email_match.group(0)

        # Зарплата
        salary_match = re.search(r'зарплат[а-я]*\s+(\d+)', text.lower())
        if salary_match:
            values["salary"] = int(salary_match.group(1))

        # Статус
        if "активн" in text.lower():
            values["status"] = "active"
        else:
            values["status"] = "active"

        return values

    def _extract_update_values(self, text: str) -> dict:
        """Извлекает новые значения для UPDATE."""
        updates = {}

        email_match = re.search(r'(?:email|почту?)\s+(?:на\s+)?([\w.+-]+@[\w-]+\.[a-zA-Z]{2,})', text.lower())
        if email_match:
            updates["email"] = email_match.group(1)

        salary_match = re.search(r'зарплат[а-я]*\s+(?:на\s+)?(\d+)', text.lower())
        if salary_match:
            updates["salary"] = int(salary_match.group(1))

        status_match = re.search(r'статус\s+(?:на\s+)?([а-яёa-z]+)', text.lower())
        if status_match:
            updates["status"] = status_match.group(1)

        city_match = re.search(r'(?:город|адрес)\s+(?:на\s+)?([А-ЯЁ][а-яё\-]+)', text)
        if city_match:
            updates["city"] = city_match.group(1)

        if not updates:
            updates["status"] = "updated"

        return updates

    def parse(self, text: str, intent: str) -> dict:
        """
        Основной метод парсинга.
        Возвращает словарь с параметрами для генерации SQL.
        """
        table = self._detect_table(text)
        conditions = self._detect_conditions(text)

        result = {
            "intent": intent,
            "table": table,
            "conditions": conditions,
            "sql": "",
            "params": {}
        }

        if intent == "SELECT":
            result["sql"] = self._build_select(table, conditions)

        elif intent == "INSERT":
            values = self._extract_insert_values(text, table)
            result["params"] = values
            result["sql"] = self._build_insert(table, values)

        elif intent == "UPDATE":
            updates = self._extract_update_values(text)
            result["params"] = updates
            result["sql"] = self._build_update(table, updates, conditions)

        elif intent == "DELETE":
            result["sql"] = self._build_delete(table, conditions)

        return result

    def _build_select(self, table: str, conditions: list[str]) -> str:
        sql = f"SELECT * FROM {table}"
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += ";"
        return sql

    def _build_insert(self, table: str, values: dict) -> str:
        if not values:
            return f"INSERT INTO {table} VALUES (...);"
        cols = ", ".join(values.keys())
        vals = ", ".join(
            f"'{v}'" if isinstance(v, str) else str(v)
            for v in values.values()
        )
        return f"INSERT INTO {table} ({cols}) VALUES ({vals});"

    def _build_update(self, table: str, updates: dict, conditions: list[str]) -> str:
        if not updates:
            return f"UPDATE {table} SET ... WHERE ...;"
        set_clause = ", ".join(
            f"{k} = '{v}'" if isinstance(v, str) else f"{k} = {v}"
            for k, v in updates.items()
        )
        sql = f"UPDATE {table} SET {set_clause}"
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += ";"
        return sql

    def _build_delete(self, table: str, conditions: list[str]) -> str:
        sql = f"DELETE FROM {table}"
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += ";"
        return sql
    
    def parse_query(text, intent):
        """Основная функция парсинга (для совместимости)"""
        parser = SQLParser()  # если у тебя есть класс
        return parser.parse(text, intent)