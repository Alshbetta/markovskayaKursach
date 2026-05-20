"""
Text-to-SQL Parser.

Converts a natural-language query + classified intent into a structured
ParsedQuery object and generates the corresponding SQL string.
Handles both Russian and English input.
"""

import re
from dataclasses import dataclass, field
from typing import Optional


# ── Vocabulary maps ──────────────────────────────────────────────────────────

TABLE_KEYWORDS: dict[str, list[str]] = {
    "employees": [
        "сотрудник", "сотрудника", "сотруднике", "сотруднику", "сотрудников",
        "работник", "работника", "работнике", "работнику", "работников",
        "персонал", "employee", "employees", "worker", "workers", "staff",
    ],
    # "positions" checked BEFORE "departments" so that queries like
    # "должности в отделе ИТ" route to positions (not departments).
    "positions": [
        "должность", "должности", "должностей", "должностях", "должностью",
        "профессия", "профессии", "профессий",
        "position", "positions", "role", "roles", "job title",
    ],
    "products": [
        "товар", "товара", "товаре", "товару", "товаров",
        "продукт", "продукта", "продукту", "продуктов",
        "product", "products",
    ],
    "departments": [
        "отдел", "отдела", "отделе", "отделу", "отделов",
        "подразделение", "department", "departments", "division",
    ],
}

CITY_MAP: dict[str, str] = {
    # Москва — nom/gen/dat/acc/ins/prep
    "москва": "Москва", "москвы": "Москва", "москве": "Москва",
    "москву": "Москва", "москвой": "Москва", "moscow": "Москва",
    # Минск
    "минск": "Минск", "минска": "Минск", "минске": "Минск",
    "минску": "Минск", "минском": "Минск", "minsk": "Минск",
    # Гродно
    "гродно": "Гродно", "гродна": "Гродно", "гродне": "Гродно",
    "гродну": "Гродно", "grodno": "Гродно",
    # Санкт-Петербург
    "санкт-петербург": "Санкт-Петербург", "питер": "Санкт-Петербург",
    "петербург": "Санкт-Петербург", "saint-petersburg": "Санкт-Петербург",
    "spb": "Санкт-Петербург",
    # Киев
    "киев": "Киев", "киева": "Киев", "kyiv": "Киев", "kiev": "Киев",
}

DEPT_MAP: dict[str, str] = {
    "ит": "ИТ", "it": "ИТ", "информационных технологий": "ИТ",
    "бухгалтерия": "Бухгалтерия", "бухгалтерии": "Бухгалтерия",
    "accounting": "Бухгалтерия",
    "hr": "HR", "кадры": "HR", "кадровой": "HR", "кадровый": "HR",
    "маркетинг": "Маркетинг", "marketing": "Маркетинг",
}

CATEGORY_MAP: dict[str, str] = {
    "электроника": "Электроника", "electronics": "Электроника",
    "периферия": "Периферия", "peripherals": "Периферия",
    "peripheral": "Периферия",
}

# Job positions.
# Single-word keys use prefix matching in _extract_position (handles inflections
# by appending \w* to the stem). Multi-word keys need explicit case forms because
# Russian adjectives change their endings in a way that prefix matching cannot
# handle (e.g. "системный" → "системных", not "системного").
POSITION_MAP: dict[str, str] = {
    # ── ИТ ───────────────────────────────────────────────────────────────────
    "разработчик по":                  "Разработчик ПО",
    "разработчик":                     "Разработчик ПО",
    "программист":                     "Разработчик ПО",
    "developer":                       "Разработчик ПО",
    "programmer":                      "Разработчик ПО",
    # Системный администратор — all grammatical cases (adj ending changes)
    "системный администратор":         "Системный администратор",
    "системного администратора":       "Системный администратор",
    "системному администратору":       "Системный администратор",
    "системным администратором":       "Системный администратор",
    "системных администраторов":       "Системный администратор",
    "системные администраторы":        "Системный администратор",
    "сисадмин":                        "Системный администратор",
    "system administrator":            "Системный администратор",
    "sysadmin":                        "Системный администратор",
    # Архитектор ПО — single-word part handled by prefix match
    "архитектор по":                   "Архитектор ПО",
    "архитектор":                      "Архитектор ПО",
    "architect":                       "Архитектор ПО",
    # ── Бухгалтерия ─────────────────────────────────────────────────────────
    # Главный бухгалтер — case forms for the adjective
    "главный бухгалтер":               "Главный бухгалтер",
    "главного бухгалтера":             "Главный бухгалтер",
    "главному бухгалтеру":             "Главный бухгалтер",
    "главным бухгалтером":             "Главный бухгалтер",
    "главных бухгалтеров":             "Главный бухгалтер",
    "chief accountant":                "Главный бухгалтер",
    "бухгалтер":                       "Бухгалтер",
    "accountant":                      "Бухгалтер",
    # ── HR ──────────────────────────────────────────────────────────────────
    "hr-менеджер":                     "HR-менеджер",
    "hr менеджер":                     "HR-менеджер",
    "hr manager":                      "HR-менеджер",
    "рекрутер":                        "Рекрутер",
    "recruiter":                       "Рекрутер",
}

COLUMN_ALIASES: dict[str, list[str]] = {
    "name": ["имя", "имена", "имени", "название", "названия", "фио", "name", "names", "наименование"],
    "city": ["город", "города", "городе", "городу", "city", "location", "место"],
    "department": ["отдел", "отдела", "отделе", "department", "подразделение"],
    # All case forms of зарплата
    "salary": [
        "зарплата", "зарплату", "зарплаты", "зарплате", "зарплатой",
        "зарплатою", "оклад", "оклада", "окладу", "окладом",
        "salary", "wage", "wages", "доход", "дохода",
    ],
    "age": ["возраст", "возраста", "возрасте", "лет", "age", "years"],
    "id": ["id", "идентификатор", "номер", "number"],
    # All case forms of цена + special condition words
    "price": [
        "цена", "цены", "цену", "цене", "ценой",
        "стоимость", "стоимости", "стоимостью",
        "price", "cost", "дешевле", "дороже",
    ],
    "stock": ["количество", "количества", "запас", "запаса", "остаток", "stock", "quantity"],
    "category": ["категория", "категорию", "категории", "категориях", "category", "тип", "типа"],
    "budget": ["бюджет", "бюджета", "бюджете", "бюджетом", "budget"],
    "head": ["руководитель", "руководителя", "глава", "директор", "head", "manager"],
    # employees.position
    "position": [
        "должность", "должности", "должностью", "должностей",
        "профессия", "профессии",
        "position", "role", "job",
    ],
    # positions.title / positions.min_salary
    "title": ["название должности", "title", "наименование должности"],
    "min_salary": ["минимальная зарплата", "мин зарплата", "min salary", "minimum salary"],
}


# ── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class ParsedQuery:
    intent: str = ""
    table: str = ""
    columns: list = field(default_factory=lambda: ["*"])
    conditions: dict = field(default_factory=dict)
    values: dict = field(default_factory=dict)
    raw_sql: str = ""
    parse_notes: list = field(default_factory=list)


# ── Parser ────────────────────────────────────────────────────────────────────

class QueryParser:

    # ── Table detection ──────────────────────────────────────────────────────

    def _detect_table(self, text: str) -> str:
        lower = text.lower()
        for table, keywords in TABLE_KEYWORDS.items():
            for kw in keywords:
                if kw in lower:
                    return table
        return "employees"  # sensible default

    # ── Condition extraction ─────────────────────────────────────────────────

    def _extract_id(self, text: str) -> Optional[int]:
        m = re.search(r"\bid\s*[=:№#]?\s*(\d+)", text, re.IGNORECASE)
        if m:
            return int(m.group(1))
        m = re.search(r"(?:номер|number)\s+(\d+)", text, re.IGNORECASE)
        if m:
            return int(m.group(1))
        return None

    def _extract_city(self, text: str) -> Optional[str]:
        lower = text.lower()
        # "из Москвы", "from Moscow", "в Минске"
        m = re.search(r"(?:из|from|в|in)\s+([а-яёА-ЯЁa-zA-Z\-]+)", text, re.IGNORECASE)
        if m:
            candidate = m.group(1).lower()
            if candidate in CITY_MAP:
                return CITY_MAP[candidate]
        for key, val in CITY_MAP.items():
            if re.search(r"\b" + re.escape(key) + r"\b", lower):
                return val
        return None

    def _extract_department(self, text: str) -> Optional[str]:
        lower = text.lower()
        for key, val in DEPT_MAP.items():
            if re.search(r"\b" + re.escape(key) + r"\b", lower):
                return val
        return None

    def _extract_category(self, text: str) -> Optional[str]:
        lower = text.lower()
        for key, val in CATEGORY_MAP.items():
            if re.search(r"\b" + re.escape(key) + r"\b", lower):
                return val
        return None

    def _extract_position(self, text: str) -> Optional[str]:
        """
        Extract job position from text using POSITION_MAP.

        Uses prefix matching so inflected Russian forms are handled:
          разработчик → разработчиков, разработчика, разработчику ...
          архитектор  → архитектора, архитекторов ...
          бухгалтер   → бухгалтера, бухгалтеров ...

        Multi-word keys ("главный бухгалтер") are checked before single-word
        keys ("бухгалтер") because the list is sorted by length descending.
        """
        lower = text.lower()
        for key in sorted(POSITION_MAP.keys(), key=len, reverse=True):
            words = key.split()
            if len(words) == 1:
                # Single word: allow any inflected suffix after the stem
                pattern = r"\b" + re.escape(key) + r"\w*\b"
            else:
                # Multi-word: each word may carry its own inflection
                pattern = r"\b" + r"\s+".join(re.escape(w) + r"\w*" for w in words) + r"\b"
            if re.search(pattern, lower):
                return POSITION_MAP[key]
        return None

    # Trigger words that ARE the comparison operator themselves
    _IMPLICIT_GT = frozenset({"дороже", "выше", "больше", "более", "свыше", "старше", "above"})
    _IMPLICIT_LT = frozenset({"дешевле", "ниже", "меньше", "менее", "моложе", "cheaper", "below"})
    _IMPLICIT_GE = frozenset({"минимум"})

    def _extract_numeric_condition(self, text: str, col: str) -> Optional[dict]:
        """
        Extract numeric WHERE condition: salary > 70000, age < 30, price >= 5000.
        Uses substring after the trigger word to avoid greedy/lazy regex pitfalls.
        """
        lower = text.lower()
        trigger_words = COLUMN_ALIASES.get(col, [col])

        for tw in trigger_words:
            m_trigger = re.search(r"\b" + re.escape(tw) + r"\b", lower)
            if not m_trigger:
                continue

            # If the trigger word itself carries comparison semantics, grab the next number
            after = lower[m_trigger.end():]
            if tw in self._IMPLICIT_LT:
                m = re.search(r"\s+(\d+)", after)
                if m:
                    return {"op": "<", "value": int(m.group(1))}
            if tw in self._IMPLICIT_GT:
                m = re.search(r"\s+(\d+)", after)
                if m:
                    return {"op": ">", "value": int(m.group(1))}
            if tw in self._IMPLICIT_GE:
                m = re.search(r"\s+(\d+)", after)
                if m:
                    return {"op": ">=", "value": int(m.group(1))}

            # Regular trigger: look for comparison keyword + number after trigger
            m = re.search(
                r"\b(?:выше|больше|более|свыше|старше|дороже|greater\s+than|more\s+than|older\s+than|above)\s+(\d+)",
                after,
            )
            if m:
                return {"op": ">", "value": int(m.group(1))}

            m = re.search(
                r"\b(?:ниже|меньше|менее|моложе|дешевле|less\s+than|cheaper\s+than|younger\s+than|below)\s+(\d+)",
                after,
            )
            if m:
                return {"op": "<", "value": int(m.group(1))}

            m = re.search(
                r"\b(?:от|не\s+менее|минимум|from|at\s+least)\s+(\d+)",
                after,
            )
            if m:
                return {"op": ">=", "value": int(m.group(1))}

        return None

    def _extract_update_numeric_value(self, text: str, col: str) -> Optional[int]:
        """
        Extract the new SET value for an UPDATE: 'зарплату до 80000' → 80000.
        Looks for 'до N', 'на N', '= N', or the first large number after the trigger.
        """
        lower = text.lower()
        trigger_words = COLUMN_ALIASES.get(col, [col])

        for tw in trigger_words:
            m_trigger = re.search(r"\b" + re.escape(tw) + r"\b", lower)
            if not m_trigger:
                continue
            after = lower[m_trigger.end():]

            # Explicit keywords: "до N", "на N", "= N", "to N", "set to N", "в размере N"
            m = re.search(
                r"\b(?:до|на|=|to|set\s+to|в\s+размере|размером|равной?)\s+(\d+)",
                after,
            )
            if m:
                return int(m.group(1))

            # Fallback: first number ≥ 4 digits (avoids confusing id numbers like 2, 3)
            m = re.search(r"\b(\d{4,})\b", after)
            if m:
                return int(m.group(1))

        return None

    # Common sentence-starting words that begin with a capital letter but are NOT names
    _SKIP_INITIAL_WORDS = {
        # Russian verbs / function words
        "покажи", "показать", "показ", "выведи", "вывести", "найди", "найти",
        "получи", "получить", "отобрази", "отобразить", "выбери", "выбрать",
        "добавь", "добавить", "вставь", "вставить", "создай", "создать",
        "обнови", "обновить", "измени", "изменить", "поменяй", "поменять",
        "установи", "установить", "удали", "удалить", "убери", "убрать",
        "стереть", "исключить", "очисти", "внести", "зарегистрируй",
        # Nouns that start sentences
        "список", "все", "всех", "всю", "новый", "новую", "нового",
        "запись", "данные", "информацию", "информация",
        # English verbs
        "get", "show", "find", "list", "select", "insert", "update", "delete",
        "retrieve", "display", "search", "remove", "add", "create", "modify",
        "change", "set", "erase", "drop",
    }

    def _extract_name_like(self, text: str) -> Optional[str]:
        """Extract a proper name fragment for LIKE matching."""
        skip = set(CITY_MAP.values()) | set(DEPT_MAP.values()) | set(CATEGORY_MAP.values())
        skip_lower = {w.lower() for w in skip}
        skip_lower |= {kw for kws in TABLE_KEYWORDS.values() for kw in kws}
        skip_lower |= self._SKIP_INITIAL_WORDS

        words = re.findall(r"[А-ЯЁA-Z][а-яёa-z]+", text)
        for w in words:
            if w.lower() not in skip_lower and len(w) > 3:
                return w
        return None

    # ── Columns selection ────────────────────────────────────────────────────

    def _extract_columns(self, text: str, intent: str) -> list:
        if intent != "SELECT":
            return ["*"]
        lower = text.lower()
        mentioned = []
        for col, aliases in COLUMN_ALIASES.items():
            for alias in aliases:
                if re.search(r"\b" + re.escape(alias) + r"\b", lower):
                    if col not in mentioned:
                        mentioned.append(col)
                    break
        # If "all", "все", or no column mentioned → select all
        if not mentioned or any(w in lower for w in ["все", "всех", "всю", "all", "* "]):
            return ["*"]
        return mentioned

    # ── Value extraction for INSERT/UPDATE ──────────────────────────────────

    def _extract_values_for_update(self, text: str, table: str) -> dict:
        """Extract {column: new_value} for UPDATE using dedicated scalar extractor."""
        values = {}

        # Salary
        v = self._extract_update_numeric_value(text, "salary")
        if v is not None:
            values["salary"] = v

        if table == "products":
            v = self._extract_update_numeric_value(text, "price")
            if v is not None:
                values["price"] = v
            v = self._extract_update_numeric_value(text, "stock")
            if v is not None:
                values["stock"] = v

        if table == "departments":
            v = self._extract_update_numeric_value(text, "budget")
            if v is not None:
                values["budget"] = v

        city = self._extract_city(text)
        if city:
            values["city"] = city

        dept = self._extract_department(text)
        if dept and table == "employees":
            values["department"] = dept

        cat = self._extract_category(text)
        if cat and table == "products":
            values["category"] = cat

        pos = self._extract_position(text)
        if pos and table == "employees":
            values["position"] = pos

        return values

    def _extract_values_for_insert(self, text: str, table: str) -> dict:
        """Extract {column: value} for INSERT."""
        values = {}

        city = self._extract_city(text)
        if city:
            values["city"] = city

        dept = self._extract_department(text)
        if dept and table in ("employees", "departments"):
            values["department"] = dept

        cat = self._extract_category(text)
        if cat and table == "products":
            values["category"] = cat

        pos = self._extract_position(text)
        if pos and table == "employees":
            values["position"] = pos

        # Salary / price / budget from number patterns
        nc = self._extract_numeric_condition(text, "salary")
        if nc:
            values["salary"] = nc["value"]

        if table == "products":
            nc = self._extract_numeric_condition(text, "price")
            if nc:
                values["price"] = nc["value"]

        # Try to extract a name / product title (quoted string or proper noun after keywords)
        m = re.search(r'"([^"]+)"', text)
        if m:
            values["name"] = m.group(1)
        else:
            # For employees: look for Surname [Firstname [Patronymic]] pattern.
            # {0,2} — allow single-word surnames like "Петрова" as well as
            # full "Иванов Иван Иванович". Skip sentence-opening verbs.
            candidates = re.findall(r"[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+){0,2}", text)
            skip_values = set(str(v).lower() for v in values.values())
            for c in candidates:
                if (c.lower() not in self._SKIP_INITIAL_WORDS
                        and c.lower() not in skip_values
                        and len(c) > 4):
                    values["name"] = c
                    break

        return values

    # ── SQL generation ───────────────────────────────────────────────────────

    def _build_sql(self, pq: ParsedQuery) -> str:
        intent = pq.intent
        table = pq.table

        if intent == "SELECT":
            cols = ", ".join(pq.columns) if pq.columns != ["*"] else "*"
            sql = f"SELECT {cols} FROM {table}"
            where = self._build_where(pq.conditions)
            if where:
                sql += f" WHERE {where}"

        elif intent == "INSERT":
            if pq.values:
                cols = ", ".join(pq.values.keys())
                vals = ", ".join(
                    str(v) if isinstance(v, (int, float)) else f"'{v}'"
                    for v in pq.values.values()
                )
                sql = f"INSERT INTO {table} ({cols}) VALUES ({vals})"
            else:
                sql = f"INSERT INTO {table} VALUES (?)"

        elif intent == "UPDATE":
            if pq.values:
                assignments = ", ".join(
                    f"{k} = {v}" if isinstance(v, (int, float)) else f"{k} = '{v}'"
                    for k, v in pq.values.items()
                )
                sql = f"UPDATE {table} SET {assignments}"
            else:
                sql = f"UPDATE {table} SET ?"
            where = self._build_where(pq.conditions)
            if where:
                sql += f" WHERE {where}"

        elif intent == "DELETE":
            sql = f"DELETE FROM {table}"
            where = self._build_where(pq.conditions)
            if where:
                sql += f" WHERE {where}"

        else:
            sql = f"-- Unknown intent: {intent}"

        return sql

    def _build_where(self, conditions: dict) -> str:
        parts = []
        for col, val in conditions.items():
            if isinstance(val, dict):                  # numeric comparison
                parts.append(f"{col} {val['op']} {val['value']}")
            elif isinstance(val, str) and "%" in val:  # LIKE
                parts.append(f"{col} LIKE '{val}'")
            elif isinstance(val, (int, float)):
                parts.append(f"{col} = {val}")
            else:
                parts.append(f"{col} = '{val}'")
        return " AND ".join(parts)

    # ── Public API ───────────────────────────────────────────────────────────

    def parse(self, text: str, intent: str) -> ParsedQuery:
        pq = ParsedQuery(intent=intent)
        pq.table = self._detect_table(text)

        conditions: dict = {}
        notes: list = []

        # ── Condition extraction ─────────────────────────────────────────────
        row_id = self._extract_id(text)
        if row_id is not None:
            conditions["id"] = row_id
            notes.append(f"id={row_id}")

        if not row_id:  # id is unambiguous; skip other conditions when present
            city = self._extract_city(text)
            if city:
                conditions["city"] = city
                notes.append(f"city={city}")

            if pq.table == "employees":
                dept = self._extract_department(text)
                if dept:
                    conditions["department"] = dept
                    notes.append(f"department={dept}")

                # Position as WHERE condition for SELECT and DELETE
                if intent in ("SELECT", "DELETE"):
                    pos = self._extract_position(text)
                    if pos:
                        conditions["position"] = pos
                        notes.append(f"position={pos}")

                age_cond = self._extract_numeric_condition(text, "age")
                if age_cond:
                    conditions["age"] = age_cond
                    notes.append(f"age {age_cond['op']} {age_cond['value']}")

                sal_cond = self._extract_numeric_condition(text, "salary")
                if sal_cond and intent == "SELECT":
                    conditions["salary"] = sal_cond
                    notes.append(f"salary {sal_cond['op']} {sal_cond['value']}")

            if pq.table == "products":
                cat = self._extract_category(text)
                if cat:
                    conditions["category"] = cat
                    notes.append(f"category={cat}")

                price_cond = self._extract_numeric_condition(text, "price")
                if price_cond and intent == "SELECT":
                    conditions["price"] = price_cond
                    notes.append(f"price {price_cond['op']} {price_cond['value']}")

            if pq.table == "positions":
                # Allow filtering by department: "должности в отделе ИТ"
                dept = self._extract_department(text)
                if dept:
                    conditions["department"] = dept
                    notes.append(f"department={dept}")

                # Allow filtering by min_salary
                ms_cond = self._extract_numeric_condition(text, "min_salary")
                if ms_cond and intent == "SELECT":
                    conditions["min_salary"] = ms_cond
                    notes.append(f"min_salary {ms_cond['op']} {ms_cond['value']}")

            # Name LIKE — only if no other strong condition
            if not conditions and intent in ("SELECT", "UPDATE", "DELETE"):
                name_frag = self._extract_name_like(text)
                if name_frag:
                    conditions["name"] = f"%{name_frag}%"
                    notes.append(f"name LIKE '%{name_frag}%'")

        pq.conditions = conditions
        pq.parse_notes = notes

        # ── Columns & values ─────────────────────────────────────────────────
        # For lookup tables (positions, departments) always select all columns —
        # there is no useful "column projection" for these small reference tables.
        if pq.table in ("positions", "departments"):
            pq.columns = ["*"]
        else:
            pq.columns = self._extract_columns(text, intent)

        if intent == "INSERT":
            pq.values = self._extract_values_for_insert(text, pq.table)
        elif intent == "UPDATE":
            pq.values = self._extract_values_for_update(text, pq.table)

        pq.raw_sql = self._build_sql(pq)
        return pq