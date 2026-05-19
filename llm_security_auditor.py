# -*- coding: utf-8 -*-
"""
llm_security_auditor.py — LLM-аудитор безопасности SQL-запросов
Использует zero-shot классификацию + эвристики для детекции инъекций (CWE-89)
"""

import re
from transformers import pipeline


class LLMSecurityAuditor:
    """Аудитор безопасности на основе LLM"""

    def __init__(self):
        print("   [LLM Security] Загрузка модели facebook/bart-large-mnli...")
        self.classifier = pipeline(
            "zero-shot-classification",
            model="facebook/bart-large-mnli",
            device=-1  # -1 = CPU, 0 = GPU (если есть)
        )

        # Опасные паттерны (быстрая фильтрация)
        self.dangerous_patterns = {
            r"OR\s+['\"]?1['\"]?\s*=\s*['\"]?1": "Authentication Bypass (Tautology)",
            r"UNION\s+(ALL\s+)?SELECT": "UNION-based SQL Injection",
            r";\s*(DROP|DELETE|TRUNCATE|ALTER|UPDATE|INSERT)": "Command Stacking",
            r"--\s*$|/\*.*\*/": "SQL Comment Injection",
            r"'\s*OR\s*": "Tautology Attack",
            r"1\s*=\s*1": "Always True Condition",
            r"DROP\s+TABLE": "DROP TABLE Attempt",
        }

    def audit_sql(self, sql_query: str, user_input: str = None) -> dict:
        """Проверяет SQL-запрос на безопасность"""
        
        # 1. Эвристический анализ (высокий приоритет)
        for pattern, threat in self.dangerous_patterns.items():
            if re.search(pattern, sql_query, re.IGNORECASE):
                return {
                    "is_safe": False,
                    "risk_level": "HIGH",
                    "cwe": "CWE-89",
                    "threat_type": threat,
                    "explanation": f"Обнаружен опасный паттерн: {threat}",
                    "recommendation": "Запрос заблокирован"
                }

        # 2. Семантический анализ через LLM
        analysis_text = f"SQL: {sql_query}"
        if user_input:
            analysis_text += f" | Пользователь: {user_input}"

        result = self.classifier(
            analysis_text,
            candidate_labels=["безопасный запрос", "подозрительный запрос", "SQL-инъекция"],
            multi_label=False
        )

        label = result['labels'][0]
        confidence = result['scores'][0]

        # Доверяем LLM только при высокой уверенности
        if ("инъекц" in label.lower() or "подозрительн" in label.lower()) and confidence > 0.52:
            return {
                "is_safe": False,
                "risk_level": "MEDIUM",
                "cwe": "CWE-89",
                "threat_type": label,
                "explanation": f"LLM: {label} ({confidence:.1%})",
                "recommendation": "Требуется проверка"
            }

        # Безопасный запрос
        return {
            "is_safe": True,
            "risk_level": "LOW",
            "cwe": "N/A",
            "threat_type": None,
            "explanation": f"LLM: {label} ({confidence:.1%})",
            "recommendation": "Разрешить выполнение"
        }