import aiohttp
from typing import List
from src.utils.logger import logger
from src.models.data import MessageData, Incident, AnalysisResult, IncidentCategory, Severity
import json


class LLMClient:
    """
    Клиент для анализа текста через CometAPI LLM.
    
    Атрибуты:
        api_key (str): Ключ API для CometAPI
        api_url (str): Base URL для CometAPI
        model (str): Название модели LLM
        temperature (float): Температура для генерации
    """
    
    def __init__(
        self,
        api_key: str,
        api_url: str,
        model: str = "gpt-4-turbo",
        temperature: float = 0.3
    ):
        self.api_key = api_key
        self.api_url = api_url.rstrip('/')
        self.model = model
        self.temperature = temperature
        
    def _build_system_prompt(self) -> str:
        """
        Формирование системного промпта для LLM.
        
        Возвращает:
            str: Системный промпт с инструкциями
        """
        return """Ты - система безопасности для корпоративного мониторинга Telegram-чатов.
Твоя задача - анализировать сообщения и выявлять потенциальные нарушения.

КАТЕГОРИИ НАРУШЕНИЙ:
1. leak - утечка конфиденциальной информации (пароли, API ключи, внутренние данные)
2. inappropriate - неподобающее поведение (оскорбления, домогательства, дискриминация)
3. spam - спам или реклама сторонних сервисов
4. off_topic - обсуждение нерабочих тем в рабочем чате
5. security_risk - потенциальная угроза безопасности (фишинг, вредоносные ссылки)

ФОРМАТ ОТВЕТА (строгий JSON):
{
  "incidents": [
    {
      "message_id": <int>,
      "category": "<leak|inappropriate|spam|off_topic|security_risk>",
      "severity": "<low|medium|high|critical>",
      "description": "<краткое описание нарушения>",
      "confidence": <float 0-1>
    }
  ],
  "summary": {
    "total_analyzed": <int>,
    "incidents_found": <int>,
    "risk_level": "<none|low|medium|high>"
  }
}

Проанализируй сообщения и верни результат В ФОРМАТЕ JSON. Не добавляй никаких комментариев за пределами JSON."""
    
    def _format_messages(self, messages: List[MessageData]) -> str:
        """
        Форматирование сообщений для промпта.
        
        Формат: [ID: xxx] [timestamp] @username: text
        
        Параметры:
            messages: Список сообщений
            
        Возвращает:
            str: Отформатированный текст
        """
        formatted = []
        for msg in messages:
            timestamp = msg.timestamp.strftime("%Y-%m-%d %H:%M")
            username = msg.sender_username or "Unknown"
            text = msg.text or ""
            
            # Добавляем транскрипцию голосовых если есть
            if msg.has_voice and msg.voice_transcription:
                text += f"\n[Транскрипция] {msg.voice_transcription}"
            
            formatted.append(
                f"[ID: {msg.message_id}] [{timestamp}] @{username}: {text}"
            )
        
        return "\n".join(formatted)
    
    async def analyze_messages(
        self,
        messages: List[MessageData],
        chat_name: str
    ) -> AnalysisResult:
        """
        Анализ сообщений на предмет нарушений.
        
        Параметры:
            messages: Список сообщений для анализа
            chat_name: Название чата для контекста
            
        Возвращает:
            AnalysisResult: Найденные инциденты + общая статистика
            
        Исключения:
            aiohttp.ClientError: При ошибках сети
            ValueError: При невалидном ответе API
        """
        if not messages:
            logger.warning("No messages to analyze")
            return AnalysisResult(
                incidents=[],
                total_analyzed=0,
                incidents_found=0,
                risk_level="none"
            )
        
        # Форматирование сообщений
        formatted_messages = self._format_messages(messages)
        
        # Формирование промпта
        system_prompt = self._build_system_prompt()
        user_prompt = f"""Чат: "{chat_name}"
Период: последние 6 часов

Сообщения для анализа:
---
{formatted_messages}
---

Проанализируй эти сообщения и верни результат в формате JSON."""
        
        # Подготовка запроса
        url = f"{self.api_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": self.temperature
        }
        
        logger.info(f"Sending {len(messages)} messages to LLM for analysis")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=60)) as response:
                    response.raise_for_status()
                    data = await response.json()
                    
                    # Извлечение контента
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "{}")
                    logger.debug(f"LLM response: {content}")
                    
                    # Парсинг JSON ответа
                    result = json.loads(content)
                    
                    # Валидация структуры
                    if "incidents" not in result or "summary" not in result:
                        raise ValueError("Invalid LLM response structure")
                    
                    # Создание списка Incident объектов
                    incidents = []
                    for inc_data in result["incidents"]:
                        try:
                            incident = Incident(
                                message_id=inc_data["message_id"],
                                chat_id=messages[0].chat_id,  # Берём из первого сообщения
                                chat_name=chat_name,
                                sender_id=None,  # Будет заполнено в ContentAnalyzer
                                sender_username=None,  # Будет заполнено в ContentAnalyzer
                                category=IncidentCategory(inc_data["category"]),
                                severity=Severity(inc_data["severity"]),
                                description=inc_data["description"],
                                confidence=float(inc_data["confidence"])
                            )
                            incidents.append(incident)
                        except (KeyError, ValueError) as e:
                            logger.warning(f"Failed to parse incident: {e}")
                            continue
                    
                    # Создание AnalysisResult
                    analysis_result = AnalysisResult(
                        incidents=incidents,
                        total_analyzed=result["summary"]["total_analyzed"],
                        incidents_found=result["summary"]["incidents_found"],
                        risk_level=result["summary"]["risk_level"]
                    )
                    
                    logger.info(f"Analysis complete: {len(incidents)} incidents found")
                    return analysis_result
                    
        except aiohttp.ClientError as e:
            logger.error(f"HTTP error calling LLM API: {e}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response: {e}")
            raise ValueError(f"Invalid JSON response from LLM: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in LLM analysis: {e}")
            raise
