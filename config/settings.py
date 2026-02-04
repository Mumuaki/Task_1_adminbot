from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from dotenv import load_dotenv
import os

# Явная загрузка .env файла из папки config
# Если его нет, будут использоваться переменные окружения системы
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

class TelethonSettings(BaseSettings):
    """Настройки Telethon Userbot"""
    api_id: int
    api_hash: str
    phone: str
    session_path: Path = Path("data/sessions/userbot.session")
    
    model_config = SettingsConfigDict(env_prefix="TG_")

class AiogramSettings(BaseSettings):
    """Настройки aiogram Bot"""
    token: str
    admin_id: int
    
    model_config = SettingsConfigDict(env_prefix="BOT_")

class CometAPISettings(BaseSettings):
    """Настройки CometAPI"""
    api_key: str
    api_url: str = "https://api.comet.com/v1"
    whisper_model: str = "whisper-1"
    llm_model: str = "gpt-4-turbo"
    
    model_config = SettingsConfigDict(env_prefix="COMET_")

class GoogleSheetsSettings(BaseSettings):
    """Настройки Google Sheets"""
    spreadsheet_id: str
    service_account_path: Path = Path("config/service_account.json")
    
    model_config = SettingsConfigDict(env_prefix="GOOGLE_")

class AppSettings(BaseSettings):
    """Основные настройки приложения"""
    scan_interval_hours: int = 6
    max_messages_per_chunk: int = 50
    max_chunk_tokens: int = 4000
    voice_download_timeout: int = 30
    voice_max_size_mb: int = 50
    flood_delay_min: int = 10
    flood_delay_max: int = 30
    monitored_chats: list[int] = []  # List of chat IDs to monitor
    
    model_config = SettingsConfigDict(env_prefix="APP_")

class Settings:
    """Общий класс настроек (Singleton)"""
    telethon: TelethonSettings
    aiogram: AiogramSettings
    comet_api: CometAPISettings
    google_sheets: GoogleSheetsSettings
    app: AppSettings
    
    def __init__(self):
        # Инициализация всех подсекций настроек
        # Pydantic автоматически считает переменные окружения с соответствующими префиксами
        self.telethon = TelethonSettings()
        self.aiogram = AiogramSettings()
        self.comet_api = CometAPISettings()
        self.google_sheets = GoogleSheetsSettings()
        self.app = AppSettings()

# Экземпляр настроек (Singleton)
# Будет создан при первом импорте модуля
try:
    settings = Settings()
except Exception as e:
    # Если .env не заполнен корректно, возникнет ошибка валидации
    print(f"CRITICAL: Failed to load settings. Check config/.env file.\nError: {e}")
    # Не роняем здесь, чтобы тесты могли перехватить, или можно сделать raise
    # В prod лучше упасть сразу
    settings = None
