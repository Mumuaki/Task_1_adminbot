import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.types import Message, User, Chat
from src.manager.handlers import cmd_start, cmd_status, cmd_help


@pytest.fixture
def mock_message():
    """Фикстура с мокированным сообщением"""
    message = MagicMock(spec=Message)
    message.from_user = MagicMock(spec=User)
    message.from_user.id = 123456789
    message.answer = AsyncMock()
    return message


@pytest.mark.asyncio
async def test_cmd_start(mock_message):
    """Тест команды /start"""
    await cmd_start(mock_message)
    
    # Проверяем что ответ был отправлен
    mock_message.answer.assert_called_once()
    
    # Проверяем содержимое ответа
    response_text = mock_message.answer.call_args[0][0]
    assert "🤖" in response_text
    assert "Система мониторинга чатов" in response_text
    assert "/status" in response_text
    assert "/help" in response_text


@pytest.mark.asyncio
async def test_cmd_status(mock_message):
    """Тест команды /status"""
    # Мокируем settings
    with patch('src.manager.handlers.settings') as mock_settings:
        # Устанавливаем admin_id равным ID пользователя в тесте
        mock_settings.aiogram.admin_id = 123456789
        mock_settings.app.monitored_chats = [1, 2, 3]  # Пример чатов
        mock_settings.app.scan_interval_hours = 6
        
        await cmd_status(mock_message)
    
    # Проверяем что ответ был отправлен
    mock_message.answer.assert_called_once()
    
    # Проверяем содержимое ответа
    response_text = mock_message.answer.call_args[0][0]
    assert "📊" in response_text
    assert "Статус системы" in response_text
    assert "Бот: Активен" in response_text
    assert "Чатов на мониторинге" in response_text
    assert "Интервал сканирования" in response_text


@pytest.mark.asyncio
async def test_cmd_help(mock_message):
    """Тест команды /help"""
    await cmd_help(mock_message)
    
    # Проверяем что ответ был отправлен
    mock_message.answer.assert_called_once()
    
    # Проверяем содержимое ответа
    response_text = mock_message.answer.call_args[0][0]
    assert "📖" in response_text
    assert "Справка по командам" in response_text
    assert "/start" in response_text
    assert "/stats" in response_text
    assert "/help" in response_text
    assert "Система автоматически проверяет чаты" in response_text
