from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from pathlib import Path
from src.utils.logger import logger
import asyncio

class TelethonCollector:
    """
    Менеджер сессии Telethon для сбора данных из чатов.
    """
    
    def __init__(self, api_id: int, api_hash: str, phone: str, session_path: Path):
        self.phone = phone
        self.session_path = str(session_path)
        
        # Ensure session directory exists
        session_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.client = TelegramClient(
            self.session_path,
            api_id,
            api_hash
        )

    async def start_session(self) -> None:
        """
        Запуск сессии.
        Если сессия не авторизована, будет запрошен код (интерактивно в терминале).
        """
        logger.info(f"Connecting to Telegram as {self.phone}...")
        
        try:
            await self.client.connect()
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            raise

        if not await self.client.is_user_authorized():
            logger.warning(f"User {self.phone} not authorized. Starting interactive login...")
            try:
                # client.start() автоматически запрашивает код и пароль в консоли
                await self.client.start(phone=self.phone)
            except Exception as e:
                logger.error(f"Authorization failed: {e}")
                raise
        
        user = await self.client.get_me()
        logger.info(f"Authorized as: {user.first_name} (ID: {user.id})")

    async def stop_session(self) -> None:
        """Корректное завершение сессии"""
        if self.client.is_connected():
            await self.client.disconnect()
            logger.info("Telethon client disconnected")

    async def health_check(self) -> bool:
        """Проверка доступности аккаунта"""
        if not self.client.is_connected():
            logger.warning("Health check: Client not connected")
            return False
            
        try:
            me = await self.client.get_me()
            if me:
                return True
            return False
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
            
    # Context manager support
    async def __aenter__(self):
        await self.start_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop_session()
