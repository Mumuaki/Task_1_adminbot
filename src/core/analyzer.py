from typing import List
from datetime import datetime
from src.utils.logger import logger
from src.models.data import (
    MessageData, 
    ChatAnalysisResult, 
    GlobalReport, 
    Incident,
    Severity
)
from src.core.llm_client import LLMClient
import time


class ContentAnalyzer:
    """
    Оркестратор анализа контента чатов.
    
    Атрибуты:
        llm_client (LLMClient): Клиент для LLM анализа
    """
    
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client
    
    async def process_chat(
        self,
        chat_id: int,
        chat_name: str,
        messages: List[MessageData]
    ) -> ChatAnalysisResult:
        """
        Полная обработка одного чата.
        
        Параметры:
            chat_id: ID чата
            chat_name: Название чата
            messages: Собранные сообщения из Collector
            
        Возвращает:
            ChatAnalysisResult: Результаты анализа + статистика
        """
        start_time = time.time()
        
        logger.info(f"Processing chat {chat_name} ({chat_id}) with {len(messages)} messages")
        
        # Фильтрация пустых сообщений
        valid_messages = [msg for msg in messages if msg.text and msg.text.strip()]
        
        if not valid_messages:
            logger.warning(f"No valid messages to analyze in chat {chat_id}")
            return ChatAnalysisResult(
                chat_id=chat_id,
                chat_name=chat_name,
                messages_analyzed=0,
                voices_transcribed=0,
                incidents=[],
                processing_time=time.time() - start_time
            )
        
        logger.info(f"Analyzing {len(valid_messages)} valid messages")
        
        # Анализ через LLM
        analysis_result = await self.llm_client.analyze_messages(valid_messages, chat_name)
        
        # Дополнение инцидентов информацией об отправителях
        # Создаём словарь message_id -> MessageData для быстрого поиска
        msg_map = {msg.message_id: msg for msg in valid_messages}
        
        enriched_incidents = []
        for incident in analysis_result.incidents:
            # Находим исходное сообщение
            original_msg = msg_map.get(incident.message_id)
            if original_msg:
                # Обновляем sender_id и sender_username
                incident.sender_id = original_msg.sender_id
                incident.sender_username = original_msg.sender_username
            
            enriched_incidents.append(incident)
        
        # Подсчёт транскрибированных голосовых (для MVP = 0, будет в Этапе 2)
        voices_transcribed = sum(1 for msg in valid_messages if msg.has_voice and msg.voice_transcription)
        
        processing_time = time.time() - start_time
        
        result = ChatAnalysisResult(
            chat_id=chat_id,
            chat_name=chat_name,
            messages_analyzed=len(valid_messages),
            voices_transcribed=voices_transcribed,
            incidents=enriched_incidents,
            processing_time=processing_time
        )
        
        logger.info(
            f"Chat {chat_name} processed in {processing_time:.2f}s: "
            f"{len(enriched_incidents)} incidents found"
        )
        
        return result
    
    async def aggregate_results(
        self,
        chat_results: List[ChatAnalysisResult],
        start_time: datetime,
        end_time: datetime
    ) -> GlobalReport:
        """
        Агрегация результатов по всем чатам.
        
        Параметры:
            chat_results: Список результатов анализа чатов
            start_time: Время начала сканирования
            end_time: Время окончания сканирования
            
        Возвращает:
            GlobalReport: Сводный отчёт
        """
        logger.info(f"Aggregating results from {len(chat_results)} chats")
        
        # Подсчёт общей статистики
        total_messages = sum(r.messages_analyzed for r in chat_results)
        total_voices = sum(r.voices_transcribed for r in chat_results)
        
        # Сбор всех инцидентов
        all_incidents = []
        for result in chat_results:
            all_incidents.extend(result.incidents)
        
        # Группировка по severity
        critical_count = sum(1 for inc in all_incidents if inc.severity == Severity.CRITICAL)
        high_count = sum(1 for inc in all_incidents if inc.severity == Severity.HIGH)
        medium_count = sum(1 for inc in all_incidents if inc.severity == Severity.MEDIUM)
        low_count = sum(1 for inc in all_incidents if inc.severity == Severity.LOW)
        
        # Вычисление длительности
        duration_seconds = (end_time - start_time).total_seconds()
        
        report = GlobalReport(
            start_time=start_time,
            end_time=end_time,
            chats_scanned=len(chat_results),
            total_messages=total_messages,
            total_voices=total_voices,
            total_incidents=len(all_incidents),
            critical_incidents=critical_count,
            high_incidents=high_count,
            medium_incidents=medium_count,
            low_incidents=low_count,
            missing_participants=0,  # Будет заполнено при интеграции с ParticipantCollector
            extra_participants=0,  # Будет заполнено при интеграции с ParticipantCollector
            duration_seconds=duration_seconds
        )
        
        logger.info(
            f"Aggregation complete: {len(all_incidents)} total incidents "
            f"({critical_count} critical, {high_count} high, {medium_count} medium, {low_count} low)"
        )
        
        return report
