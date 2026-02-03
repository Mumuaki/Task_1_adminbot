from loguru import logger
import sys

def setup_logger():
    """
    Настройка Loguru для логирования в файлы и консоль.
    Создает ротируемые логи в папке logs/
    """
    logger.remove()  # Удаление дефолтного хэндлера
    
    # Консоль (для разработки) - цветной, читаемый формат
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO"
    )
    
    # Файл приложения (для продакшена) - JSON формат для машиночитаемости (опционально) или просто текст
    # В реализации указан serialize=True для JSON, но для удобства чтения сделаем пока текст, 
    # или можно оставить JSON если планируется ELK. Оставлю как в ТЗ (serialize=True).
    logger.add(
        "logs/app_{time:YYYY-MM-DD}.log",
        rotation="00:00",  # Новый файл каждый день
        retention="30 days",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} - {message}",
        serialize=True,  # JSON формат
        encoding="utf-8"
    )
    
    # Файл ошибок - отдельный файл для серьезных проблем
    logger.add(
        "logs/errors_{time:YYYY-MM-DD}.log",
        rotation="10 MB",
        level="ERROR",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} - {message}",
        backtrace=True,
        diagnose=True,
        encoding="utf-8"
    )

# Экспорт настроенного логгера
__all__ = ["logger", "setup_logger"]
