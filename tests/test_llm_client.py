import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone
from src.core.llm_client import LLMClient
from src.models.data import MessageData, AnalysisResult, Incident, IncidentCategory, Severity
import json


@pytest.fixture
def llm_client():
    """Фикстура для создания LLMClient"""
    return LLMClient(
        api_key="test_api_key",
        api_url="https://api.test.com/v1",
        model="gpt-4-turbo",
        temperature=0.3
    )


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
            text="Наш API ключ: sk-abc123def456",
            timestamp=datetime.now(timezone.utc)
        ),
        MessageData(
            chat_id=-1001234567,
            message_id=3,
            sender_id=333,
            sender_username="user3",
            text="Отлично, спасибо!",
            timestamp=datetime.now(timezone.utc)
        )
    ]


def test_llm_client_initialization(llm_client):
    """Тест инициализации клиента"""
    assert llm_client.api_key == "test_api_key"
    assert llm_client.api_url == "https://api.test.com/v1"
    assert llm_client.model == "gpt-4-turbo"
    assert llm_client.temperature == 0.3


def test_build_system_prompt(llm_client):
    """Тест генерации системного промпта"""
    prompt = llm_client._build_system_prompt()
    
    assert "система безопасности" in prompt
    assert "leak" in prompt
    assert "inappropriate" in prompt
    assert "spam" in prompt
    assert "off_topic" in prompt
    assert "security_risk" in prompt
    assert "JSON" in prompt


def test_format_messages(llm_client, sample_messages):
    """Тест форматирования сообщений"""
    formatted = llm_client._format_messages(sample_messages)
    
    assert "[ID: 1]" in formatted
    assert "@user1: Привет всем!" in formatted
    assert "[ID: 2]" in formatted
    assert "@user2: Наш API ключ: sk-abc123def456" in formatted


def test_format_messages_with_voice(llm_client):
    """Тест форматирования сообщений с голосовыми"""
    messages = [
        MessageData(
            chat_id=-1001234567,
            message_id=1,
            sender_id=111,
            sender_username="user1",
            text="",
            has_voice=True,
            voice_transcription="Голосовое сообщение текст",
            timestamp=datetime.now(timezone.utc)
        )
    ]
    
    formatted = llm_client._format_messages(messages)
    
    assert "[Транскрипция] Голосовое сообщение текст" in formatted


@pytest.mark.asyncio
async def test_analyze_messages_empty_list(llm_client):
    """Тест анализа пустого списка сообщений"""
    result = await llm_client.analyze_messages([], "Test Chat")
    
    assert isinstance(result, AnalysisResult)
    assert result.total_analyzed == 0
    assert result.incidents_found == 0
    assert result.risk_level == "none"
    assert len(result.incidents) == 0


@pytest.mark.asyncio
async def test_analyze_messages_success(llm_client, sample_messages):
    """Тест успешного анализа сообщений"""
    
    # Мокаем ответ API
    mock_response_data = {
        "choices": [
            {
                "message": {
                    "content": json.dumps({
                        "incidents": [
                            {
                                "message_id": 2,
                                "category": "leak",
                                "severity": "high",
                                "description": "Обнаружена утечка API ключа",
                                "confidence": 0.95
                            }
                        ],
                        "summary": {
                            "total_analyzed": 3,
                            "incidents_found": 1,
                            "risk_level": "high"
                        }
                    })
                }
            }
        ]
    }
    
    # Создаём мок для aiohttp response
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json = AsyncMock(return_value=mock_response_data)
    
    # Используем контекстный менеджер для session.post
    mock_post_context = AsyncMock()
    mock_post_context.__aenter__ = AsyncMock(return_value=mock_response)
    mock_post_context.__aexit__ = AsyncMock(return_value=None)
    
    # Создаём мок для aiohttp session
    mock_session_instance = MagicMock()
    mock_session_instance.post = MagicMock(return_value=mock_post_context)
    
    # Контекстный менеджер для ClientSession
    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session_instance)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=None)
    
    # Патчим ClientSession
    with patch('aiohttp.ClientSession', return_value=mock_session_ctx):
        result = await llm_client.analyze_messages(sample_messages, "Test Chat")
    
    # Проверки
    assert isinstance(result, AnalysisResult)
    assert result.total_analyzed == 3
    assert result.incidents_found == 1
    assert result.risk_level == "high"
    assert len(result.incidents) == 1
    
    incident = result.incidents[0]
    assert incident.message_id == 2
    assert incident.category == IncidentCategory.LEAK
    assert incident.severity == Severity.HIGH
    assert incident.description == "Обнаружена утечка API ключа"
    assert incident.confidence == 0.95



@pytest.mark.asyncio
async def test_analyze_messages_invalid_json(llm_client, sample_messages):
    """Тест обработки невалидного JSON ответа"""
    
    mock_response_data = {
        "choices": [
            {
                "message": {
                    "content": "Not a valid JSON"
                }
            }
        ]
    }
    
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json = AsyncMock(return_value=mock_response_data)
    
    mock_post_context = AsyncMock()
    mock_post_context.__aenter__ = AsyncMock(return_value=mock_response)
    mock_post_context.__aexit__ = AsyncMock(return_value=None)
    
    mock_session_instance = MagicMock()
    mock_session_instance.post = MagicMock(return_value=mock_post_context)
    
    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session_instance)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=None)
    
    with patch('aiohttp.ClientSession', return_value=mock_session_ctx):
        with pytest.raises(ValueError, match="Invalid JSON response"):
            await llm_client.analyze_messages(sample_messages, "Test Chat")


@pytest.mark.asyncio
async def test_analyze_messages_missing_structure(llm_client, sample_messages):
    """Тест обработки ответа с неполной структурой"""
    
    # Ответ без поля "summary"
    mock_response_data = {
        "choices": [
            {
                "message": {
                    "content": json.dumps({
                        "incidents": []
                    })
                }
            }
        ]
    }
    
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json = AsyncMock(return_value=mock_response_data)
    
    mock_post_context = AsyncMock()
    mock_post_context.__aenter__ = AsyncMock(return_value=mock_response)
    mock_post_context.__aexit__ = AsyncMock(return_value=None)
    
    mock_session_instance = MagicMock()
    mock_session_instance.post = MagicMock(return_value=mock_post_context)
    
    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session_instance)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=None)
    
    with patch('aiohttp.ClientSession', return_value=mock_session_ctx):
        with pytest.raises(ValueError, match="Invalid LLM response structure"):
            await llm_client.analyze_messages(sample_messages, "Test Chat")
