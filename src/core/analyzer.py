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
from src.core.whisper import WhisperClient
from pathlib import Path
import time
from src.storage.database import DatabaseManager


class ContentAnalyzer:
    """
    Оркестратор анализа контента чатов.
    
    Атрибуты:
        llm_client (LLMClient): Клиент для LLM анализа
    """
    
    def __init__(self, llm_client: LLMClient, whisper_client: WhisperClient, db_manager: DatabaseManager = None):
        self.llm_client = llm_client
        self.whisper_client = whisper_client
        self.db_manager = db_manager
    
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
        
        # Фильтрация сообщений: текст или голосовое
        valid_messages = [msg for msg in messages if (msg.text and msg.text.strip()) or msg.has_voice]
        
        # Дедупликация: исключаем то, что уже анализировалось (если есть БД)
        if self.db_manager:
            all_ids = [msg.message_id for msg in valid_messages]
            new_ids = await self.db_manager.filter_new_messages(chat_id, all_ids)
            
            if len(new_ids) < len(valid_messages):
                logger.info(f"Deduplication: {len(valid_messages) - len(new_ids)} messages already analyzed, {len(new_ids)} new")
                valid_messages = [msg for msg in valid_messages if msg.message_id in new_ids]
        
        if not valid_messages:
            logger.info(f"No new valid messages to analyze in chat {chat_id}")
            return ChatAnalysisResult(
                chat_id=chat_id,
                chat_name=chat_name,
                messages_analyzed=0,
                voices_transcribed=0,
                incidents=[],
                processing_time=time.time() - start_time
            )
        
        # Обработка голосовых сообщений (Whisper)
        voices_count = 0
        for msg in valid_messages:
            if msg.has_voice and msg.voice_path:
                try:
                    # Транскрибируем
                    audio_path = Path(msg.voice_path)
                    transcription = await self.whisper_client.transcribe_voice(audio_path)
                    msg.voice_transcription = transcription.text
                    
                    # Добавляем транскрипцию в текст сообщения для LLM анализа
                    voice_text = f"\n[Транскрипция голосового] {transcription.text}"
                    if msg.text:
                        msg.text += voice_text
                    else:
                        msg.text = voice_text
                        
                    voices_count += 1
                    
                    # Удаляем временный файл после успешной транскрипции (Задача 2.15)
                    try:
                        audio_path.unlink(missing_ok=True)
                        logger.debug(f"Temporary voice file {audio_path} deleted")
                    except Exception as de:
                        logger.warning(f"Failed to delete temp file {audio_path}: {de}")
                        
                except Exception as e:
                    logger.error(f"Failed to transcribe voice for message {msg.message_id}: {e}")
                    # Пытаемся удалить файл даже при ошибке
                    try:
                        Path(msg.voice_path).unlink(missing_ok=True)
                    except:
                        pass


        logger.info(f"Analyzing {len(valid_messages)} messages ({voices_count} voices transcribed)")
        
        # Анализ через LLM по частям (чанкование)
        chunks = self._chunk_messages(valid_messages, size=50)
        all_incidents = []
        
        for i, chunk in enumerate(chunks):
            logger.info(f"Analyzing chunk {i+1}/{len(chunks)} in chat {chat_name} ({len(chunk)} messages)")
            try:
                chunk_result = await self.llm_client.analyze_messages(chunk, chat_name)
                all_incidents.extend(chunk_result.incidents)
                
                # Помечаем сообщения как обработанные после успешного анализа чанка
                if self.db_manager:
                    chunk_ids = [msg.message_id for msg in chunk]
                    await self.db_manager.mark_as_processed(chat_id, chunk_ids)
                    
            except Exception as e:
                logger.error(f"Failed to analyze chunk {i+1} in chat {chat_id}: {e}")
                # Продолжаем с остальными чанками
        
        # Дополнение инцидентов информацией об отправителях
        # Создаём словарь message_id -> MessageData для быстрого поиска
        msg_map = {msg.message_id: msg for msg in valid_messages}
        
        enriched_incidents = []
        for incident in all_incidents:
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
        
        # Статистика участников
        missing_participants = sum(
            len(r.participant_report.missing) for r in chat_results if r.participant_report
        )
        extra_participants = sum(
            len(r.participant_report.extra) for r in chat_results if r.participant_report
        )
        
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
        
        # Агрегация ID участников
        all_missing_ids = []
        all_extra_ids = []
        for r in chat_results:
            if r.participant_report:
                all_missing_ids.extend([p.user_id for p in r.participant_report.missing])
                all_extra_ids.extend([p.user_id for p in r.participant_report.extra])

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
            missing_participants=missing_participants,
            extra_participants=extra_participants,
            duration_seconds=duration_seconds,
            missing_ids=all_missing_ids,
            extra_ids=all_extra_ids
        )

        
        logger.info(
            f"Aggregation complete: {len(all_incidents)} total incidents "
            f"({critical_count} critical, {high_count} high, {medium_count} medium, {low_count} low)"
        )
        
        return report

    @staticmethod
    def _chunk_messages(messages: List[MessageData], size: int = 50) -> List[List[MessageData]]:
        """
        Разбивает список сообщений на части (чанки).
        
        Параметры:
            messages: Исходный список сообщений
            size: Максимальный размер чанка
            
        Возвращает:
            List[List[MessageData]]: Список чанков
        """
        return [messages[i:i + size] for i in range(0, len(messages), size)]
