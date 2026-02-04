import os
import sys
import unittest
from pathlib import Path
import logging

# Добавляем корень проекта в путь
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

class TestInfrastructure(unittest.TestCase):
    def setUp(self):
        # Подготовка тестового окружения через patch.dict
        self.env_patcher = unittest.mock.patch.dict(os.environ, {
            "TG_API_ID": "1234567",
            "TG_API_HASH": "test_hash_0000000000000000000000000",
            "TG_PHONE": "+79991234567",
            "BOT_TOKEN": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            "BOT_ADMIN_ID": "999999999",
            "COMET_API_KEY": "sk-test-key-1234567890abcdef",
            "GOOGLE_SPREADSHEET_ID": "1A2B3C4D5E6F7G8H9I0J1K2L3M4N5O6P"
        })
        self.env_patcher.start()

    def tearDown(self):
        self.env_patcher.stop()

    def test_settings_load(self):
        """Проверка загрузки настроек"""
        from config import settings
        from config.settings import Settings
        
        # Всегда создаем новый экземпляр настроек для теста, 
        # чтобы гарантированно прочитать значения из os.environ
        cfg = Settings()

        self.assertIsNotNone(cfg)
        self.assertEqual(cfg.telethon.api_id, 1234567)
        self.assertEqual(cfg.telethon.api_hash, "test_hash_0000000000000000000000000")
        self.assertEqual(cfg.app.scan_interval_hours, 6) # Default value checking

    def test_logger_setup(self):
        """Проверка настройки логгера"""
        from src.utils.logger import setup_logger, logger
        
        setup_logger()
        
        # Проверяем запись в файл
        test_msg = "INFRASTRUCTURE TEST MESSAGE"
        logger.info(test_msg)
        
        # Ищем файл лога
        logs_dir = project_root / "logs"
        self.assertTrue(logs_dir.exists())
        
        # Находим самый свежий лог
        log_files = list(logs_dir.glob("app_*.log"))
        self.assertTrue(len(log_files) > 0)
        
        # Читаем последний лог и ищем сообщение
        latest_log = sorted(log_files)[-1]
        content = latest_log.read_text(encoding='utf-8')
        self.assertIn(test_msg, content)
        print(f"Log check passed: found '{test_msg}' in {latest_log.name}")

if __name__ == "__main__":
    unittest.main()
