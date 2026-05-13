# -*- coding: utf-8 -*-
"""
security.py — Модуль информационной безопасности
Используется для проверки запросов на опасные операции
"""

class QuerySecurityManager:
    """
    Менеджер безопасности SQL-запросов.
    Проверяет запросы на основе классифицированного интента и содержания.
    """

    def __init__(self):
        # Опасные паттерны, которые могут указывать на вредоносные запросы
        self.dangerous_keywords = [
            "drop table", "drop database", "truncate", "delete from",
            "update .* set .* where 1=1", "--", "; drop", "union select",
            "exec", "execute", "xp_cmdshell", "shutdown", "backup"
        ]

    def is_safe_query(self, user_text: str, intent: str, sql: str, conditions: dict = None) -> dict:
        """
        Основная функция проверки безопасности запроса.
        
        Returns:
            dict: Результат проверки с уровнем риска и рекомендацией
        """
        text_lower = user_text.lower()
        sql_lower = sql.lower()

        result = {
            "safe": True,
            "risk_level": "low",
            "reason": "Запрос признан безопасным",
            "recommended_action": "ALLOW"
        }

        # 1. Проверка опасных интентов без условий
        if intent == "DELETE" and not conditions:
            result.update({
                "safe": False,
                "risk_level": "high",
                "reason": "Попытка удаления данных без условий WHERE (опасная операция)",
                "recommended_action": "BLOCK"
            })
            return result

        if intent == "UPDATE" and not conditions:
            result.update({
                "safe": False,
                "risk_level": "medium",
                "reason": "Обновление данных без условий WHERE",
                "recommended_action": "BLOCK"
            })
            return result

        # 2. Проверка подозрительных ключевых слов
        for keyword in self.dangerous_keywords:
            if keyword in text_lower or keyword in sql_lower:
                result.update({
                    "safe": False,
                    "risk_level": "critical",
                    "reason": f"Обнаружен опасный паттерн: '{keyword}'",
                    "recommended_action": "BLOCK"
                })
                return result

        # 3. Проверка запросов на массовое удаление/изменение
        mass_delete_words = ["всех", "все", "удали всё", "очисти таблиц", "удалить всех", "удали всех"]
        if any(word in text_lower for word in mass_delete_words):
            if intent in ["DELETE", "UPDATE"]:
                result.update({
                    "safe": False,
                    "risk_level": "high",
                    "reason": "Запрос на массовое удаление или изменение данных",
                    "recommended_action": "BLOCK"
                })
                return result

        # 4. Дополнительная проверка для DELETE
        if intent == "DELETE" and conditions and len(conditions) == 0:
            result.update({
                "safe": False,
                "risk_level": "high",
                "reason": "DELETE-запрос без условий",
                "recommended_action": "BLOCK"
            })

        return result

    def print_security_report(self, result: dict):
        """Красивый вывод отчёта о безопасности"""
        if result["safe"]:
            print(f"  Безопасность: OK (уровень риска: {result['risk_level']})")
            print(f"   Причина: {result['reason']}")
        else:
            print(f" ВНИМАНИЕ! Уровень риска: {result['risk_level'].upper()}")
            print(f"   Причина: {result['reason']}")
            print("    Запрос **заблокирован** системой безопасности!")
        
        print("-" * 60)