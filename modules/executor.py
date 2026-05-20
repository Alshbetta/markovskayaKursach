"""
JSON Database Executor.

Emulates a relational database (SELECT / INSERT / UPDATE / DELETE)
backed by a single database.json file.
"""

import json
import os
from typing import Any

from modules.parser import ParsedQuery


class DatabaseExecutor:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._db: dict = {}
        self._load()

    # ── I/O ──────────────────────────────────────────────────────────────────

    def _load(self):
        with open(self.db_path, "r", encoding="utf-8") as f:
            self._db = json.load(f)

    def _save(self):
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(self._db, f, ensure_ascii=False, indent=2)

    def reload(self):
        self._load()

    # ── Row matching ─────────────────────────────────────────────────────────

    def _row_matches(self, row: dict, conditions: dict) -> bool:
        for col, val in conditions.items():
            if col not in row:
                return False
            cell = row[col]
            if isinstance(val, dict):          # numeric comparison
                op, num = val["op"], val["value"]
                try:
                    cell_num = float(cell)
                except (TypeError, ValueError):
                    return False
                ops = {">": cell_num > num, "<": cell_num < num,
                       ">=": cell_num >= num, "<=": cell_num <= num,
                       "=": cell_num == num, "!=": cell_num != num}
                if not ops.get(op, False):
                    return False
            elif isinstance(val, str) and "%" in val:   # LIKE
                pattern = val.replace("%", "").lower()
                if pattern not in str(cell).lower():
                    return False
            else:                                        # equality
                if str(cell).lower() != str(val).lower():
                    return False
        return True

    # ── Operations ───────────────────────────────────────────────────────────

    def _select(self, pq: ParsedQuery) -> dict:
        table_data = self._db.get(pq.table, [])
        rows = [r for r in table_data if self._row_matches(r, pq.conditions)]

        # Column projection
        if pq.columns and pq.columns != ["*"]:
            rows = [{c: r.get(c) for c in pq.columns} for r in rows]

        return {"success": True, "data": rows, "affected": len(rows)}

    def _insert(self, pq: ParsedQuery) -> dict:
        table_data = self._db.get(pq.table)
        if table_data is None:
            return {"success": False, "error": f"Table '{pq.table}' not found", "data": []}
        if not pq.values:
            return {"success": False, "error": "No values provided for INSERT", "data": []}

        new_id = max((r.get("id", 0) for r in table_data), default=0) + 1
        new_row: dict[str, Any] = {"id": new_id, **pq.values}
        table_data.append(new_row)
        self._save()

        return {
            "success": True,
            "data": [new_row],
            "affected": 1,
            "message": f"Inserted 1 row (id={new_id})",
        }

    def _update(self, pq: ParsedQuery) -> dict:
        table_data = self._db.get(pq.table)
        if table_data is None:
            return {"success": False, "error": f"Table '{pq.table}' not found", "data": []}
        if not pq.values:
            return {"success": False, "error": "No SET values provided for UPDATE", "data": []}

        count = 0
        for row in table_data:
            if self._row_matches(row, pq.conditions):
                row.update(pq.values)
                count += 1

        if count:
            self._save()

        return {
            "success": True,
            "data": [],
            "affected": count,
            "message": f"Updated {count} row(s)",
        }

    def _delete(self, pq: ParsedQuery) -> dict:
        table_data = self._db.get(pq.table)
        if table_data is None:
            return {"success": False, "error": f"Table '{pq.table}' not found", "data": []}

        if not pq.conditions:
            return {
                "success": False,
                "error": "DELETE without WHERE is not allowed for safety",
                "data": [],
            }

        before = len(table_data)
        self._db[pq.table] = [r for r in table_data if not self._row_matches(r, pq.conditions)]
        after = len(self._db[pq.table])
        deleted = before - after

        if deleted:
            self._save()

        return {
            "success": True,
            "data": [],
            "affected": deleted,
            "message": f"Deleted {deleted} row(s)",
        }

    # ── Public API ────────────────────────────────────────────────────────────

    def execute(self, pq: ParsedQuery) -> dict:
        """Execute a ParsedQuery against the JSON database."""
        if pq.table not in self._db:
            return {
                "success": False,
                "error": f"Table '{pq.table}' not found. "
                         f"Available: {', '.join(self._db.keys())}",
                "data": [],
            }

        dispatch = {
            "SELECT": self._select,
            "INSERT": self._insert,
            "UPDATE": self._update,
            "DELETE": self._delete,
        }
        handler = dispatch.get(pq.intent)
        if handler is None:
            return {"success": False, "error": f"Unknown intent '{pq.intent}'", "data": []}

        return handler(pq)

    def list_tables(self) -> list[str]:
        return list(self._db.keys())

    def table_schema(self, table: str) -> list[str]:
        rows = self._db.get(table, [])
        return list(rows[0].keys()) if rows else []