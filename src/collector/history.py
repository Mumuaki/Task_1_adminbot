from telethon import TelegramClient
from datetime import datetime, timedelta, timezone
from typing import List
import asyncio
from pathlib import Path
from src.utils.logger import logger
from src.models.data import MessageData

class MessageHistoryCollector:
    """
    Сборщик истории сообщений из чатов.
    """
    def __init__(self, client: TelegramClient):
        self.client = client

    async def collect_messages(
        self,
        chat_id: int,
        hours_back: int = 6
    ) -> List[MessageData]:
        """
        Сбор сообщений за последние N часов.
        Итерируется от текущего момента в прошлое, пока не достигнет границы времени.
        """
        # Вычисляем пороговую дату (UTC)
        offset_date = datetime.now(timezone.utc) - timedelta(hours=hours_back)
        
        logger.info(f"Collecting messages for chat {chat_id} since {offset_date.isoformat()}")
        
        collected_messages = []
        
        try:
            # Итерируемся по сообщениям от новых к старым
            async for message in self.client.iter_messages(chat_id, limit=None):
                
                # Проверка даты (message.date - aware datetime в UTC)
                if message.date < offset_date:
                    break
                
                # Пропускаем только если нет ни текста, ни медиа (служебные могли попасть)
                # Но лучше сохранить всё, что похоже на контент
                if not message.message and not message.media:
                    continue

                # Попытка получить username отправителя
                sender_username = None
                # message.sender - это User или Channel, подгружается автоматически если в кэше
                # Если sender_id есть, но объекта нет, username будет None
                if message.sender and hasattr(message.sender, 'username'):
                    sender_username = message.sender.username
                
                # Проверка на наличие голосового сообщения
                has_voice = bool(message.voice) if hasattr(message, 'voice') else False

                msg_data = MessageData(
                    chat_id=chat_id,
                    message_id=message.id,
                    sender_id=message.sender_id,
                    sender_username=sender_username,
                    text=message.message or "",  # Может быть None, если только медиа
                    has_voice=has_voice,
                    timestamp=message.date
                )
                
                collected_messages.append(msg_data)
                
        except Exception as e:
            logger.error(f"Error collecting messages from {chat_id}: {e}")
            raise e

        logger.info(f"Collected {len(collected_messages)} messages from {chat_id}")
        return collected_messages

    async def download_voice(
        self,
        message,  # Telethon Message object
        timeout: int = 30,
        max_size_mb: int = 50
    ) -> Path | None:
        """
        Скачивание голосового с защитой от зависания и проверкой размера.
        """
        # 1. Проверка наличия голосового
        if not (message.voice or message.audio):
            return None
            
        # 2. Проверка размера (если доступен)
        # message.file.size обычно в байтах
        if message.file and message.file.size:
             if message.file.size > max_size_mb * 1024 * 1024:
                 logger.warning(f"Voice message too large: {message.file.size} bytes")
                 return None

        # 3. Формирование пути
        # Сохраняем во временную директорию data/temp
        temp_dir = Path("data/temp")
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Имя файла: {chat_id}_{message_id}.ogg
        # message.chat_id может быть недоступен напрямую если это User, но обычно message.chat_id есть
        chat_id = message.chat_id or message.peer_id.user_id if hasattr(message.peer_id, 'user_id') else 0
        file_path = temp_dir / f"{chat_id}_{message.id}.ogg"
        
        try:
            # 4. Скачивание с таймаутом
            # download_media возвращает путь к файлу или None
            logger.debug(f"Downloading voice to {file_path}")
            
            # Используем wait_for для таймаута
            download_task = message.download_media(file=file_path)
            saved_path = await asyncio.wait_for(download_task, timeout=timeout)
            
            if saved_path:
                return Path(saved_path)
            return None
            
        except asyncio.TimeoutError:
            logger.warning(f"Timeout downloading voice message {message.id}")
            return None
        except Exception as e:
            logger.error(f"Error downloading voice {message.id}: {e}")
            return None
