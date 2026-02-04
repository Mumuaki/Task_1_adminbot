from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from src.models.data import Incident, GlobalReport
from src.utils.logger import logger
from datetime import datetime
from config.settings import settings


# Маппинг эмодзи для категорий инцидентов
CATEGORY_EMOJIS = {
    "leak": "🔐",
    "inappropriate": "⚠️",
    "spam": "📢",
    "off_topic": "💬",
    "security_risk": "🛡"
}

# Маппинг эмодзи для уровней критичности
SEVERITY_EMOJIS = {
    "critical": "🔴",
    "high": "🟠",
    "medium": "🟡",
    "low": "🟢"
}


class IncidentNotifier:
    """
    Отправка уведомлений администратору через Telegram Bot.
    
    Атрибуты:
        bot (Bot): Экземпляр aiogram Bot для отправки сообщений
    """
    
    def __init__(self, bot: Bot):
        """
        Инициализация notifier.
        
        Параметры:
            bot: Экземпляр aiogram Bot
        """
        self.bot = bot
    
    async def send_incident_alert(
        self,
        admin_id: int,
        incident: Incident
    ):
        """
        Отправка уведомления об одном инциденте.
        
        Формирует карточку инцидента с эмодзи и отправляет администратору.
        
        Параметры:
            admin_id: ID администратора (Telegram user ID)
            incident: Объект инцидента с деталями
            
        Исключения:
            Exception: При ошибке отправки сообщения
        """
        # Получение эмодзи для категории и критичности
        category_emoji = CATEGORY_EMOJIS.get(incident.category.value, "❓")
        severity_emoji = SEVERITY_EMOJIS.get(incident.severity.value, "⚪")
        
        # Форматирование времени
        timestamp_str = incident.detected_at.strftime("%d.%m.%Y %H:%M")
        
        # Формирование сообщения
        message_text = (
            f"🚨 <b>ИНЦИДЕНТ #{incident.id or 'N/A'}</b>\n\n"
            f"📍 Чат: <b>{incident.chat_name}</b>\n"
            f"👤 Пользователь: @{incident.sender_username or 'Unknown'}\n"
            f"🕐 Время: {timestamp_str}\n\n"
            f"📂 Категория: {category_emoji} {incident.category.value}\n"
            f"⚠️ Критичность: {severity_emoji} {incident.severity.value.upper()}\n"
            f"🎯 Уверенность: {int(incident.confidence * 100)}%\n\n"
            f"📝 <b>Анализ:</b>\n{incident.description}"
        )
        
        # Создание клавиатуры с кнопками
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❌ Ложное срабатывание",
                    callback_data=f"incident_false_{incident.id}"
                ),
                InlineKeyboardButton(
                    text="✅ Подтвердить",
                    callback_data=f"incident_confirm_{incident.id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📋 Подробнее",
                    callback_data=f"incident_details_{incident.id}"
                )
            ]
        ])
        
        try:
            await self.bot.send_message(
                chat_id=admin_id,
                text=message_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            logger.info(f"Incident alert sent to admin {admin_id} for incident {incident.id}")
        except Exception as e:
            logger.error(f"Failed to send incident alert to {admin_id}: {e}")
            raise
    
    async def send_summary_report(
        self,
        admin_id: int,
        report: GlobalReport
    ):
        """
        Отправка сводного отчёта после сканирования.
        
        Формирует сводку с общей статистикой и детализацией по инцидентам.
        
        Параметры:
            admin_id: ID администратора
            report: Глобальный отчёт со статистикой
            
        Исключения:
            Exception: При ошибке отправки сообщения
        """
        # Форматирование времени
        start_str = report.start_time.strftime("%d.%m %H:%M")
        end_str = report.end_time.strftime("%d.%m %H:%M")
        
        # Длительность в минутах
        duration_min = int(report.duration_seconds / 60)
        duration_sec = int(report.duration_seconds % 60)
        
        # Базовая часть сообщения
        message_text = (
            f"📊 <b>СВОДНЫЙ ОТЧЁТ</b>\n"
            f"Период: {start_str} - {end_str}\n\n"
            f"✅ Проверено чатов: {report.chats_scanned}\n"
            f"📨 Обработано сообщений: {report.total_messages}\n"
            f"🎙 Транскрибировано голосовых: {report.total_voices}\n\n"
            f"🚨 Найдено инцидентов: <b>{report.total_incidents}</b>\n"
        )
        
        # Добавление детализации по инцидентам если они есть
        if report.total_incidents > 0:
            message_text += (
                f"   {SEVERITY_EMOJIS['critical']} Критичные: {report.critical_incidents}\n"
                f"   {SEVERITY_EMOJIS['high']} Высокие: {report.high_incidents}\n"
                f"   {SEVERITY_EMOJIS['medium']} Средние: {report.medium_incidents}\n"
                f"   {SEVERITY_EMOJIS['low']} Низкие: {report.low_incidents}\n"
            )
        
        # Добавление информации об участниках
        if report.missing_participants > 0 or report.extra_participants > 0:
            message_text += f"\n👥 <b>Контроль доступа:</b>\n"
            
            if report.missing_participants > 0 and hasattr(report, 'missing_ids') and report.missing_ids:
                message_text += f"   ❌ Отсутствуют ({report.missing_participants}): {', '.join(map(str, report.missing_ids))}\n"
            elif report.missing_participants > 0:
                message_text += f"   ❌ Отсутствуют: {report.missing_participants}\n"

            if report.extra_participants > 0 and hasattr(report, 'extra_ids') and report.extra_ids:
                message_text += f"   🚫 Лишние ({report.extra_participants}): {', '.join(map(str, report.extra_ids))}\n"
            elif report.extra_participants > 0:
                message_text += f"   🚫 Лишние: {report.extra_participants}\n"
        
        # Добавление информации о длительности
        if duration_min > 0:
            message_text += f"\n⏱ Длительность: {duration_min} мин {duration_sec} сек"
        else:
            message_text += f"\n⏱ Длительность: {duration_sec} сек"
            
        # Кнопки для сводного отчета
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📊 Открыть таблицу",
                    url=f"https://docs.google.com/spreadsheets/d/{settings.google_sheets.spreadsheet_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔄 Повторить сканирование",
                    callback_data="cmd_scan_now"
                )
            ]
        ])
        
        try:
            await self.bot.send_message(
                chat_id=admin_id,
                text=message_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            logger.info(f"Summary report sent to admin {admin_id}")
        except Exception as e:
            logger.error(f"Failed to send summary report to {admin_id}: {e}")
            raise

    async def edit_incident_card(
        self,
        chat_id: int,
        message_id: int,
        incident: Incident,
        new_status: str
    ):
        """
        Редактирование карточки инцидента после принятия решения.
        
        Добавляет текстовую метку о принятом решении и удаляет кнопки.
        
        Параметры:
            chat_id: ID чата (admin_id)
            message_id: ID сообщения для редактирования
            incident: Объект инцидента
            new_status: Новый статус ('confirmed', 'false_positive')
        """
        # Получение эмодзи для категории и критичности
        category_emoji = CATEGORY_EMOJIS.get(incident.category.value, "❓")
        severity_emoji = SEVERITY_EMOJIS.get(incident.severity.value, "⚪")
        
        # Метка статуса
        status_label = "✅ ПОДТВЕРЖДЕНО" if new_status == 'confirmed' else "❌ ЛОЖНОЕ СРАБАТЫВАНИЕ"
        
        # Форматирование времени
        timestamp_str = incident.detected_at.strftime("%d.%m.%Y %H:%M")
        
        # Обновленный текст (с меткой решения)
        message_text = (
            f"<b>{status_label}</b>\n\n"
            f"🚨 <b>ИНЦИДЕНТ #{incident.id or 'N/A'}</b>\n\n"
            f"📍 Чат: <b>{incident.chat_name}</b>\n"
            f"👤 Пользователь: @{incident.sender_username or 'Unknown'}\n"
            f"🕐 Время: {timestamp_str}\n\n"
            f"📂 Категория: {category_emoji} {incident.category.value}\n"
            f"⚠️ Критичность: {severity_emoji} {incident.severity.value.upper()}\n\n"
            f"📝 <b>Анализ:</b>\n{incident.description}"
        )
        
        try:
            await self.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=message_text,
                reply_markup=None, # Удаляем кнопки
                parse_mode="HTML"
            )
            logger.info(f"Incident card {message_id} updated with status {new_status}")
        except Exception as e:
            logger.error(f"Failed to edit incident card {message_id}: {e}")
            raise
