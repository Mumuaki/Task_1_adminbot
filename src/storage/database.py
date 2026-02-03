import aiosqlite
from pathlib import Path
from src.utils.logger import logger

class DatabaseManager:
    """
    Менеджер SQLite для локального кэширования и хранения истории.
    Использует aiosqlite для асинхронного доступа.
    """
    
    def __init__(self, db_path: Path = None):
        # По умолчанию используем путь из настроек или хардкод (лучше передавать)
        # Если db_path не передан, берем дефолтный
        self.db_path = db_path or Path("data/local_db.sqlite")

    async def get_connection(self) -> aiosqlite.Connection:
        """Создает и возвращает подключение к БД"""
        conn = await aiosqlite.connect(self.db_path)
        # Включаем FK support
        await conn.execute("PRAGMA foreign_keys = ON;")
        # Возвращаем rows как dict-like (sqlite3.Row)
        conn.row_factory = aiosqlite.Row
        return conn

    async def init_db(self):
        """Создание структуры БД (таблицы и индексы)"""
        logger.info(f"Initializing database at {self.db_path}")
        
        # Убедимся, что папка существует
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        async with aiosqlite.connect(self.db_path) as db:
            # 1. Таблица сообщений (дедупликация)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id BIGINT NOT NULL,
                    message_id BIGINT NOT NULL,
                    sender_id BIGINT,
                    sender_username TEXT,
                    text TEXT,
                    has_voice BOOLEAN DEFAULT 0,
                    voice_transcription TEXT,
                    timestamp DATETIME NOT NULL,
                    collected_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(chat_id, message_id)
                );
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_message_timestamp ON messages(chat_id, timestamp);")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_message_collected ON messages(collected_at);")

            # 2. Таблица инцидентов
            await db.execute("""
                CREATE TABLE IF NOT EXISTS incidents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id BIGINT,
                    chat_id BIGINT NOT NULL,
                    chat_name TEXT,
                    sender_id BIGINT,
                    sender_username TEXT,
                    category TEXT NOT NULL, 
                    severity TEXT NOT NULL,
                    description TEXT,
                    confidence REAL,
                    status TEXT DEFAULT 'new',
                    detected_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    resolved_at DATETIME,
                    resolved_by BIGINT,
                    FOREIGN KEY (chat_id, message_id) REFERENCES messages(chat_id, message_id) ON DELETE SET NULL
                );
            """)
            # Note: FK references (chat_id, message_id) which is a UNIQUE key in messages, but not a PK. 
            # SQLite allows this if UNIQUE constraint exists.
            
            await db.execute("CREATE INDEX IF NOT EXISTS idx_incident_status ON incidents(status, severity);")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_incident_chat ON incidents(chat_id, detected_at);")

            # 3. Таблица участников (снапшоты)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS participants (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id BIGINT NOT NULL,
                    user_id BIGINT NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    is_bot BOOLEAN DEFAULT 0,
                    snapshot_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(chat_id, user_id, snapshot_date)
                );
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_participant_chat ON participants(chat_id, snapshot_date);")

            # 4. Таблица логов сканирований
            await db.execute("""
                CREATE TABLE IF NOT EXISTS scan_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    start_time DATETIME NOT NULL,
                    end_time DATETIME,
                    chats_scanned INTEGER DEFAULT 0,
                    messages_processed INTEGER DEFAULT 0,
                    voices_transcribed INTEGER DEFAULT 0,
                    incidents_found INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'running',
                    error_message TEXT,
                    duration_seconds REAL
                );
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_scan_date ON scan_logs(start_time);")
            
            await db.commit()
            logger.info("Database initialized successfully")

# Singleton не делаем, так как может потребоваться несколько коннектов или тестовая БД
