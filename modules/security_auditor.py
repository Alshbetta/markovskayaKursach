"""
LLM Security Auditor — two-stage SQL injection detection.

Stage 1 (Regex): Fast pattern matching for known injection signatures.
Stage 2 (LLM):  Zero-shot classification via facebook/bart-large-mnli.
                Performs semantic analysis that regex cannot catch.

CWE reference: CWE-89 — Improper Neutralization of Special Elements
               used in an SQL Command ('SQL Injection').
"""

import re
import time
from typing import Optional

import config


# ── Regex patterns for known SQL injection signatures ────────────────────────

INJECTION_PATTERNS: list[tuple[str, str]] = [
    # Tautology-based
    (r"(?i)\bOR\b\s+['\"]?\d+['\"]?\s*=\s*['\"]?\d+['\"]?",   "OR numeric tautology"),
    (r"(?i)\bOR\b\s+'[^']*'\s*=\s*'[^']*'",                    "OR string tautology"),
    (r"(?i)\bAND\b\s+['\"]?\d+['\"]?\s*=\s*['\"]?\d+['\"]?",  "AND numeric tautology"),
    # UNION-based
    (r"(?i)\bUNION\b\s+\bSELECT\b",                            "UNION SELECT"),
    (r"(?i)\bUNION\b\s+\bALL\b\s+\bSELECT\b",                 "UNION ALL SELECT"),
    # DDL injection
    (r"(?i)\bDROP\b\s+\bTABLE\b",                              "DROP TABLE"),
    (r"(?i)\bDROP\b\s+\bDATABASE\b",                           "DROP DATABASE"),
    (r"(?i)\bTRUNCATE\b\s+\bTABLE\b",                          "TRUNCATE TABLE"),
    (r"(?i)\bALTER\b\s+\bTABLE\b",                             "ALTER TABLE"),
    # Stacked queries
    (r";\s*\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|EXEC)\b", "Stacked query"),
    # Comment injection
    (r"--(?:[^-]|$)",                                           "SQL comment (--)"),
    (r"/\*.*?\*/",                                              "Block comment (/* */)"),
    (r"#(?:\s|$)",                                              "MySQL comment (#)"),
    # Stored procedure / system calls
    (r"(?i)\bEXEC\b\s*\(",                                      "EXEC()"),
    (r"(?i)\bEXECUTE\b\s*\(",                                   "EXECUTE()"),
    (r"(?i)\bxp_\w+",                                           "Extended stored procedure"),
    (r"(?i)\bsp_\w+",                                           "System stored procedure"),
    # Time-based blind injection
    (r"(?i)\bSLEEP\b\s*\(\d+\)",                               "SLEEP() blind injection"),
    (r"(?i)\bWAITFOR\b\s+\bDELAY\b",                           "WAITFOR DELAY"),
    (r"(?i)\bBENCHMARK\b\s*\(",                                 "BENCHMARK() blind injection"),
    # String escape sequences
    (r"'[^']*'[^']*=\s*'",                                     "String comparison bypass"),
    (r"(?i)\bCHAR\b\s*\(\d+",                                  "CHAR() encoding bypass"),
    (r"(?i)0x[0-9a-fA-F]{4,}",                                 "Hex encoding"),
    # Boolean-based
    (r"(?i)\bOR\b\s+\bTRUE\b",                                 "OR TRUE"),
    (r"(?i)\bAND\b\s+\bFALSE\b",                               "AND FALSE"),
]


class SecurityAuditor:
    """
    Two-stage SQL injection auditor.

    Parameters
    ----------
    use_llm : bool
        Whether to load and use the BART LLM for Stage 2.
        Setting to False makes the system regex-only (faster, lighter).
    """

    def __init__(self, use_llm: bool = True):
        self.use_llm = use_llm
        self._llm = None
        self._llm_available = False
        if use_llm:
            self._load_llm()

    # ── LLM loading ──────────────────────────────────────────────────────────

    def _load_llm(self):
        try:
            from transformers import pipeline
            print("  [LLM] Загрузка модели facebook/bart-large-mnli...")
            t0 = time.time()
            self._llm = pipeline(
                "zero-shot-classification",
                model=config.LLM_MODEL,
                device=-1,        # CPU; set to 0 for GPU
            )
            elapsed = round(time.time() - t0, 1)
            self._llm_available = True
            print(f"  [LLM] Модель загружена за {elapsed}с")
        except Exception as exc:
            print(f"  [LLM] Предупреждение: модель недоступна ({exc})")
            self._llm = None
            self._llm_available = False

    # ── Stage 1: Regex ────────────────────────────────────────────────────────

    def _stage1_regex(self, combined_text: str) -> dict:
        """Check the combined (input + SQL) string against known patterns."""
        detected: list[str] = []
        for pattern, name in INJECTION_PATTERNS:
            if re.search(pattern, combined_text):
                detected.append(name)

        return {
            "safe": len(detected) == 0,
            "detected_patterns": detected,
        }

    # ── Stage 2: LLM ─────────────────────────────────────────────────────────

    def _stage2_llm(self, natural_input: str, generated_sql: str) -> dict:
        """
        Semantic zero-shot classification using BART-large-MNLI.

        We intentionally analyse only the *natural-language input*, NOT the
        generated SQL.  Reason: the regex stage already covers all SQL-syntax
        patterns.  Feeding the SQL into the LLM causes false positives because
        the English model sees Cyrillic text mixed with SQL keywords and
        incorrectly associates them with the "injection" label.
        """
        if not self._llm_available:
            return {
                "safe": True,
                "confidence": 0.0,
                "label": "LLM not available — skipped",
                "all_scores": {},
            }

        # Wrap in a clear English frame so the NLI model has context even for
        # non-English user inputs.
        prompt = f"A user typed this message into a database interface: {natural_input}"

        try:
            result = self._llm(prompt, config.LLM_CANDIDATE_LABELS)
            top_label: str = result["labels"][0]
            top_score: float = result["scores"][0]
            all_scores = dict(zip(result["labels"], result["scores"]))

            is_safe = "normal" in top_label.lower() or "query" in top_label.lower()
            return {
                "safe": is_safe,
                "confidence": round(top_score, 4),
                "label": top_label,
                "all_scores": {k: round(v, 4) for k, v in all_scores.items()},
            }
        except Exception as exc:
            return {
                "safe": True,
                "confidence": 0.0,
                "label": f"LLM error: {exc}",
                "all_scores": {},
            }

    # ── Public API ────────────────────────────────────────────────────────────

    def audit(self, natural_input: str, generated_sql: str) -> dict:
        """
        Full two-stage security audit.

        Returns
        -------
        dict with keys:
          natural_input, generated_sql,
          stage1 (regex result),
          stage2 (LLM result),
          final_verdict: "SAFE" | "BLOCKED_REGEX" | "BLOCKED_LLM",
          blocked: bool
        """
        result = {
            "natural_input": natural_input,
            "generated_sql": generated_sql,
            "stage1": {},
            "stage2": {},
            "final_verdict": "SAFE",
            "blocked": False,
        }

        # Stage 1 — Regex
        combined = f"{natural_input} {generated_sql}"
        stage1 = self._stage1_regex(combined)
        result["stage1"] = stage1

        if not stage1["safe"]:
            result["final_verdict"] = "BLOCKED_REGEX"
            result["blocked"] = True
            return result

        # Stage 2 — LLM
        stage2 = self._stage2_llm(natural_input, generated_sql)
        result["stage2"] = stage2

        if (
            self._llm_available
            and not stage2["safe"]
            and stage2["confidence"] >= config.LLM_DANGER_THRESHOLD
        ):
            result["final_verdict"] = "BLOCKED_LLM"
            result["blocked"] = True

        return result

    @property
    def llm_available(self) -> bool:
        return self._llm_available