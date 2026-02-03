import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone
from aiogram import Bot
from src.manager.notifier import (
    IncidentNotifier, 
    CATEGORY_EMOJIS, 
    SEVERITY_EMOJIS
)
from src.models.data import Incident, GlobalReport, IncidentCategory, Severity


@pytest.fixture
def mock_bot():
    """Фикстура с мокированным Bot"""
    bot = MagicMock(spec=Bot)
    bot.send_message = AsyncMock()
    return bot


@pytest.fixture
def notifier(mock_bot):
    """Фикстура с IncidentNotifier"""
    return IncidentNotifier(bot=mock_bot)


@pytest.fixture
def sample_incident():
    """Фикстура с примером инцидента"""
    return Incident(
        id=123,
        message_id=456,
        chat_id=-1001234567,
        chat_name="Test Chat",
        sender_id=111,
        sender_username="testuser",
        category=IncidentCategory.LEAK,
        severity=Severity.HIGH,
        description="Обнаружена утечка API ключа в сообщении",
        confidence=0.95,
        detected_at=datetime(2026, 2, 3, 12, 30, 0, tzinfo=timezone.utc)
    )


@pytest.fixture
def sample_report():
    """Фикстура с примером отчёта"""
    return GlobalReport(
        start_time=datetime(2026, 2, 3, 12, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 2, 3, 12, 15, 30, tzinfo=timezone.utc),
        chats_scanned=5,
        total_messages=150,
        total_voices=10,
        total_incidents=8,
        critical_incidents=1,
        high_incidents=3,
        medium_incidents=2,
        low_incidents=2,
        missing_participants=0,
        extra_participants=0,
        duration_seconds=930  # 15 мин 30 сек
    )


def test_category_emojis_mapping():
    """Тест маппинга категорий на эмодзи"""
    assert CATEGORY_EMOJIS["leak"] == "🔐"
    assert CATEGORY_EMOJIS["inappropriate"] == "⚠️"
    assert CATEGORY_EMOJIS["spam"] == "📢"
    assert CATEGORY_EMOJIS["off_topic"] == "💬"
    assert CATEGORY_EMOJIS["security_risk"] == "🛡"


def test_severity_emojis_mapping():
    """Тест маппинга severity на эмодзи"""
    assert SEVERITY_EMOJIS["critical"] == "🔴"
    assert SEVERITY_EMOJIS["high"] == "🟠"
    assert SEVERITY_EMOJIS["medium"] == "🟡"
    assert SEVERITY_EMOJIS["low"] == "🟢"


@pytest.mark.asyncio
async def test_send_incident_alert(notifier, mock_bot, sample_incident):
    """Тест отправки уведомления об инциденте"""
    admin_id = 123456789
    
    await notifier.send_incident_alert(admin_id, sample_incident)
    
    # Проверяем что send_message был вызван
    mock_bot.send_message.assert_called_once()
    
    # Проверяем параметры вызова
    call_args = mock_bot.send_message.call_args
    assert call_args.kwargs["chat_id"] == admin_id
    
    # Проверяем содержимое сообщения
    message_text = call_args.kwargs["text"]
    assert "🚨" in message_text
    assert "ИНЦИДЕНТ #123" in message_text
    assert "Test Chat" in message_text
    assert "@testuser" in message_text
    assert "leak" in message_text
    assert "HIGH" in message_text
    assert "95%" in message_text
    assert CATEGORY_EMOJIS["leak"] in message_text
    assert SEVERITY_EMOJIS["high"] in message_text


@pytest.mark.asyncio
async def test_send_incident_alert_without_id(notifier, mock_bot):
    """Тест отправки уведомления об инциденте без ID"""
    incident = Incident(
        message_id=456,
        chat_id=-1001234567,
        chat_name="Test Chat",
        category=IncidentCategory.SPAM,
        severity=Severity.LOW,
        description="Спам обнаружен",
        confidence=0.75,
        detected_at=datetime.now(timezone.utc)
    )
    
    admin_id = 123456789
    
    await notifier.send_incident_alert(admin_id, incident)
    
    # Проверяем что сообщение отправлено
    mock_bot.send_message.assert_called_once()
    
    # Проверяем что в сообщении есть N/A вместо ID
    message_text = mock_bot.send_message.call_args.kwargs["text"]
    assert "N/A" in message_text


@pytest.mark.asyncio
async def test_send_incident_alert_error_handling(notifier, mock_bot, sample_incident):
    """Тест обработки ошибок при отправке уведомления"""
    admin_id = 123456789
    
    # Мокируем ошибку отправки
    mock_bot.send_message.side_effect = Exception("Network error")
    
    with pytest.raises(Exception, match="Network error"):
        await notifier.send_incident_alert(admin_id, sample_incident)


@pytest.mark.asyncio
async def test_send_summary_report(notifier, mock_bot, sample_report):
    """Тест отправки сводного отчёта"""
    admin_id = 123456789
    
    await notifier.send_summary_report(admin_id, sample_report)
    
    # Проверяем что send_message был вызван
    mock_bot.send_message.assert_called_once()
    
    # Проверяем параметры вызова
    call_args = mock_bot.send_message.call_args
    assert call_args.kwargs["chat_id"] == admin_id
    
    # Проверяем содержимое сообщения
    message_text = call_args.kwargs["text"]
    assert "📊" in message_text
    assert "СВОДНЫЙ ОТЧЁТ" in message_text
    assert "Проверено чатов: 5" in message_text
    assert "Обработано сообщений: 150" in message_text
    assert "Транскрибировано голосовых: 10" in message_text
    assert "Найдено инцидентов: <b>8</b>" in message_text
    assert "Критичные: 1" in message_text
    assert "Высокие: 3" in message_text
    assert "Средние: 2" in message_text
    assert "Низкие: 2" in message_text
    assert "15 мин 30 сек" in message_text


@pytest.mark.asyncio
async def test_send_summary_report_no_incidents(notifier, mock_bot):
    """Тест отправки отчёта без инцидентов"""
    report = GlobalReport(
        start_time=datetime.now(timezone.utc),
        end_time=datetime.now(timezone.utc),
        chats_scanned=3,
        total_messages=50,
        total_voices=0,
        total_incidents=0,
        critical_incidents=0,
        high_incidents=0,
        medium_incidents=0,
        low_incidents=0,
        missing_participants=0,
        extra_participants=0,
        duration_seconds=45
    )
    
    admin_id = 123456789
    
    await notifier.send_summary_report(admin_id, report)
    
    # Проверяем что сообщение отправлено
    mock_bot.send_message.assert_called_once()
    
    # Проверяем что в сообщении нет детализации по severity
    message_text = mock_bot.send_message.call_args.kwargs["text"]
    assert "Найдено инцидентов: <b>0</b>" in message_text
    assert "Критичные:" not in message_text  # Не должно быть детализации


@pytest.mark.asyncio
async def test_send_summary_report_short_duration(notifier, mock_bot):
    """Тест форматирования короткой длительности"""
    report = GlobalReport(
        start_time=datetime.now(timezone.utc),
        end_time=datetime.now(timezone.utc),
        chats_scanned=1,
        total_messages=10,
        total_voices=0,
        total_incidents=0,
        critical_incidents=0,
        high_incidents=0,
        medium_incidents=0,
        low_incidents=0,
        missing_participants=0,
        extra_participants=0,
        duration_seconds=45  # Меньше минуты
    )
    
    admin_id = 123456789
    
    await notifier.send_summary_report(admin_id, report)
    
    # Проверяем форматирование времени (должно быть только в секундах)
    message_text = mock_bot.send_message.call_args.kwargs["text"]
    assert "45 сек" in message_text
    assert "мин" not in message_text


@pytest.mark.asyncio
async def test_send_summary_report_error_handling(notifier, mock_bot, sample_report):
    """Тест обработки ошибок при отправке отчёта"""
    admin_id = 123456789
    
    # Мокируем ошибку отправки
    mock_bot.send_message.side_effect = Exception("API error")
    
    with pytest.raises(Exception, match="API error"):
        await notifier.send_summary_report(admin_id, sample_report)
