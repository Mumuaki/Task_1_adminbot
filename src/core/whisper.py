import aiohttp
import asyncio
from pathlib import Path
from typing import Optional
from src.utils.logger import logger
from src.models.data import TranscriptionResult

class WhisperClient:
    """
    Клиент для транскрипции голосовых сообщений через CometAPI Whisper.
    
    Атрибуты:
        api_key (str): Ключ API для CometAPI
        api_url (str): Base URL для CometAPI
        model (str): Название модели Whisper
    """
    
    def __init__(self, api_key: str, api_url: str, model: str = "whisper-1"):
        self.api_key = api_key
        self.api_url = api_url.rstrip('/')
        self.model = model

    async def transcribe_voice(
        self,
        audio_path: Path,
        language: str = "ru"
    ) -> TranscriptionResult:
        """
        Транскрибирует аудиофайл.
        
        Параметры:
            audio_path: Путь к аудиофайлу
            language: Код языка (ISO-639-1)
            
        Возвращает:
            TranscriptionResult: Результат транскрипции
            
        Исключения:
            FileNotFoundError: Если файл не найден
            aiohttp.ClientError: При ошибках API
        """
        if not audio_path.exists():
            error_msg = f"Audio file not found: {audio_path}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)
            
        url = f"{self.api_url}/audio/transcriptions"
        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }
        
        # Подготовка multipart/form-data
        # Используем aiohttp.FormData для корректной передачи файлов
        form_data = aiohttp.FormData()
        form_data.add_field('model', self.model)
        form_data.add_field('language', language)
        
        # Открываем файл для чтения
        # В aiohttp лучше передавать открытый файл
        with open(audio_path, 'rb') as f:
            form_data.add_field(
                'file', 
                f, 
                filename=audio_path.name, 
                content_type='audio/ogg'  # Telegram голосовые обычно ogg/opus
            )
            
            logger.info(f"Sending audio file {audio_path.name} to Whisper for transcription")
            
            try:
                # Внимание: для multipart запроса с файлом не нужно передавать session отдельно 
                # или следить за закрытием файла вручную если используем with
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        url,
                        headers=headers,
                        data=form_data,
                        timeout=aiohttp.ClientTimeout(total=60)
                    ) as response:
                        if response.status != 200:
                            error_text = await response.text()
                            logger.error(f"Whisper API error ({response.status}): {error_text}")
                            response.raise_for_status()
                            
                        result = await response.json()
                        
                        text = result.get("text", "")
                        duration = result.get("duration", 0.0)
                        
                        logger.info(f"Transcription successful for {audio_path.name}")
                        return TranscriptionResult(
                            text=text,
                            language=language,
                            duration=float(duration)
                        )
            except Exception as e:
                logger.error(f"Whisper transcription request failed: {e}")
                raise e
