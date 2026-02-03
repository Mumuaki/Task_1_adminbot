from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from src.utils.logger import logger
from src.manager.handlers import router


class TelegramBot:
    """
    Менеджер Telegram бота для команд управления.
    
    Атрибуты:
        bot (Bot): Экземпляр aiogram Bot
        dp (Dispatcher): Диспетчер для обработки сообщений
        admin_id (int): ID администратора
    """
    
    def __init__(self, token: str, admin_id: int):
        """
        Инициализация бота.
        
        Параметры:
            token: Токен бота от BotFather
            admin_id: ID администратора для проверки прав
        """
        self.admin_id = admin_id
        
        # Создание Bot с HTML parse mode
        self.bot = Bot(
            token=token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        
        # Создание Dispatcher
        self.dp = Dispatcher()
        
        # Регистрация роутеров
        self.dp.include_router(router)
        
        logger.info(f"TelegramBot initialized for admin {admin_id}")
    
    async def start_polling(self):
        """
        Запуск long polling.
        
        Метод блокирующий - запускает бесконечный цикл обработки обновлений.
        """
        logger.info("Starting bot polling...")
        try:
            await self.dp.start_polling(self.bot)
        except Exception as e:
            logger.error(f"Error during polling: {e}")
            raise
    
    async def stop_polling(self):
        """
        Корректная остановка бота.
        
        Закрывает сессию и освобождает ресурсы.
        """
        logger.info("Stopping bot polling...")
        await self.bot.session.close()
