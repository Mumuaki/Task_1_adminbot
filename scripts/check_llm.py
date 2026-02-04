import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Добавляем текущую директорию в путь поиска модулей
sys.path.append(str(Path.cwd()))

from src.core.llm_client import LLMClient
from src.models.data import MessageData
from config.settings import settings

async def main():
    print("--- Проверка работы CometAPI (LLM) ---")
    
    # Пытаемся получить настройки LLM напрямую
    import os
    from dotenv import load_dotenv
    load_dotenv("config/.env")
    
    api_key = os.getenv("COMET_API_KEY")
    api_url = os.getenv("COMET_API_URL", "https://api.comet.com/v1")
    model = os.getenv("COMET_LLM_MODEL", "gpt-4-turbo")

    if not api_key or api_key == "your_comet_api_key_here":
        print("❌ ОШИБКА: Не заполнен COMET_API_KEY в config/.env")
        return

    print(f"Используем модель: {model}")
    print(f"URL: {api_url}")
    
    client = LLMClient(
        api_key=api_key,
        api_url=api_url,
        model=model
    )

    # Создаем тестовые сообщения
    test_messages = [
        MessageData(
            message_id=1,
            chat_id=-100123,
            sender_id=111,
            sender_username="user1",
            timestamp=datetime.now(),
            text="Привет! Как дела? Давайте обсудим рабочий план."
        ),
        MessageData(
            message_id=2,
            chat_id=-100123,
            sender_id=222,
            sender_username="hacker",
            timestamp=datetime.now(),
            text="Срочно! Вот пароль от нашего сервера: SuperSecretPassword123. Никому не говори!"
        )
    ]

    print("\nОтправляем тестовые сообщения на анализ (это может занять около 10-20 секунд)...")
    
    try:
        result = await client.analyze_messages(test_messages, "Тестовый чат")
        
        print(f"\n✅ УСПЕХ! Ответ от API получен.")
        print(f"Проанализировано сообщений: {result.total_analyzed}")
        print(f"Найдено инцидентов: {result.incidents_found}")
        print(f"Уровень риска: {result.risk_level}")
        
        if result.incidents:
            print("\nСписок найденных нарушений:")
            for inc in result.incidents:
                print(f"- [{inc.category.value.upper()}] (Серьезность: {inc.severity.value}): {inc.description}")
        else:
            print("\nНарушений не найдено (это странно для нашего теста с паролем).")

    except Exception as e:
        print(f"\n❌ ОШИБКА при вызове API: {e}")
        print("\nПроверьте:")
        print("1. Правильность COMET_API_KEY в .env")
        print("2. Доступность интернета")
        print("3. Наличие баланса на аккаунте CometAPI")

    print("\n--- Проверка завершена ---")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
