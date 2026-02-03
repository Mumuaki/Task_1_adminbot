from aiogram import Bot
from src.models.data import Incident, GlobalReport
from src.utils.logger import logger
from datetime import datetime


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
        
        try:
            await self.bot.send_message(
                chat_id=admin_id,
                text=message_text
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
        
        # Добавление информации о длительности
        if duration_min > 0:
            message_text += f"\n⏱ Длительность: {duration_min} мин {duration_sec} сек"
        else:
            message_text += f"\n⏱ Длительность: {duration_sec} сек"
        
        try:
            await self.bot.send_message(
                chat_id=admin_id,
                text=message_text
            )
            logger.info(f"Summary report sent to admin {admin_id}")
        except Exception as e:
            logger.error(f"Failed to send summary report to {admin_id}: {e}")
            raise
