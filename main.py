import asyncio
import sys
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

from config.settings import settings
from src.collector.client import TelethonCollector
from src.collector.history import MessageHistoryCollector
from src.collector.participants import ParticipantCollector
from src.manager.bot import TelegramBot
from src.manager.notifier import IncidentNotifier
from src.core.llm_client import LLMClient
from src.core.whisper import WhisperClient
from src.core.analyzer import ContentAnalyzer
from src.scheduler.jobs import ScanJob
from src.scheduler.health import HealthCheckJob
from src.storage.database import DatabaseManager
from src.storage.sheets import GoogleSheetsManager
from src.utils.logger import setup_logger

async def main():
    """Точка входа приложения"""
    
    # 1. Настройка логирования
    setup_logger()
    logger.info("Starting Telegram Monitor System")
    
    if not settings:
        logger.error("Settings not loaded. Exiting.")
        return

    # 2. Инициализация БД
    db_manager = DatabaseManager()
    await db_manager.init_db()
    logger.info("Database initialized")
    
    # 3. Инициализация Telethon (Collector)
    telethon_collector = TelethonCollector(
        api_id=settings.telethon.api_id,
        api_hash=settings.telethon.api_hash,
        phone=settings.telethon.phone,
        session_path=settings.telethon.session_path
    )
    
    # Запускаем сессию Telethon (здесь может потребоваться интерактивный вход)
    await telethon_collector.start_session()
    logger.info("Telethon collector session started")
    
    # 4. Инициализация компонентов сбора и анализа
    message_collector = MessageHistoryCollector(telethon_collector.client)
    
    llm_client = LLMClient(
        api_key=settings.comet_api.api_key,
        api_url=settings.comet_api.api_url,
        model=settings.comet_api.llm_model
    )
    
    whisper_client = WhisperClient(
        api_key=settings.comet_api.api_key,
        api_url=settings.comet_api.api_url,
        model=settings.comet_api.whisper_model
    )
    
    analyzer = ContentAnalyzer(llm_client, whisper_client, db_manager)
    
    # 5. Инициализация Bot и Notifier
    bot = TelegramBot(
        token=settings.aiogram.token,
        admin_id=settings.aiogram.admin_id,
        db_manager=db_manager
    )
    # Инициализация webhook/polling логики внутри бота (если есть) или просто создание instance
    # В текущей реализации TelegramBot сам создает Bot instance
    
    notifier = IncidentNotifier(bot.bot) # bot.bot - доступ к объекту aiogram.Bot шз враппер
    logger.info("Telegram bot initialized")
    
    # 6. Инициализация Scheduler и ScanJob
    scheduler = AsyncIOScheduler()
    
    # Инициализация Google Sheets Manager
    sheets_manager = GoogleSheetsManager(
        spreadsheet_id=settings.google_sheets.spreadsheet_id,
        service_account_path=settings.google_sheets.service_account_path
    )
    logger.info("Google Sheets manager initialized")
    
    # Получаем список чатов для мониторинга из Google Sheets
    try:
        monitored_chats = await sheets_manager.get_monitored_chats()
        if not monitored_chats:
            logger.warning("No monitored chats configured in Google Sheets! Scan job will do nothing.")
    except Exception as e:
        logger.error(f"Failed to load monitored chats from Google Sheets: {e}")
        logger.warning("Falling back to settings.app.monitored_chats")
        # Fallback на статическую конфигурацию
        monitored_chats = [(chat_id, f"Chat_{chat_id}") for chat_id in settings.app.monitored_chats]
    
    # Извлекаем только chat_id для совместимости с текущим ScanJob
    chat_ids = [chat_id for chat_id, _ in monitored_chats]
    
    # Создаём ParticipantCollector для проверки участников
    participant_collector = ParticipantCollector(telethon_collector.client)
    logger.info("Participant collector initialized")
    
    scan_job = ScanJob(
        collector=message_collector,
        participant_collector=participant_collector,
        analyzer=analyzer,
        notifier=notifier,
        db_manager=db_manager,
        sheets_manager=sheets_manager,
        chat_ids=chat_ids
    )
    
    # Регистрация scan_job и notifier в боте для доступа из команд
    bot.scan_job = scan_job
    bot.notifier = notifier
    bot.dp["scan_job"] = scan_job
    bot.dp["notifier"] = notifier

    
    # Добавление задач
    scheduler.add_job(
        scan_job.run,
        trigger='interval',
        hours=settings.app.scan_interval_hours,
        id='main_scan',
        replace_existing=True,
        max_instances=1
    )
    logger.info(f"Scan job scheduled every {settings.app.scan_interval_hours} hours for {len(chat_ids)} chats")
    
    # Регистрация и настройка Health Check
    health_check_job = HealthCheckJob(
        bot=bot.bot,
        telethon_client=telethon_collector.client,
        db=db_manager,
        admin_id=settings.aiogram.admin_id
    )
    
    scheduler.add_job(
        health_check_job.run,
        trigger='interval',
        minutes=30,
        id='health_check',
        replace_existing=True,
        max_instances=1
    )
    logger.info("Health check job scheduled every 30 minutes")
    
    # 7. Запуск
    scheduler.start()
    logger.info("Scheduler started")
    
    # Запуск бота (blocking)
    try:
        await bot.start_polling()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Critical error: {e}")
    finally:
        scheduler.shutdown()
        await telethon_collector.stop_session()
        logger.info("Shutdown complete")

if __name__ == "__main__":
    # Windows SelectorEventLoop policy fix for Python 3.8+
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    asyncio.run(main())
