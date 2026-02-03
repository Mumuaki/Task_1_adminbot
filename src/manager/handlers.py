from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from src.utils.logger import logger
from config.settings import settings



router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message):
    """
    Команда /start - приветствие и справка.
    
    Отправляет приветственное сообщение со списком доступных команд.
    """
    logger.info(f"User {message.from_user.id} sent /start")
    
    await message.answer(
        "🤖 <b>Система мониторинга чатов v1.0 (MVP)</b>\n\n"
        "Доступные команды:\n"
        "/status - Текущее состояние системы\n"
        "/help - Справка"
    )


@router.message(Command("status"))
async def cmd_status(message: Message):
    """
    Команда /status - статус системы.
    
    Показывает текущее состояние системы мониторинга:
    - Статус бота
    - Количество отслеживаемых чатов
    - Интервал сканирования
    """
    logger.info(f"User {message.from_user.id} sent /status")
    
    # Упрощённая версия для MVP
    # В полной версии будет читаться из Google Sheets
    chats_count = 30
    scan_interval = settings.app_scan_interval_hours
    
    await message.answer(
        "📊 <b>Статус системы:</b>\n\n"
        f"✅ Бот: Активен\n"
        f"📁 Чатов на мониторинге: {chats_count}\n"
        f"🕐 Интервал сканирования: каждые {scan_interval} ч"
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    """
    Команда /help - справка по использованию.
    
    Выводит детальную информацию о доступных командах.
    """
    logger.info(f"User {message.from_user.id} sent /help")
    
    await message.answer(
        "📖 <b>Справка по командам:</b>\n\n"
        "/start - Показать приветствие\n"
        "/status - Состояние системы\n"
        "/help - Эта справка\n\n"
        "Система автоматически сканирует чаты и отправляет уведомления о найденных инцидентах."
    )
