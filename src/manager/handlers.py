from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from src.utils.logger import logger
from config.settings import settings
import asyncio


router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message):
    """
    Команда /start - приветствие и справка.
    """
    logger.info(f"User {message.from_user.id} sent /start")
    
    await message.answer(
        "🤖 <b>Система мониторинга чатов v1.0</b>\n\n"
        "Доступные команды:\n"
        "/status - Текущее состояние системы\n"
        "/scan - Запустить сканирование сейчас\n"
        "/stats - Статистика инцидентов\n"
        "/help - Справка"
    )


@router.message(Command("status"))
async def cmd_status(message: Message):
    """
    Команда /status - статус системы.
    """
    if message.from_user.id != settings.aiogram.admin_id:
        await message.answer("⛔ У вас нет прав для выполнения этой команды.")
        return

    logger.info(f"User {message.from_user.id} sent /status")
    
    # В реальности эти данные можно брать динамически
    chats_count = len(settings.app.monitored_chats) or "динамически из Sheets"
    scan_interval = settings.app.scan_interval_hours
    
    await message.answer(
        "📊 <b>Статус системы:</b>\n\n"
        f"✅ Бот: Активен\n"
        f"📁 Чатов на мониторинге: {chats_count}\n"
        f"🕐 Интервал сканирования: каждые {scan_interval} ч"
    )


@router.message(Command("scan"))
async def cmd_scan(message: Message, scan_job):
    """
    Команда /scan - принудительный запуск сканирования.
    """
    if message.from_user.id != settings.aiogram.admin_id:
        await message.answer("⛔ У вас нет прав для выполнения этой команды.")
        return
        
    logger.info(f"Admin {message.from_user.id} triggered manual scan")
    await message.answer("🔄 Запущено принудительное сканирование чатов...")
    
    # Запускаем сканирование в фоновой задаче
    asyncio.create_task(scan_job.run())


@router.message(Command("stats"))
async def cmd_stats(message: Message, db_manager):
    """
    Команда /stats - общая статистика.
    """
    if message.from_user.id != settings.aiogram.admin_id:
        await message.answer("⛔ У вас нет прав для выполнения этой команды.")
        return

    logger.info(f"User {message.from_user.id} requested stats")
    
    try:
        async with db_manager.get_connection() as conn:
            # Всего инцидентов
            async with conn.execute("SELECT COUNT(*) FROM incidents") as cursor:
                total_incidents = (await cursor.fetchone())[0]
            
            # Инциденты за 24 часа
            async with conn.execute(
                "SELECT COUNT(*) FROM incidents WHERE detected_at > datetime('now', '-1 day')"
            ) as cursor:
                incidents_24h = (await cursor.fetchone())[0]
            
            # Сканирований сегодня
            async with conn.execute(
                "SELECT COUNT(*) FROM scan_logs WHERE start_time > datetime('now', 'start of day')"
            ) as cursor:
                scans_today = (await cursor.fetchone())[0]

        await message.answer(
            "📊 <b>Статистика мониторинга:</b>\n\n"
            f"🚨 Всего инцидентов: <b>{total_incidents}</b>\n"
            f"📅 За последние 24 часа: <b>{incidents_24h}</b>\n"
            f"🔄 Сканирований сегодня: <b>{scans_today}</b>"
        )
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        await message.answer("❌ Ошибка при получении статистики.")


@router.callback_query(F.data.startswith("incident_"))
async def handle_incident_action(callback: CallbackQuery, db_manager, notifier):
    """
    Обработка нажатий на кнопки в алертах.
    """
    parts = callback.data.split("_")
    if len(parts) < 3:
        return
        
    action = parts[1]
    incident_id = int(parts[2])
    
    if action == "details":
        await callback.answer("Детальная информация доступна в Google Sheets", show_alert=True)
        return

    # Получаем данные инцидента
    incident_data = await db_manager.get_incident(incident_id)
    if not incident_data:
        await callback.answer("❌ Инцидент не найден в базе")
        return

    from src.models.data import Incident, IncidentCategory, Severity
    from datetime import datetime
    
    # Реконструкция объекта Incident для нотификатора
    incident = Incident(
        id=incident_data['id'],
        chat_id=incident_data['chat_id'],
        chat_name=incident_data['chat_name'],
        message_id=incident_data['message_id'],
        sender_id=incident_data['sender_id'],
        sender_username=incident_data['sender_username'],
        category=IncidentCategory(incident_data['category']),
        severity=Severity(incident_data['severity']),
        description=incident_data['description'],
        confidence=incident_data['confidence'],
        detected_at=datetime.fromisoformat(incident_data['detected_at']) if isinstance(incident_data['detected_at'], str) else incident_data['detected_at']
    )
    
    new_status = ""
    if action == "false":
        new_status = "false_positive"
    elif action == "confirm":
        new_status = "confirmed"
    
    if new_status:
        await db_manager.update_incident_status(incident_id, new_status, callback.from_user.id)
        
        # Обновляем сообщение через notifier
        try:
            from src.manager.notifier import IncidentNotifier
            await notifier.edit_incident_card(
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
                incident=incident,
                new_status=new_status
            )
            await callback.answer("Статус обновлен")
        except Exception as e:
            logger.error(f"Failed to edit message after callback: {e}")
            await callback.answer("Ошибка при обновлении интерфейса")



@router.callback_query(F.data == "cmd_scan_now")
async def handle_scan_now(callback: CallbackQuery, scan_job):
    """
    Обработка кнопки "Повторить сканирование" из отчета.
    """
    if callback.from_user.id != settings.aiogram.admin_id:
        await callback.answer("⛔ У вас нет прав.", show_alert=True)
        return
        
    await callback.answer("🔄 Сканирование запущено")
    await callback.message.answer("🔄 Запущено принудительное сканирование чатов...")
    asyncio.create_task(scan_job.run())



@router.message(Command("help"))
async def cmd_help(message: Message):
    """
    Команда /help - справка.
    """
    await message.answer(
        "📖 <b>Справка по командам:</b>\n\n"
        "/start - Приветствие\n"
        "/status - Состояние системы\n"
        "/scan - Запустить сканирование\n"
        "/stats - Статистика\n"
        "/help - Эта справка\n\n"
        "Система автоматически проверяет чаты каждые несколько часов."
    )

