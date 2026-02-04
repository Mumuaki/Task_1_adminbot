import aiosqlite
from pathlib import Path
from typing import List, Optional
from src.utils.logger import logger
from datetime import datetime
from contextlib import asynccontextmanager

class DatabaseManager:
    """
    Менеджер SQLite для локального кэширования и хранения истории.
    Использует aiosqlite для асинхронного доступа.
    """
    async def update_incident_status(
        self,
        incident_id: int,
        new_status: str,
        resolved_by: int = None
    ) -> None:
        """
        Обновление статуса инцидента.
        """
        resolved_at = datetime.now() if new_status in ['confirmed', 'false_positive'] else None
        
        async with self.get_connection() as db:
            await db.execute("""
                UPDATE incidents SET 
                    status = ?,
                    resolved_at = ?,
                    resolved_by = ?
                WHERE id = ?
            """, (new_status, resolved_at, resolved_by, incident_id))
            await db.commit()
            logger.info(f"Incident {incident_id} status updated to {new_status}")
    
    async def get_incident(self, incident_id: int) -> dict:
        """
        Получение данных инцидента по его ID.
        """
        async with self.get_connection() as conn:
            async with conn.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    
    def __init__(self, db_path: Path | str = None):
        if db_path is None:
            self.db_path = Path("data/local_db.sqlite")
        elif str(db_path) == ":memory:":
            self.db_path = db_path
        else:
            self.db_path = Path(db_path)


    @asynccontextmanager
    async def get_connection(self):
        """Контекстный менеджер для подключения к БД с предустановленными PRAGMA"""
        conn = await aiosqlite.connect(self.db_path)
        try:
            # Включаем FK support и WAL mode для производительности и надежности
            await conn.execute("PRAGMA foreign_keys = ON;")
            await conn.execute("PRAGMA journal_mode = WAL;")
            await conn.execute("PRAGMA synchronous = NORMAL;")
            # Возвращаем rows как dict-like (sqlite3.Row)
            conn.row_factory = aiosqlite.Row
            yield conn
        finally:
            await conn.close()


    async def init_db(self):
        """Создание структуры БД (таблицы и индексы)"""
        logger.info(f"Initializing database at {self.db_path}")
        
        # Убедимся, что папка существует (если это не БД в памяти)
        if str(self.db_path) != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        
        async with self.get_connection() as db:
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
                    is_analyzed BOOLEAN DEFAULT 0,
                    timestamp DATETIME NOT NULL,
                    collected_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(chat_id, message_id)
                );
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_message_timestamp ON messages(chat_id, timestamp);")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_message_collected ON messages(collected_at);")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_message_analyzed ON messages(is_analyzed);")

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
            
            await db.execute("CREATE INDEX IF NOT EXISTS idx_incident_status ON incidents(status, severity);")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_incident_chat ON incidents(chat_id, detected_at);")

            # 3. Таблица участников (снапшоты и отчеты)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS participants (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id BIGINT NOT NULL,
                    user_id BIGINT NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    is_bot BOOLEAN DEFAULT 0,
                    status TEXT DEFAULT 'ok', -- 'extra', 'missing', 'ok'
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

            # 5. Таблица проанализированных сообщений (processed_ids)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS processed_ids (
                    chat_id BIGINT NOT NULL,
                    message_id BIGINT NOT NULL,
                    processed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (chat_id, message_id)
                );
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_processed_at ON processed_ids(processed_at);")
            
            await db.commit()
            logger.info("Database initialized successfully")

# Singleton не делаем, так как может потребоваться несколько коннектов или тестовая БД

    async def save_messages(self, messages: list) -> int:
        """
        Сохранение списка сообщений в БД.
        Игнорирует дубликаты (INSERT OR IGNORE).
        Возвращает количество новых сохраненных сообщений.
        """
        if not messages:
            return 0
            
        count = 0
        async with self.get_connection() as db:
            for msg in messages:
                try:
                    await db.execute("""
                        INSERT OR IGNORE INTO messages (
                            chat_id, message_id, sender_id, sender_username, 
                            text, has_voice, voice_transcription, timestamp
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        msg.chat_id, msg.message_id, msg.sender_id, msg.sender_username,
                        msg.text, msg.has_voice, msg.voice_transcription, msg.timestamp
                    ))
                except Exception as e:
                    logger.error(f"Failed to save message {msg.message_id}: {e}")
            
            await db.commit()
            count = len(messages) 
            
        return count

    async def save_incidents(self, incidents: list):
        """Сохранение новых инцидентов и обновление их ID."""
        if not incidents:
            return

        async with self.get_connection() as db:
            for inc in incidents:
                cursor = await db.execute("""
                    INSERT INTO incidents (
                        message_id, chat_id, chat_name, sender_id, sender_username,
                        category, severity, description, confidence, status, detected_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    inc.message_id, inc.chat_id, inc.chat_name, inc.sender_id, inc.sender_username,
                    inc.category.value, inc.severity.value, inc.description, inc.confidence,
                    "new", inc.detected_at
                ))
                # Присваиваем сгенерированный ID объекту
                inc.id = cursor.lastrowid
            await db.commit()


    async def create_scan_log(self, start_time) -> int:
        """Создание записи о начале сканирования. Возвращает ID лога."""
        async with self.get_connection() as db:
            cursor = await db.execute("""
                INSERT INTO scan_logs (start_time, status) VALUES (?, 'running')
            """, (start_time,))
            await db.commit()
            return cursor.lastrowid

    async def update_scan_log(self, log_id: int, end_time, stats: dict, status: str = "completed", error: str = None):
        """Обновление записи лога после завершения"""
        duration = (end_time - stats.get("start_time")).total_seconds() if stats.get("start_time") else 0
        
        async with self.get_connection() as db:
            await db.execute("""
                UPDATE scan_logs SET 
                    end_time = ?,
                    chats_scanned = ?,
                    messages_processed = ?,
                    voices_transcribed = ?,
                    incidents_found = ?,
                    status = ?,
                    error_message = ?,
                    duration_seconds = ?
                WHERE id = ?
            """, (
                end_time,
                stats.get("chats_scanned", 0),
                stats.get("messages_processed", 0),
                stats.get("voices_transcribed", 0),
                stats.get("incidents_found", 0),
                status,
                error,
                duration,
                log_id
            ))
            await db.commit()

    async def insert_participant_report(self, report) -> None:
        """Сохранение отчёта о сверке участников."""
        async with self.get_connection() as db:
            # Сохраняем "лишних" участников (extra)
            for p in report.extra:
                await db.execute("""
                    INSERT OR IGNORE INTO participants (
                        chat_id, user_id, username, first_name, last_name, is_bot, status, snapshot_date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    report.chat_id, p.user_id, p.username, p.first_name, p.last_name, 
                    p.is_bot, 'extra', report.timestamp
                ))
            
            # Сохраняем "отсутствующих" (missing)
            for p in report.missing:
                await db.execute("""
                    INSERT OR IGNORE INTO participants (
                        chat_id, user_id, username, first_name, last_name, is_bot, status, snapshot_date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    report.chat_id, p.user_id, p.username, p.first_name, p.last_name, 
                    p.is_bot, 'missing', report.timestamp
                ))
            
            await db.commit()
            logger.info(f"Saved participant report for chat {report.chat_id} to database")


    async def filter_new_messages(self, chat_id: int, message_ids: List[int]) -> List[int]:
        """
        Принимает список ID сообщений и возвращает только те, которых нет в processed_ids.
        """
        if not message_ids:
            return []
            
        async with self.get_connection() as db:
            # Для больших батчей используем временную таблицу или IN (но лимит IN обычно 999)
            # Для MVP 50-100 сообщений IN вполне подходит
            placeholders = ','.join(['?'] * len(message_ids))
            query = f"SELECT message_id FROM processed_ids WHERE chat_id = ? AND message_id IN ({placeholders})"
            
            async with db.execute(query, [chat_id] + message_ids) as cursor:
                rows = await cursor.fetchall()
                processed = {row['message_id'] for row in rows}
                
        return [mid for mid in message_ids if mid not in processed]

    async def mark_as_processed(self, chat_id: int, message_ids: List[int]) -> None:
        """
        Помечает сообщения как проанализированные в processed_ids и таблице messages.
        """
        if not message_ids:
            return
            
        async with self.get_connection() as db:
            # 1. Запись в processed_ids
            for mid in message_ids:
                await db.execute(
                    "INSERT OR IGNORE INTO processed_ids (chat_id, message_id) VALUES (?, ?)",
                    (chat_id, mid)
                )
            
            # 2. Обновление флага в messages
            placeholders = ','.join(['?'] * len(message_ids))
            await db.execute(
                f"UPDATE messages SET is_analyzed = 1 WHERE chat_id = ? AND message_id IN ({placeholders})",
                [chat_id] + message_ids
            )
            
            await db.commit()
            logger.debug(f"Marked {len(message_ids)} messages as processed in chat {chat_id}")

    async def cleanup_old_processed_ids(self, days: int = 7) -> None:
        """
        Удаляет старые записи из processed_ids для экономии места.
        """
        async with self.get_connection() as db:
            await db.execute(
                "DELETE FROM processed_ids WHERE processed_at < datetime('now', ?)",
                (f'-{days} days',)
            )
            await db.commit()
            logger.info(f"Cleaned up processed_ids older than {days} days")


