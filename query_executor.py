# -*- coding: utf-8 -*-
"""
query_executor.py — Исполнитель SQL-запросов на JSON базе данных
Эмулирует выполнение SQL-запросов SELECT, INSERT, UPDATE, DELETE
"""
import json
import copy
import os
import glob
from datetime import datetime


class JSONDatabase:
    """Простая эмуляция реляционной БД на основе JSON"""

    def __init__(self, db_path="database.json"):
        """Загрузка базы данных из JSON файла"""
        self.db_path = db_path
        self.data = self._load_db()
        self.changes_log = []  # Лог изменений для аудита

    def _load_db(self):
        """Загрузка данных из JSON файла"""
        try:
            with open(self.db_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"  Файл {self.db_path} не найден. Создаётся пустая БД...")
            return {"users": [], "orders": [], "departments": []}

    def save_db(self):
        """Сохранение изменений в JSON файл"""
        with open(self.db_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        print(f" База данных сохранена в {self.db_path}")

    def _create_backup(self):
        """Автоматически сохраняет копию текущего состояния БД"""
        if not os.path.exists("backups"):
            os.makedirs("backups")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"backups/database_{timestamp}.json"
        try:
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            print(f"    Бэкап создан: {backup_path}")
        except Exception as e:
            print(f"    Ошибка создания бэкапа: {e}")

    def execute_select(self, table, conditions=None, columns="*"):
        """
        Эмуляция SELECT запроса (Обновленная версия с поддержкой операторов)
        """
        if table not in self.data:
            print(f" Таблица '{table}' не найдена!")
            return []
        
        results = self.data[table]
        
        # Применение условий WHERE
        if conditions:
            filtered = []
            for row in results:
                match = True
                for key, value in conditions.items():
                    row_val = row.get(key)
                    
                    # 1. Если условие — кортеж с оператором, например ('>', 80000)
                    if isinstance(value, tuple) and len(value) == 2:
                        op, target = value
                        if op == '>' and not (row_val > target):
                            match = False
                        elif op == '<' and not (row_val < target):
                            match = False
                        elif op == '=' and not (row_val == target):
                            match = False
                    # 2. Обычное сравнение на равенство (например, city='Москва')
                    else:
                        if row_val != value:
                            match = False
                    
                    if not match:
                        break
                
                if match:
                    filtered.append(row)
            results = filtered

        # Выборка конкретных колонок
        if columns not in ("*", ["*"]):
            if isinstance(columns, str):
                columns = [c.strip() for c in columns.split(",")]
            results = [{k: v for k, v in row.items() if k in columns} for row in results]
        
        return results

    def execute_insert(self, table, record):
        """
        Эмуляция INSERT запроса
        """
        if table not in self.data:
            print(f" Таблица '{table}' не найдена!")
            return False
        
        # Автогенерация ID
        if "id" not in record and self.data[table]:
            max_id = max(row.get("id", 0) for row in self.data[table])
            record["id"] = max_id + 1
        elif "id" not in record:
            record["id"] = 1
        
        self.data[table].append(record)
        
        # Логирование
        self.changes_log.append({
            "operation": "INSERT",
            "table": table,
            "record": record,
            "timestamp": datetime.now().isoformat()
        })
        
        print(f" Добавлена запись в таблицу '{table}': {record}")
        return True

    def execute_update(self, table, updates, conditions):
        """
        Эмуляция UPDATE запроса
        """
        if table not in self.data:
            print(f" Таблица '{table}' не найдена!")
            return 0
        
        self._create_backup()

        count = 0
        for row in self.data[table]:
            match = True
            for key, value in conditions.items():
                if row.get(key) != value:
                    match = False
                    break
            
            if match:
                row.update(updates)
                count += 1
        
        # Логирование
        if count > 0:
            self.changes_log.append({
                "operation": "UPDATE",
                "table": table,
                "updates": updates,
                "conditions": conditions,
                "affected_rows": count,
                "timestamp": datetime.now().isoformat()
            })
            print(f" Обновлено {count} записей в таблице '{table}'")
        
        return count

    def execute_delete(self, table, conditions):
        """
        Эмуляция DELETE запроса
        """
        if table not in self.data:
            print(f" Таблица '{table}' не найдена!")
            return 0
        
        self._create_backup()

        original_count = len(self.data[table])
        
        # ИСПРАВЛЕНО: убрана опечатка "fo r" -> "for"
        self.data[table] = [
            row for row in self.data[table]
            if not all(row.get(k) == v for k, v in conditions.items())
        ]
        
        deleted_count = original_count - len(self.data[table])
        
        # Логирование
        if deleted_count > 0:
            self.changes_log.append({
                "operation": "DELETE",
                "table": table,
                "conditions": conditions,
                "deleted_rows": deleted_count,
                "timestamp": datetime.now().isoformat()
            })
            print(f"✅ Удалено {deleted_count} записей из таблицы '{table}'")
        
        return deleted_count

    def show_table(self, table):
        """Отображение содержимого таблицы"""
        if table not in self.data:
            print(f"❌ Таблица '{table}' не найдена!")
            return
        
        print(f"\n Таблица '{table}' ({len(self.data[table])} записей):")
        print("-" * 80)
        
        if not self.data[table]:
            print("   (пусто)")
            return
        
        # Заголовки
        headers = list(self.data[table][0].keys())
        print("   | " + " | ".join(f"{h:15}" for h in headers) + " |")
        print("   |" + "|".join(f"{'-'*15}" for _ in headers) + "|")
        
        # Данные (первые 10 записей)
        for i, row in enumerate(self.data[table][:10]):
            values = [str(row.get(h, ""))[:15] for h in headers]
            print(f" {i+1:2}| " + " | ".join(f"{v:15}" for v in values) + " |")
        
        if len(self.data[table]) > 10:
            print(f"   ... и ещё {len(self.data[table]) - 10} записей")
        
        print("-" * 80)

    def show_changes_log(self):
        """Отображение лога изменений"""
        if not self.changes_log:
            print("\n📋 Лог изменений: (нет изменений)")
            return
        
        print(f"\n Лог изменений ({len(self.changes_log)} операций):")
        print("-" * 80)
        for entry in self.changes_log:
            print(f"  [{entry['timestamp'][:19]}] {entry['operation']:8} {entry['table']:12}")
        print("-" * 80)

    def restore_latest(self):
        """Восстанавливает БД из последнего бэкапа"""
        backups = sorted(glob.glob("backups/database_*.json"))
        if not backups:
            print(" Бэкапы не найдены. Убедитесь, что папка 'backups/' существует и содержит файлы.")
            return False
        latest = backups[-1]
        with open(latest, 'r', encoding='utf-8') as f:
            self.data = json.load(f)
        print(f" База восстановлена из: {latest}")
        return True