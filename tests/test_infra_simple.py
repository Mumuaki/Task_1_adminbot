import os
import sys
import unittest
from pathlib import Path
import logging

# Устанавливаем минимально необходимые переменные окружения
# чтобы Pydantic не ругался при импорте settings
os.environ["TG_API_ID"] = "12345"
os.environ["TG_API_HASH"] = "test_hash_0000000000000000000000000"
os.environ["TG_PHONE"] = "+79991234567"
os.environ["BOT_TOKEN"] = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
os.environ["BOT_ADMIN_ID"] = "999999999"
os.environ["COMET_API_KEY"] = "sk-test-key-1234567890abcdef"
os.environ["GOOGLE_SPREADSHEET_ID"] = "1A2B3C4D5E6F7G8H9I0J1K2L3M4N5O6P"

# Добавляем корень проекта в путь
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

class TestInfrastructure(unittest.TestCase):
    def test_settings_load(self):
        """Проверка загрузки настроек"""
        from config import settings
        from config.settings import Settings
        
        # Если импорт прошел и settings создался (может потребоваться пересоздать если глобальный failed)
        if settings.settings is None:
             # Попробуем создать вручную, так как ENV мы задали выше
            cfg = Settings()
        else:
            cfg = settings.settings

        self.assertIsNotNone(cfg)
        self.assertEqual(cfg.telethon.api_id, 12345)
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
