import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram import Bot, Dispatcher, Router
from src.manager.bot import TelegramBot


@pytest.fixture
def bot_token():
    """Фикстура с тестовым токеном бота"""
    return "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"


@pytest.fixture
def admin_id():
    """Фикстура с ID администратора"""
    return 123456789


def test_telegram_bot_initialization(bot_token, admin_id):
    """Тест инициализации TelegramBot"""
    # Создаём реальный router для теста
    with patch('src.manager.bot.router', Router()):
        bot = TelegramBot(token=bot_token, admin_id=admin_id)
        
        assert bot.admin_id == admin_id
        assert isinstance(bot.bot, Bot)
        assert isinstance(bot.dp, Dispatcher)


@pytest.mark.asyncio
async def test_start_polling_error_handling(bot_token, admin_id):
    """Тест обработки ошибок при запуске polling"""
    with patch('src.manager.bot.router', Router()):
        bot_instance = TelegramBot(token=bot_token, admin_id=admin_id)
        
        # Мокируем bot.delete_webhook чтобы не было реальных запросов
        bot_instance.bot.delete_webhook = AsyncMock()
        
        # Мокируем dp.start_polling чтобы вызвать исключение
        bot_instance.dp.start_polling = AsyncMock(side_effect=Exception("Test error"))
        
        with pytest.raises(Exception, match="Test error"):
            await bot_instance.start_polling()


@pytest.mark.asyncio
async def test_stop_polling(bot_token, admin_id):
    """Тест корректной остановки бота"""
    with patch('src.manager.bot.router', Router()):
        bot_instance = TelegramBot(token=bot_token, admin_id=admin_id)
        
        # Мокируем session.close()
        bot_instance.bot.session = MagicMock()
        bot_instance.bot.session.close = AsyncMock()
        
        await bot_instance.stop_polling()
        
        # Проверяем что close был вызван
        bot_instance.bot.session.close.assert_called_once()
