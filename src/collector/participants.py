from telethon import TelegramClient
from typing import List, Set
from src.utils.logger import logger
from src.models.data import ParticipantData, ParticipantReport

class ParticipantCollector:
    """
    Сборщик списка участников чата.
    """
    
    def __init__(self, client: TelegramClient):
        self.client = client

    async def get_full_participants(
        self, 
        chat_id: int
    ) -> List[ParticipantData]:
        """
        Получение всех участников чата включая неактивных.
        
        Использует aggressive=True для получения полного списка в больших чатах.
        """
        logger.info(f"Collecting participants for chat {chat_id}")
        
        participants_data = []
        
        try:
            # aggressive=True пытается получить всех участников, обходя ограничения
            async for user in self.client.iter_participants(chat_id, aggressive=True):
                if not user:
                    continue
                    
                p_data = ParticipantData(
                    user_id=user.id,
                    username=user.username,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    is_bot=user.bot
                )
                participants_data.append(p_data)
                
        except Exception as e:
            logger.error(f"Error collecting participants from {chat_id}: {e}")
            raise e
            
        logger.info(f"Collected {len(participants_data)} participants from {chat_id}")
        return participants_data

    async def compare_with_whitelist(
        self,
        chat_id: int,
        chat_name: str,
        participants: List[ParticipantData],
        whitelist: List[int]
    ) -> ParticipantReport:
        """
        Сверка участников с белым списком.
        """
        # Преобразуем в множества для быстрого поиска
        current_map = {p.user_id: p for p in participants}
        current_ids = set(current_map.keys())
        whitelist_ids = set(whitelist)
        
        # missing: должны быть (whitelist), но их нет (current)
        missing_ids = whitelist_ids - current_ids
        # extra: есть (current), но их не должно быть (whitelist)
        extra_ids = current_ids - whitelist_ids
        
        # Формируем списки ParticipantData
        # Для missing у нас нет данных из чата, поэтому создаем заглушки или ищем если возможно (но здесь просто ID)
        # В отчете missing лучше хранить как ParticipantData, но у нас есть только ID.
        # Модель ParticipantData требует user_id. Остальное Optional.
        
        missing_participants = [
            ParticipantData(user_id=uid) for uid in missing_ids
        ]
        
        extra_participants = [
            current_map[uid] for uid in extra_ids
        ]
        
        report = ParticipantReport(
            chat_id=chat_id,
            chat_name=chat_name,
            missing=missing_participants,
            extra=extra_participants
        )
        
        logger.info(f"Participant check for {chat_id}: {len(missing_ids)} missing, {len(extra_ids)} extra")
        return report
