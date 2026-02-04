from datetime import datetime, timezone
from typing import List
from src.utils.logger import logger
from src.collector.history import MessageHistoryCollector
from src.collector.participants import ParticipantCollector
from src.core.analyzer import ContentAnalyzer
from src.manager.notifier import IncidentNotifier
from src.storage.database import DatabaseManager
from src.storage.sheets import GoogleSheetsManager
from src.models.data import ChatAnalysisResult
from config.settings import settings

class ScanJob:
    """
    Оркестратор процесса сканирования чатов.
    Запускается по расписанию через Scheduler.
    """
    
    def __init__(
        self,
        collector: MessageHistoryCollector,
        participant_collector: ParticipantCollector,
        analyzer: ContentAnalyzer,
        notifier: IncidentNotifier,
        db_manager: DatabaseManager,
        sheets_manager: GoogleSheetsManager,
        chat_ids: List[int]
    ):
        """
        Инициализация задачи сканирования.
        
        Параметры:
            collector: Сборщик сообщений
            participant_collector: Сборщик участников для сверки с whitelist
            analyzer: Анализатор контента
            notifier: Отправщик уведомлений
            db_manager: Менеджер БД для сохранения результатов
            sheets_manager: Менеджер Google Sheets для чтения whitelist и записи
            chat_ids: Список ID чатов для мониторинга
        """
        self.collector = collector
        self.participant_collector = participant_collector
        self.analyzer = analyzer
        self.notifier = notifier
        self.db_manager = db_manager
        self.sheets_manager = sheets_manager
        self.chat_ids = chat_ids

    async def run(self):
        """
        Основной метод запуска сканирования.
        Обрабатывает все чаты последовательно (или параллельно - для MVP последовательно безопаснее).
        """
        scan_start_time = datetime.now(timezone.utc)
        logger.info(f"Starting scheduled scan for {len(self.chat_ids)} chats")
        
        # Создаем лог сканирования в БД
        try:
            log_id = await self.db_manager.create_scan_log(scan_start_time)
        except Exception as e:
            logger.error(f"Failed to create scan log: {e}")
            log_id = None

        chat_results: List[ChatAnalysisResult] = []
        
        for chat_id in self.chat_ids:
            try:
                # Получаем название чата (пока заглушка или через collector)
                # В Telethon methods обычно можно получить entity, но для MVP можно просто ID или попытку
                try:
                    entity = await self.collector.client.get_entity(chat_id)
                    chat_name = entity.title if hasattr(entity, 'title') else f"Chat {chat_id}"
                except Exception:
                    chat_name = f"Chat {chat_id}"

                result = await self.run_single_chat(chat_id, chat_name)
                if result:
                    chat_results.append(result)
                
                # Добавляем случайную задержку (jitter) между чатами для защиты от флуда
                if chat_id != self.chat_ids[-1]: # Не ждем после последнего чата
                    import random
                    jitter = random.uniform(10, 30)
                    logger.info(f"Sleeping for {jitter:.1f}s before next chat...")
                    await asyncio.sleep(jitter)
                    
            except Exception as e:

                logger.error(f"Error processing chat {chat_id}: {e}")
                # Продолжаем с следующим чатом
                continue

        scan_end_time = datetime.now(timezone.utc)
        
        # Агрегация результатов
        try:
            global_report = await self.analyzer.aggregate_results(
                chat_results, 
                scan_start_time, 
                scan_end_time
            )
            
            # Отправка сводного отчета
            # TODO: Получить admin_id из конфига. Пока возьмем из notifier.bot (недоступно напрямую)
            # Придется передать admin_id в ScanJob или брать из settings
            admin_id = settings.aiogram.admin_id
            await self.notifier.send_summary_report(admin_id, global_report)
            
            # Сохраняем лог сканирования в Google Sheets
            try:
                await self.sheets_manager.append_scan_log(global_report)
                logger.info("Scan log saved to Google Sheets")
            except Exception as e:
                logger.error(f"Failed to save scan log to Sheets: {e}")

            
        except Exception as e:
            logger.error(f"Error aggregating/sending report: {e}")
            global_report = None

        # Обновление лога
        if log_id:
            try:
                stats = {
                    "start_time": scan_start_time,
                    "chats_scanned": len(chat_results),
                    "messages_processed": sum(r.messages_analyzed for r in chat_results),
                    "voices_transcribed": sum(r.voices_transcribed for r in chat_results),
                    "incidents_found": sum(len(r.incidents) for r in chat_results)
                }
                await self.db_manager.update_scan_log(log_id, scan_end_time, stats, status="completed")
            except Exception as e:
                logger.error(f"Failed to update scan log: {e}")

        logger.info("Scan cycle completed")

    async def run_single_chat(self, chat_id: int, chat_name: str) -> ChatAnalysisResult | None:
        """
        Полный цикл обработки одного чата.
        Collector -> Analyzer -> Notifier -> Store
        """
        logger.info(f"Processing single chat: {chat_name} ({chat_id})")
        
        # 1. Collector
        try:
            messages = await self.collector.collect_messages(
                chat_id, 
                hours_back=settings.app.scan_interval_hours
            )
        except Exception as e:
            logger.error(f"Collector failed for {chat_id}: {e}")
            return None
            
        # Сохраняем сырые сообщения в БД (кэш)
        await self.db_manager.save_messages(messages)
        
        # 2. Analyzer
        # Анализатор фильтрует пустые сообщения внутри, так что передаем все
        result = await self.analyzer.process_chat(chat_id, chat_name, messages)
        
        # 3. Store Results (Incidents)
        if result.incidents:
            await self.db_manager.save_incidents(result.incidents)
            
            # Сохраняем инциденты в Google Sheets
            try:
                await self.sheets_manager.append_incidents(result.incidents)
                logger.info(f"Incidents saved to Google Sheets for chat {chat_id}")
            except Exception as e:
                logger.error(f"Failed to save incidents to Sheets: {e}. Data saved to SQLite only.")
            
        # 3.1. Проверка участников чата
        try:
            # Загружаем whitelist из Google Sheets
            whitelist = await self.sheets_manager.get_whitelist()
            logger.info(f"Loaded whitelist from Google Sheets: {len(whitelist)} chats")
            
            # Получаем whitelist для текущего чата
            chat_whitelist = whitelist.get(chat_id, [])
            
            if chat_whitelist:
                # Собираем текущих участников
                participants = await self.participant_collector.get_full_participants(chat_id)
                
                # Сверяем с whitelist
                participant_report = await self.participant_collector.compare_with_whitelist(
                    chat_id, chat_name, participants, chat_whitelist
                )
                
                # Сохраняем отчёт в БД
                await self.db_manager.insert_participant_report(participant_report)
                
                # Сохраняем отчёт в Google Sheets
                try:
                    await self.sheets_manager.append_participant_report(participant_report)
                    logger.info(f"Participant report saved to Google Sheets for chat {chat_id}")
                except Exception as e:
                    logger.error(f"Failed to save participant report to Sheets: {e}")
                    
                # Логируем результат
                if participant_report.missing or participant_report.extra:
                    missing_ids = [str(p.user_id) for p in participant_report.missing]
                    extra_ids = [str(p.user_id) for p in participant_report.extra]
                    
                    logger.warning(
                        f"Chat {chat_name} Check Results:\n"
                        f"❌ Missing IDs ({len(missing_ids)}): {', '.join(missing_ids)}\n"
                        f"⚠️ Unauthorized IDs ({len(extra_ids)}): {', '.join(extra_ids)}"
                    )
                
                # Добавляем отчет в результат для агрегации
                result.participant_report = participant_report
                
            else:
                logger.info(f"No whitelist configured for chat {chat_id}, skipping participant check")
                
        except Exception as e:
            logger.error(f"Participant check failed for chat {chat_id}: {e}")
        
        # 4. Notifier (Individual Alerts)
        # Отправляем алерты для критических и высоких инцидентов сразу
        admin_id = settings.aiogram.admin_id
        
        for incident in result.incidents:
            # Можно настроить фильтр по severity, чтобы не спамить
            # Например, отправлять только HIGH и CRITICAL сразу
            # А остальные - только в сводке
            if incident.severity.value in ['critical', 'high']:
                try:
                    await self.notifier.send_incident_alert(admin_id, incident)
                except Exception as e:
                    logger.error(f"Failed to send alert for incident {incident.id}: {e}")
                    
        return result

