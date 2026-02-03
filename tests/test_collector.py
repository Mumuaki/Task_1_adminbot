import unittest
from unittest.mock import MagicMock, AsyncMock, patch
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.collector.client import TelethonCollector
from src.collector.history import MessageHistoryCollector
from src.models.data import MessageData

class TestCollector(unittest.IsolatedAsyncioTestCase):
    @patch('src.collector.client.TelegramClient')
    async def test_initialization(self, mock_client_cls):
        """Проверка инициализации и авторизованной сессии"""
        # Setup mock
        mock_client_instance = AsyncMock()
        mock_client_cls.return_value = mock_client_instance
        
        # Init collector
        collector = TelethonCollector(12345, "hash", "+7999", Path("data/sessions/test.session"))
        
        # Verify Telethon client creation
        mock_client_cls.assert_called_once()
        
        # Setup behaviors
        mock_client_instance.connect.return_value = None
        mock_client_instance.is_user_authorized.return_value = True
        mock_user = MagicMock()
        mock_user.id = 123
        mock_user.first_name = "Test"
        mock_client_instance.get_me.return_value = mock_user
        
        # Act
        await collector.start_session()
        
        # Assert
        mock_client_instance.connect.assert_called_once()
        mock_client_instance.is_user_authorized.assert_called_once()
        # start() не должен вызываться, если уже авторизованы
        mock_client_instance.start.assert_not_called()
        
    @patch('src.collector.client.TelegramClient')
    async def test_auth_flow_interactive(self, mock_client_cls):
        """Проверка вызова start() если не авторизован"""
        mock_client_instance = AsyncMock()
        mock_client_cls.return_value = mock_client_instance
        
        collector = TelethonCollector(12345, "hash", "+7999", Path("data/sessions/test.session"))
        
        mock_client_instance.is_user_authorized.return_value = False
        mock_user = MagicMock()
        mock_user.id = 123
        mock_client_instance.get_me.return_value = mock_user
        
        await collector.start_session()
        
        # Должен вызваться start(), так как is_user_authorized=False
        mock_client_instance.start.assert_called_once_with(phone="+7999")
        
    @patch('src.collector.client.TelegramClient')
    async def test_health_check(self, mock_client_cls):
        mock_client_instance = AsyncMock()
        # is_connected - синхронный метод в Telethon, поэтому используем MagicMock
        mock_client_instance.is_connected = MagicMock()
        
        mock_client_cls.return_value = mock_client_instance
        collector = TelethonCollector(1, "h", "p", Path("p"))
        
        # Case 1: Connected and happy
        mock_client_instance.is_connected.return_value = True
        mock_client_instance.get_me.return_value = MagicMock()
        self.assertTrue(await collector.health_check())
        
        # Case 2: Not connected
        mock_client_instance.is_connected.return_value = False
        self.assertFalse(await collector.health_check())

class TestMessageHistoryCollector(unittest.IsolatedAsyncioTestCase):
    async def test_collect_messages(self):
        mock_client = AsyncMock()
        collector = MessageHistoryCollector(mock_client)
        
        # Mock message
        msg1 = MagicMock()
        msg1.id = 100
        msg1.date = datetime.now(timezone.utc) # Real datetime for comparison
        msg1.message = "Test text"
        msg1.media = None
        msg1.voice = None
        msg1.sender = MagicMock()
        msg1.sender.username = "sender_u"
        msg1.sender_id = 999
        msg1.chat_id = 123
        
        # iter_messages mock
        async def async_iter(*args, **kwargs):
            yield msg1
            
        mock_client.iter_messages = MagicMock(side_effect=async_iter)
        
        # Act
        messages = await collector.collect_messages(123, hours_back=1)
        
        # Assert
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].text, "Test text")
        self.assertEqual(messages[0].sender_username, "sender_u")

    @patch('src.collector.history.asyncio.wait_for')
    async def test_download_voice(self, mock_wait_for):
        mock_client = AsyncMock()
        collector = MessageHistoryCollector(mock_client)
        
        msg = MagicMock()
        msg.id = 555
        msg.chat_id = 777
        msg.voice = True
        msg.file.size = 1024 # Small enough
        
        # Mock saving path
        expected_path = Path("data/temp/777_555.ogg")
        mock_wait_for.return_value = str(expected_path)
        
        msg.download_media = MagicMock()
        
        # Act
        path = await collector.download_voice(msg)
        
        # Assert
        self.assertEqual(path, expected_path)
        msg.download_media.assert_called_once() # Should be called
        
    async def test_download_voice_size_limit(self):
        mock_client = AsyncMock()
        collector = MessageHistoryCollector(mock_client)
        
        msg = MagicMock()
        msg.voice = True
        msg.file.size = 100 * 1024 * 1024 # 100 MB > 50 MB limit
        
        # Act
        path = await collector.download_voice(msg, max_size_mb=50)
        
        # Assert
        self.assertIsNone(path)

if __name__ == "__main__":
    unittest.main()
