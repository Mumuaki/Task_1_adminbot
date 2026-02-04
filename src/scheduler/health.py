import asyncio
import aiosqlite
from aiogram import Bot
from telethon import TelegramClient
from src.storage.database import DatabaseManager
from src.utils.logger import logger
from datetime import datetime

class HealthCheckJob:
    """
    Задача для периодической проверки работоспособности всех компонентов системы.
    """
    
    def __init__(
        self, 
        bot: Bot, 
        telethon_client: TelegramClient, 
        db: DatabaseManager, 
        admin_id: int
    ):
        """
        Инициализация задачи.
        
        Параметры:
            bot: Клиент aiogram (Manager)
            telethon_client: Клиент Telethon (Collector)
            db: Менеджер базы данных
            admin_id: Telegram ID администратора для уведомлений
        """
        self.bot = bot
        self.telethon_client = telethon_client
        self.db = db
        self.admin_id = admin_id

    async def check_telethon(self) -> bool:
        """Проверка подключения клиента Telethon."""
        try:
            return self.telethon_client.is_connected()
        except Exception as e:
            logger.error(f"HealthCheck: Telethon check failed: {e}")
            return False

    async def check_bot(self) -> bool:
        """Проверка доступности Telegram Bot API."""
        try:
            await self.bot.get_me()
            return True
        except Exception as e:
            logger.error(f"HealthCheck: Bot check failed: {e}")
            return False

    async def check_database(self) -> bool:
        """Проверка работоспособности SQLite."""
        try:
            async with aiosqlite.connect(self.db.db_path) as db:
                await db.execute("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"HealthCheck: Database check failed: {e}")
            return False

    async def run(self):
        """Запуск всех проверок и отправка уведомления при сбоях."""
        logger.info("Running scheduled Health Check...")
        
        results = await asyncio.gather(
            self.check_telethon(),
            self.check_bot(),
            self.check_database(),
            return_exceptions=True
        )
        
        # Обработка результатов gather (могут быть исключения)
        clean_results = []
        for res in results:
            if isinstance(res, Exception):
                clean_results.append(False)
            else:
                clean_results.append(res)
        
        is_telethon_ok, is_bot_ok, is_db_ok = clean_results
        
        if not all(clean_results):
            errors = []
            if not is_telethon_ok: errors.append("Telethon (Collector) disconnect")
            if not is_bot_ok: errors.append("Telegram Bot API (Manager) unreachable")
            if not is_db_ok: errors.append("Database (SQLite) connection failed")
            
            timestamp = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
            error_msg = (
                f"🚨 <b>SYSTEM HEALTH ALERT</b>\n"
                f"Time: {timestamp}\n\n"
                f"Detected failures:\n" + 
                "\n".join([f"❌ {e}" for e in errors]) +
                "\n\n<i>Immediate intervention required!</i>"
            )
            
            logger.critical(f"Health Check failed: {', '.join(errors)}")
            
            try:
                await self.bot.send_message(self.admin_id, error_msg, parse_mode="HTML")
            except Exception as e:
                logger.error(f"Failed to send Health Check alert to admin {self.admin_id}: {e}")
        else:
            logger.info("Health Check: All systems operational")
