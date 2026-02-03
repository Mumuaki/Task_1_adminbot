import unittest
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime, timedelta, timezone
import sys
from pathlib import Path

# Add project root
sys.path.append(str(Path(__file__).parent.parent))

from src.collector.history import MessageHistoryCollector

class TestHistory(unittest.IsolatedAsyncioTestCase):
    async def test_collect_messages(self):
        """Проверка сбора сообщений с фильтрацией по дате"""
        mock_client = AsyncMock()
        
        # Prepare dates
        # Use aware UTC datetimes
        now = datetime.now(timezone.utc)
        msg_date_new = now - timedelta(hours=1)      # Входит в 6 часов
        msg_date_boundary = now - timedelta(hours=5) # Входит
        msg_date_old = now - timedelta(hours=10)     # Не входит (старше 6 часов)
        
        # Prepare messages (mock objects)
        
        # Msg 1: New, with text and username
        msg1 = MagicMock()
        msg1.id = 100
        msg1.date = msg_date_new
        msg1.message = "Hello World"
        msg1.media = None
        msg1.sender_id = 123
        msg1.sender.username = "user1"
        msg1.voice = None # Not a voice
        
        # Msg 2: Boundary, voice, no username
        msg2 = MagicMock()
        msg2.id = 99
        msg2.date = msg_date_boundary
        msg2.message = None # Voice often has empty text or caption?
        msg2.media = True
        msg2.sender_id = 456
        msg2.sender = None # No sender info cached
        msg2.voice = True
        
        # Msg 3: Old (should stop iteration before or after processing?)
        # Our logic: "if message.date < offset_date: break". 
        # So this message acts as the stopper.
        msg3 = MagicMock()
        msg3.id = 50
        msg3.date = msg_date_old
        msg3.message = "Old message"
        
        # Helper for async generator
        async def mock_iter_messages(*args, **kwargs):
            yield msg1
            yield msg2
            yield msg3

        # side_effect works for calling the method, but here iter_messages is called and returns an async iterator
        # AsyncMock called returns a Coroutine by default, but we nneed it to return an Async Iterator
        # Setting side_effect on the call to return our generator works.
        mock_client.iter_messages.side_effect = mock_iter_messages
        
        collector = MessageHistoryCollector(mock_client)
        messages = await collector.collect_messages(chat_id=-100123, hours_back=6)
        
        # Checks
        self.assertEqual(len(messages), 2, "Should collect 2 messages and stop at the 3rd")
        
        # Verify Msg 1
        self.assertEqual(messages[0].message_id, 100)
        self.assertEqual(messages[0].text, "Hello World")
        self.assertEqual(messages[0].sender_username, "user1")
        self.assertFalse(messages[0].has_voice)
        
        # Verify Msg 2
        self.assertEqual(messages[1].message_id, 99)
        self.assertEqual(messages[1].has_voice, True)
        self.assertIsNone(messages[1].sender_username)
        
        # Msg 3 should NOT be in the list
        
if __name__ == "__main__":
    unittest.main()
