import asyncio
import sys
from pathlib import Path

# Добавляем текущую директорию в путь поиска модулей
sys.path.append(str(Path.cwd()))

from src.storage.sheets import GoogleSheetsManager
from config.settings import settings
from src.utils.logger import logger

async def main():
    print("--- Проверка интеграции с Google Sheets ---")
    
    # Пытаемся получить настройки Google Sheets напрямую, если общий объект не загрузился
    try:
        from config.settings import GoogleSheetsSettings
        gs_settings = GoogleSheetsSettings()
        spreadsheet_id = gs_settings.spreadsheet_id
        service_account_path = gs_settings.service_account_path
    except Exception:
        # Если даже так не вышло, пробуем через переменные окружения напрямую или значения по умолчанию
        import os
        spreadsheet_id = os.getenv("GOOGLE_SPREADSHEET_ID")
        service_account_path = Path("config/service_account.json")

    if not spreadsheet_id or spreadsheet_id == "your_spreadsheet_id_here":
        print("❌ ОШИБКА: Не заполнен GOOGLE_SPREADSHEET_ID в config/.env")
        return

    if not service_account_path.exists():
        print(f"❌ ОШИБКА: Файл {service_account_path} не найден!")
        return

    print(f"Используем таблицу: {spreadsheet_id}")
    
    manager = GoogleSheetsManager(
        spreadsheet_id=spreadsheet_id,
        service_account_path=service_account_path
    )

    print("\n1. Пробуем прочитать Whitelist из листа 'Конфигурация'...")
    whitelist = await manager.get_whitelist()
    
    if whitelist:
        print(f"✅ УСПЕХ! Найдено ID: {whitelist}")
    else:
        print("⚠️ Либо список пуст, либо нет доступа к листу 'Конфигурация'")
        print("Убедитесь, что в таблице есть лист с именем 'Конфигурация' и в первой колонке вписаны ID.")

    print("\n--- Проверка завершена ---")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"❌ Произошла непредвиденная ошибка: {e}")
