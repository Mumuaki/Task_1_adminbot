import asyncio
from typing import List, Optional, Any, Dict, Tuple
from pathlib import Path
from datetime import datetime

import gspread_asyncio
from google.oauth2.service_account import Credentials
from loguru import logger

from src.models.data import Incident, ParticipantReport, GlobalReport
from config.settings import settings


class GoogleSheetsManager:
    """
    Менеджер для работы с Google Sheets API в асинхронном режиме.
    
    Использует gspread_asyncio для неблокирующих запросов.
    """
    
    def __init__(
        self, 
        spreadsheet_id: str, 
        service_account_path: Path
    ) -> None:
        """
        Инициализация менеджера.
        
        Args:
            spreadsheet_id: ID Google таблицы.
            service_account_path: Путь к файлу ключей сервисного аккаунта.
        """
        self.spreadsheet_id = spreadsheet_id
        self.service_account_path = service_account_path
        self._agcm = gspread_asyncio.AsyncioGspreadClientManager(self._get_creds)
        self._client: Optional[gspread_asyncio.AsyncioGspreadClient] = None
        self._spreadsheet: Optional[gspread_asyncio.AsyncioGspreadSpreadsheet] = None

    def _get_creds(self) -> Credentials:
        """Получение учетных данных из файла."""
        creds = Credentials.from_service_account_file(str(self.service_account_path))
        scoped_creds = creds.with_scopes([
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ])
        return scoped_creds

    async def _get_spreadsheet(self) -> gspread_asyncio.AsyncioGspreadSpreadsheet:
        """Авторизация и получение объекта таблицы."""
        if not self._client:
            self._client = await self._agcm.authorize()
        
        if not self._spreadsheet:
            self._spreadsheet = await self._client.open_by_key(self.spreadsheet_id)
        
        return self._spreadsheet

    async def get_whitelist(self) -> Dict[int, List[int]]:
        """
        Чтение белого списка участников из листа 'Конфигурация'.
        
        Ожидаемый формат листа:
        chat_id | chat_name | allowed_users | monitoring_enabled
        
        Где allowed_users - строка с ID пользователей через запятую,
        например: "123456,789012,345678"
        
        Returns:
            Dict[int, List[int]]: Словарь {chat_id: [user_id1, user_id2, ...]}
        """
        try:
            ss = await self._get_spreadsheet()
            worksheet = await ss.worksheet("Конфигурация")
            
            # Получаем все значения листа (начиная со строки 2, пропуская заголовок)
            all_values = await worksheet.get_all_values()
            
            whitelist_dict = {}
            
            # Пропускаем заголовок (первая строка)
            for row in all_values[1:]:
                if len(row) < 3:  # Не хватает колонок
                    continue
                
                try:
                    chat_id = int(row[0])  # Колонка A: chat_id
                    allowed_users_str = row[2].strip()  # Колонка C: allowed_users
                    
                    # Парсим список ID через запятую
                    user_ids = []
                    if allowed_users_str:
                        for user_id_str in allowed_users_str.split(','):
                            try:
                                user_id = int(user_id_str.strip())
                                user_ids.append(user_id)
                            except ValueError:
                                logger.warning(
                                    f"Invalid user_id '{user_id_str}' for chat {chat_id}"
                                )
                                continue
                    
                    whitelist_dict[chat_id] = user_ids
                    
                except (ValueError, IndexError) as e:
                    logger.warning(f"Skipping invalid row in Конфигурация: {row}, error: {e}")
                    continue
            
            logger.info(
                f"Loaded whitelist for {len(whitelist_dict)} chats "
                f"with total {sum(len(v) for v in whitelist_dict.values())} allowed users"
            )
            return whitelist_dict
            
        except Exception as e:
            logger.error(f"Failed to read whitelist from Google Sheets: {e}")
            return {}

    async def get_monitored_chats(self) -> List[Tuple[int, str]]:
        """
        Получение списка чатов для мониторинга из листа 'Конфигурация'.
        
        Ожидаемый формат листа:
        chat_id | chat_name | allowed_users | monitoring_enabled
        
        Returns:
            List[Tuple[int, str]]: Список кортежей (chat_id, chat_name) 
                                   для чатов с monitoring_enabled = 'ДА' или 'TRUE'
        """
        try:
            ss = await self._get_spreadsheet()
            worksheet = await ss.worksheet("Конфигурация")
            
            # Получаем все значения листа
            all_values = await worksheet.get_all_values()
            
            monitored_chats = []
            
            # Пропускаем заголовок (первая строка)
            for row in all_values[1:]:
                if len(row) < 4:  # Не хватает колонок
                    continue
                
                try:
                    chat_id = int(row[0])  # Колонка A: chat_id
                    chat_name = row[1].strip()  # Колонка B: chat_name
                    monitoring_enabled = row[3].strip().upper()  # Колонка D: monitoring_enabled
                    
                    # Фильтруем только активные чаты
                    if monitoring_enabled in ['ДА', 'TRUE', 'YES', '1']:
                        monitored_chats.append((chat_id, chat_name))
                    
                except (ValueError, IndexError) as e:
                    logger.warning(
                        f"Skipping invalid row in Конфигурация: {row}, error: {e}"
                    )
                    continue
            
            logger.info(f"Loaded {len(monitored_chats)} monitored chats from Google Sheets")
            return monitored_chats
            
        except Exception as e:
            logger.error(f"Failed to read monitored chats from Google Sheets: {e}")
            return []

    async def append_incidents(self, incidents: List[Incident]) -> None:
        """
        Запись списка инцидентов в лист 'Инциденты'.
        
        Args:
            incidents: Список объектов Incident.
        """
        if not incidents:
            return

        try:
            ss = await self._get_spreadsheet()
            worksheet = await ss.worksheet("Инциденты")
            
            rows = []
            for inc in incidents:
                data = inc.to_dict()
                rows.append([
                    data["timestamp"],
                    data["chat_name"],
                    data["username"],
                    data["category"],
                    data["severity"],
                    data["description"],
                    data["confidence"],
                    data["status"]
                ])
            
            await worksheet.append_rows(rows)
            logger.info(f"Successfully appended {len(incidents)} incidents to Google Sheets")
        except Exception as e:
            logger.error(f"Failed to append incidents to Google Sheets: {e}")

    async def append_participant_report(self, report: ParticipantReport) -> None:
        """
        Запись отчета о сверке участников в лист 'Участники'.
        
        Формат листа:
        timestamp | chat_id | chat_name | missing_count | missing_users | extra_count | extra_users
        
        Где:
        - missing_users и extra_users - это строки вида "123(username), 456(username2)"
        
        Args:
            report: Объект ParticipantReport.
        """
        # Пропускаем если нет расхождений
        if not report.missing and not report.extra:
            logger.debug(f"No discrepancies in participant report for chat {report.chat_name}, skipping")
            return
            
        try:
            ss = await self._get_spreadsheet()
            worksheet = await ss.worksheet("Участники")
            
            # Формируем строку с недостающими участниками
            missing_users_str = ", ".join([
                f"{p.user_id}(@{p.username or 'N/A'})"
                for p in report.missing
            ]) if report.missing else ""
            
            # Формируем строку с лишними участниками
            extra_users_str = ", ".join([
                f"{p.user_id}(@{p.username or 'N/A'})"
                for p in report.extra
            ]) if report.extra else ""
            
            row = [
                report.timestamp.isoformat(),
                report.chat_id,
                report.chat_name,
                len(report.missing),
                missing_users_str,
                len(report.extra),
                extra_users_str
            ]
            
            await worksheet.append_row(row)
            logger.info(
                f"Appended participant report for {report.chat_name}: "
                f"{len(report.missing)} missing, {len(report.extra)} extra"
            )
        except Exception as e:
            logger.error(f"Failed to append participant report to Google Sheets: {e}")

    async def append_scan_log(self, report: GlobalReport) -> None:
        """
        Запись итогов сканирования в лист 'Логи сканирования'.
        
        Формат листа:
        timestamp | chats_scanned | messages_processed | incidents_found | status | duration_sec
        
        Args:
            report: Объект GlobalReport.
        """
        try:
            ss = await self._get_spreadsheet()
            worksheet = await ss.worksheet("Логи сканирования")
            
            row = [
                report.start_time.isoformat(),
                report.chats_scanned,
                report.total_messages,
                report.total_incidents,
                "COMPLETED",
                f"{report.duration_seconds:.2f}"
            ]
            
            await worksheet.append_row(row)
            logger.info(
                f"Successfully appended scan log: {report.chats_scanned} chats, "
                f"{report.total_incidents} incidents, {report.duration_seconds:.2f}s"
            )
        except Exception as e:
            logger.error(f"Failed to append scan log to Google Sheets: {e}")
