from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional, List
from enum import Enum

# ===== ENUMS =====

class IncidentCategory(str, Enum):
    LEAK = "leak"
    INAPPROPRIATE = "inappropriate"
    SPAM = "spam"
    OFF_TOPIC = "off_topic"
    SECURITY_RISK = "security_risk"

class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class IncidentStatus(str, Enum):
    NEW = "new"
    CONFIRMED = "confirmed"
    FALSE_POSITIVE = "false_positive"
    IGNORED = "ignored"

# ===== DATA MODELS =====

class MessageData(BaseModel):
    """Модель сообщения из Telegram"""
    chat_id: int
    message_id: int
    sender_id: Optional[int] = None
    sender_username: Optional[str] = None
    text: Optional[str] = None
    has_voice: bool = False
    voice_path: Optional[str] = None  # Path object as string
    voice_transcription: Optional[str] = None
    timestamp: datetime
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "chat_id": -1001234567890,
                "message_id": 12345,
                "sender_id": 123456789,
                "sender_username": "john_doe",
                "text": "Привет, коллеги!",
                "has_voice": False,
                "timestamp": "2026-02-02T15:30:00"
            }
        }
    )

class TranscriptionResult(BaseModel):
    """Результат транскрипции голосового"""
    text: str
    language: str = "ru"
    duration: float
    confidence: Optional[float] = None

class Incident(BaseModel):
    """Модель инцидента безопасности"""
    id: Optional[int] = None
    message_id: int
    chat_id: int
    chat_name: str
    sender_id: Optional[int] = None
    sender_username: Optional[str] = None
    category: IncidentCategory
    severity: Severity
    description: str
    confidence: float = Field(ge=0.0, le=1.0)
    status: IncidentStatus = IncidentStatus.NEW
    detected_at: datetime = Field(default_factory=datetime.now)
    
    def to_dict(self) -> dict:
        """Сериализация для Google Sheets"""
        return {
            "timestamp": self.detected_at.isoformat(),
            "chat_name": self.chat_name,
            "username": self.sender_username or "Unknown",
            "category": self.category.value,
            "severity": self.severity.value,
            "description": self.description,
            "confidence": f"{self.confidence:.2%}",
            "status": self.status.value
        }

class ParticipantData(BaseModel):
    """Модель участника чата"""
    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_bot: bool = False

class ParticipantReport(BaseModel):
    """Отчет о сверке участников"""
    chat_id: int
    chat_name: str
    missing: List[ParticipantData] = []  # Должны быть, но их нет
    extra: List[ParticipantData] = []    # Есть, но не в whitelist
    timestamp: datetime = Field(default_factory=datetime.now)

class AnalysisResult(BaseModel):
    """Результат LLM анализа сообщений"""
    incidents: List[Incident]
    total_analyzed: int
    incidents_found: int
    risk_level: str  # "none" | "low" | "medium" | "high"

class ChatAnalysisResult(BaseModel):
    """Результат анализа одного чата"""
    chat_id: int
    chat_name: str
    messages_analyzed: int
    voices_transcribed: int
    incidents: List[Incident]
    processing_time: float
    participant_report: Optional[ParticipantReport] = None

    
class GlobalReport(BaseModel):
    """Сводный отчет по всем чатам"""
    scan_id: Optional[int] = None
    start_time: datetime
    end_time: datetime
    chats_scanned: int
    total_messages: int
    total_voices: int
    total_incidents: int
    critical_incidents: int
    high_incidents: int
    medium_incidents: int
    low_incidents: int
    missing_participants: int
    extra_participants: int
    duration_seconds: float
    missing_ids: List[int] = []
    extra_ids: List[int] = []
    
    def to_scan_log(self) -> dict:
        """Преобразование в формат для scan_logs таблицы"""
        return {
            "start_time": self.start_time,
            "end_time": self.end_time,
            "chats_scanned": self.chats_scanned,
            "messages_processed": self.total_messages,
            "voices_transcribed": self.total_voices,
            "incidents_found": self.total_incidents,
            "status": "completed",
            "duration_seconds": self.duration_seconds
        }
