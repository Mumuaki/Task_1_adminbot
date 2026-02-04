import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock
from src.core.llm_client import LLMClient
from src.core.analyzer import ContentAnalyzer
from src.models.data import MessageData
import os
import aiohttp


@pytest.mark.integration
@pytest.mark.asyncio
async def test_llm_client_real_api():
    """
    Интеграционный тест с реальным CometAPI.
    """
    api_key = os.getenv("COMET_API_KEY")
    api_url = os.getenv("COMET_API_URL", "https://api.comet.com/v1")
    
    if not api_key or len(api_key) < 20 or "your_" in api_key or "sk-test" in api_key:
        pytest.skip("COMET_API_KEY not set or placeholder/test key")
    
    # Создаём клиента
    llm_client = LLMClient(
        api_key=api_key,
        api_url=api_url,
        temperature=0.2
    )
    
    # Тестовые сообщения с явной утечкой
    test_messages = [
        MessageData(
            chat_id=-1001234567,
            message_id=1,
            sender_id=111,
            sender_username="alice",
            text="Привет, как дела?",
            timestamp=datetime.now(timezone.utc)
        ),
        MessageData(
            chat_id=-1001234567,
            message_id=2,
            sender_id=222,
            sender_username="bob",
            text="Вот наш API ключ для продакшена: sk-abc123def456ghi789",
            timestamp=datetime.now(timezone.utc)
        ),
        MessageData(
            chat_id=-1001234567,
            message_id=3,
            sender_id=333,
            sender_username="charlie",
            text="Отлично, спасибо!",
            timestamp=datetime.now(timezone.utc)
        )
    ]
    
    # Вызываем анализ
    try:
        result = await llm_client.analyze_messages(test_messages, "Test Chat")
    except aiohttp.ClientResponseError as e:
        if e.status in [401, 402]:
            pytest.skip(f"API key auth/payment error: {e}")
        raise e
    
    # Проверки
    assert result is not None
    assert result.total_analyzed == 3
    assert result.incidents_found >= 1  # Должен найти как минимум утечку API ключа
    
    # Проверяем что найден инцидент с message_id=2
    leak_incidents = [inc for inc in result.incidents if inc.message_id == 2]
    assert len(leak_incidents) >= 1
    
    # Проверяем категорию и severity
    leak_incident = leak_incidents[0]
    # Должна быть категория leak и высокая критичность
    assert leak_incident.category.value in ["leak", "security_risk"]
    assert leak_incident.severity.value in ["high", "critical"]
    assert leak_incident.confidence > 0.7
    
    print(f"\n✅ Integration test passed!")
    print(f"Found {result.incidents_found} incidents")
    print(f"Risk level: {result.risk_level}")
    for inc in result.incidents:
        print(f"  - Message {inc.message_id}: {inc.category.value} ({inc.severity.value})")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_content_analyzer_full_flow():
    """
    Интеграционный тест полного потока ContentAnalyzer.
    """
    api_key = os.getenv("COMET_API_KEY")
    api_url = os.getenv("COMET_API_URL", "https://api.comet.com/v1")
    
    if not api_key or len(api_key) < 20 or "your_" in api_key or "sk-test" in api_key:
        pytest.skip("COMET_API_KEY not set or placeholder/test key")
    
    # Создаём реальный LLMClient
    llm_client = LLMClient(
        api_key=api_key,
        api_url=api_url,
        temperature=0.3
    )
    
    # Создаём ContentAnalyzer
    analyzer = ContentAnalyzer(llm_client=llm_client, whisper_client=MagicMock())
    
    # Тестовые сообщения
    test_messages = [
        MessageData(
            chat_id=-1001234567,
            message_id=1,
            sender_id=111,
            sender_username="alice",
            text="Доброе утро всем!",
            timestamp=datetime.now(timezone.utc)
        ),
        MessageData(
            chat_id=-1001234567,
            message_id=2,
            sender_id=222,
            sender_username="bob",
            text="Пароль от базы данных: admin123",
            timestamp=datetime.now(timezone.utc)
        ),
        MessageData(
            chat_id=-1001234567,
            message_id=3,
            sender_id=333,
            sender_username="charlie",
            text="Купите наш супер продукт по ссылке: http://spam.com",
            timestamp=datetime.now(timezone.utc)
        )
    ]
    
    # Обрабатываем чат
    try:
        result = await analyzer.process_chat(
            chat_id=-1001234567,
            chat_name="Integration Test Chat",
            messages=test_messages
        )
        
        # Если API вернул ошибку, которую analyzer проглотил (но логировал),
        # проверим не пустые ли инциденты при наличии явных триггеров.
        # В данном случае, если мы здесь, значит process_chat не бросил исключение.
    except Exception as e:
        # Если исключение все же вылетело
        raise e
    
    # Проверки
    assert result is not None
    assert result.chat_id == -1001234567
    assert result.chat_name == "Integration Test Chat"
    assert result.messages_analyzed == 3
    
    # Должны быть найдены инциденты (как минимум утечка пароля)
    if len(result.incidents) == 0:
        # Проверяем, не произошло ли это из-за ошибки API (которую анализатор логгирует, но не пробрасывает)
        try:
            # Отправляем одно пустое/тестовое сообщение для проверки связи
            ping_msg = MessageData(
                chat_id=0, message_id=0, sender_id=0, 
                text="ping", timestamp=datetime.now(timezone.utc)
            )
            await analyzer.llm_client.analyze_messages([ping_msg], "ping")
        except aiohttp.ClientResponseError as e:
            if e.status in [401, 402]:
                pytest.skip(f"API key auth/payment error during full flow: {e}")
        
    assert len(result.incidents) >= 1
    
    # Проверяем что sender_id и sender_username заполнены
    for incident in result.incidents:
        assert incident.sender_id is not None
        assert incident.sender_username is not None
        assert incident.chat_id == -1001234567
        assert incident.chat_name == "Integration Test Chat"
    
    # Проверяем агрегацию
    start_time = datetime.now(timezone.utc)
    end_time = datetime.now(timezone.utc)
    
    global_report = await analyzer.aggregate_results(
        chat_results=[result],
        start_time=start_time,
        end_time=end_time
    )
    
    assert global_report.chats_scanned == 1
    assert global_report.total_messages == 3
    assert global_report.total_incidents >= 1
    
    print(f"\n✅ Full flow integration test passed!")
    print(f"Chat analysis result:")
    print(f"  - Messages analyzed: {result.messages_analyzed}")
    print(f"  - Incidents found: {len(result.incidents)}")
    print(f"  - Processing time: {result.processing_time:.2f}s")
    print(f"\nGlobal report:")
    print(f"  - Total incidents: {global_report.total_incidents}")
    print(f"  - Critical: {global_report.critical_incidents}")
    print(f"  - High: {global_report.high_incidents}")
    print(f"  - Medium: {global_report.medium_incidents}")
    print(f"  - Low: {global_report.low_incidents}")
