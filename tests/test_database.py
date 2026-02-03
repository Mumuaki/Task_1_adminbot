import unittest
import asyncio
from pathlib import Path
import os
import sys

# Добавляем корень в путь
sys.path.append(str(Path(__file__).parent.parent))

from src.storage.database import DatabaseManager

class TestDatabase(unittest.IsolatedAsyncioTestCase):
    async def test_init_db(self):
        """Проверка инициализации БД и создания таблиц"""
        test_db_path = Path("data/test_db.sqlite")
        
        # Чистка перед тестом
        if test_db_path.exists():
            os.remove(test_db_path)
            
        try:
            db = DatabaseManager(test_db_path)
            await db.init_db()
            
            self.assertTrue(test_db_path.exists(), "DB file was not created")
            
            # Проверим таблицы
            conn = await db.get_connection()
            try:
                cursor = await conn.execute("SELECT name FROM sqlite_master WHERE type='table';")
                rows = await cursor.fetchall()
                # rows - это объекты Row, приводим к строкам или обращаемся по ключу
                tables = [row[0] for row in rows] # row[0] is 'name' column
                
                required_tables = ['messages', 'incidents', 'participants', 'scan_logs']
                for table in required_tables:
                    self.assertIn(table, tables, f"Table {table} missing")
                    
            finally:
                await conn.close()
                
        finally:
            # Cleanup
            if test_db_path.exists():
                try:
                    os.remove(test_db_path)
                except PermissionError:
                    pass # Иногда файл залочен Windows, если коннект не закрылся

if __name__ == "__main__":
    unittest.main()
