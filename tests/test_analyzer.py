import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone
from src.core.analyzer import ContentAnalyzer
from src.core.llm_client import LLMClient
from src.models.data import (
    MessageData, 
    AnalysisResult, 
    ChatAnalysisResult,
    GlobalReport,
    Incident, 
    IncidentCategory, 
    Severity
)


@pytest.fixture
def mock_llm_client():
    """Фикстура для мокированного LLMClient"""
    return MagicMock(spec=LLMClient)


@pytest.fixture
def content_analyzer(mock_llm_client):
    """Фикстура для ContentAnalyzer"""
    return ContentAnalyzer(llm_client=mock_llm_client)


@pytest.fixture
def sample_messages():
    """Фикстура с примерами сообщений"""
    return [
        MessageData(
            chat_id=-1001234567,
            message_id=1,
            sender_id=111,
            sender_username="user1",
            text="Привет всем!",
            timestamp=datetime.now(timezone.utc)
        ),
        MessageData(
            chat_id=-1001234567,
            message_id=2,
            sender_id=222,
            sender_username="user2",
            text="Наш API ключ: sk-abc123",
            timestamp=datetime.now(timezone.utc)
        )
    ]


@pytest.mark.asyncio
async def test_process_chat_empty_messages(content_analyzer, mock_llm_client):
    """Тест обработки чата с пустым списком сообщений"""
    
    result = await content_analyzer.process_chat(
        chat_id=-1001234567,
        chat_name="Test Chat",
        messages=[]
    )
    
    assert isinstance(result, ChatAnalysisResult)
    assert result.chat_id == -1001234567
    assert result.chat_name == "Test Chat"
    assert result.messages_analyzed == 0
    assert result.voices_transcribed == 0
    assert len(result.incidents) == 0
    
    # LLM не должен вызываться
    mock_llm_client.analyze_messages.assert_not_called()


@pytest.mark.asyncio
async def test_process_chat_filters_empty_text(content_analyzer, mock_llm_client):
    """Тест фильтрации сообщений с пустым текстом"""
    
    messages = [
        MessageData(
            chat_id=-1001234567,
            message_id=1,
            sender_id=111,
            sender_username="user1",
            text="",  # Пустой текст
            timestamp=datetime.now(timezone.utc)
        ),
        MessageData(
            chat_id=-1001234567,
            message_id=2,
            sender_id=222,
            sender_username="user2",
            text="   ",  # Только пробелы
            timestamp=datetime.now(timezone.utc)
        ),
        MessageData(
            chat_id=-1001234567,
            message_id=3,
            sender_id=333,
            sender_username="user3",
            text=None,  # None
            timestamp=datetime.now(timezone.utc)
        )
    ]
    
    result = await content_analyzer.process_chat(
        chat_id=-1001234567,
        chat_name="Test Chat",
        messages=messages
    )
    
    assert result.messages_analyzed == 0
    mock_llm_client.analyze_messages.assert_not_called()


@pytest.mark.asyncio
async def test_process_chat_success(content_analyzer, mock_llm_client, sample_messages):
    """Тест успешной обработки чата"""
    
    # Мокируем ответ LLM
    mock_analysis_result = AnalysisResult(
        incidents=[
            Incident(
                message_id=2,
                chat_id=-1001234567,
                chat_name="Test Chat",
                sender_id=None,  # Будет заполнено в ContentAnalyzer
                sender_username=None,
                category=IncidentCategory.LEAK,
                severity=Severity.HIGH,
                description="API ключ обнаружен",
                confidence=0.95
            )
        ],
        total_analyzed=2,
        incidents_found=1,
        risk_level="high"
    )
    
    mock_llm_client.analyze_messages = AsyncMock(return_value=mock_analysis_result)
    
    result = await content_analyzer.process_chat(
        chat_id=-1001234567,
        chat_name="Test Chat",
        messages=sample_messages
    )
    
    # Проверки
    assert isinstance(result, ChatAnalysisResult)
    assert result.chat_id == -1001234567
    assert result.chat_name == "Test Chat"
    assert result.messages_analyzed == 2
    assert result.voices_transcribed == 0
    assert len(result.incidents) == 1
    
    # Проверка обогащения инцидента данными отправителя
    incident = result.incidents[0]
    assert incident.message_id == 2
    assert incident.sender_id == 222
    assert incident.sender_username == "user2"
    assert incident.category == IncidentCategory.LEAK
    assert incident.severity == Severity.HIGH
    
    # LLM должен быть вызван с валидными сообщениями
    mock_llm_client.analyze_messages.assert_called_once()
    call_args = mock_llm_client.analyze_messages.call_args
    assert len(call_args[0][0]) == 2  # 2 валидных сообщения
    assert call_args[0][1] == "Test Chat"


@pytest.mark.asyncio
async def test_process_chat_with_voice_transcription(content_analyzer, mock_llm_client):
    """Тест подсчёта транскрибированных голосовых"""
    
    messages = [
        MessageData(
            chat_id=-1001234567,
            message_id=1,
            sender_id=111,
            sender_username="user1",
            text="Текст",
            has_voice=True,
            voice_transcription="Транскрипция голоса",
            timestamp=datetime.now(timezone.utc)
        ),
        MessageData(
            chat_id=-1001234567,
            message_id=2,
            sender_id=222,
            sender_username="user2",
            text="Обычный текст",
            timestamp=datetime.now(timezone.utc)
        )
    ]
    
    mock_analysis_result = AnalysisResult(
        incidents=[],
        total_analyzed=2,
        incidents_found=0,
        risk_level="none"
    )
    
    mock_llm_client.analyze_messages = AsyncMock(return_value=mock_analysis_result)
    
    result = await content_analyzer.process_chat(
        chat_id=-1001234567,
        chat_name="Test Chat",
        messages=messages
    )
    
    assert result.voices_transcribed == 1


@pytest.mark.asyncio
async def test_aggregate_results_empty():
    """Тест агрегации пустого списка результатов"""
    
    analyzer = ContentAnalyzer(llm_client=MagicMock())
    
    start_time = datetime.now(timezone.utc)
    end_time = datetime.now(timezone.utc)
    
    report = await analyzer.aggregate_results(
        chat_results=[],
        start_time=start_time,
        end_time=end_time
    )
    
    assert isinstance(report, GlobalReport)
    assert report.chats_scanned == 0
    assert report.total_messages == 0
    assert report.total_voices == 0
    assert report.total_incidents == 0
    assert report.critical_incidents == 0
    assert report.high_incidents == 0
    assert report.medium_incidents == 0
    assert report.low_incidents == 0


@pytest.mark.asyncio
async def test_aggregate_results_success():
    """Тест успешной агрегации результатов"""
    
    analyzer = ContentAnalyzer(llm_client=MagicMock())
    
    # Создаём несколько результатов чатов
    chat_results = [
        ChatAnalysisResult(
            chat_id=-1001,
            chat_name="Chat 1",
            messages_analyzed=50,
            voices_transcribed=5,
            incidents=[
                Incident(
                    message_id=1,
                    chat_id=-1001,
                    chat_name="Chat 1",
                    category=IncidentCategory.LEAK,
                    severity=Severity.CRITICAL,
                    description="Test",
                    confidence=0.9
                ),
                Incident(
                    message_id=2,
                    chat_id=-1001,
                    chat_name="Chat 1",
                    category=IncidentCategory.SPAM,
                    severity=Severity.LOW,
                    description="Test",
                    confidence=0.7
                )
            ],
            processing_time=3.5
        ),
        ChatAnalysisResult(
            chat_id=-1002,
            chat_name="Chat 2",
            messages_analyzed=30,
            voices_transcribed=2,
            incidents=[
                Incident(
                    message_id=3,
                    chat_id=-1002,
                    chat_name="Chat 2",
                    category=IncidentCategory.INAPPROPRIATE,
                    severity=Severity.HIGH,
                    description="Test",
                    confidence=0.85
                )
            ],
            processing_time=2.1
        )
    ]
    
    start_time = datetime(2026, 2, 3, 12, 0, 0, tzinfo=timezone.utc)
    end_time = datetime(2026, 2, 3, 12, 10, 0, tzinfo=timezone.utc)
    
    report = await analyzer.aggregate_results(
        chat_results=chat_results,
        start_time=start_time,
        end_time=end_time
    )
    
    # Проверки
    assert report.chats_scanned == 2
    assert report.total_messages == 80  # 50 + 30
    assert report.total_voices == 7  # 5 + 2
    assert report.total_incidents == 3
    assert report.critical_incidents == 1
    assert report.high_incidents == 1
    assert report.medium_incidents == 0
    assert report.low_incidents == 1
    assert report.duration_seconds == 600.0  # 10 минут
