import unittest
from unittest.mock import MagicMock, AsyncMock, patch
import sys
from pathlib import Path
from typing import List

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.collector.participants import ParticipantCollector
from src.models.data import ParticipantData

class TestParticipantCollector(unittest.IsolatedAsyncioTestCase):
    async def test_get_full_participants(self):
        # Setup mock client
        mock_client = AsyncMock()
        
        # Mock users
        user1 = MagicMock()
        user1.id = 1
        user1.username = "user1"
        user1.first_name = "User"
        user1.last_name = "One"
        user1.bot = False
        
        user2 = MagicMock()
        user2.id = 2
        user2.username = "user2"
        user2.first_name = "User"
        user2.last_name = "Two"
        user2.bot = True
        
        # iter_participants returns an async iterator
        # We can simulate this by mocking __aiter__
        async def async_iter(*args, **kwargs):
            yield user1
            yield user2
            
        mock_client.iter_participants = MagicMock(side_effect=async_iter)
        
        collector = ParticipantCollector(mock_client)
        
        # Act
        participants = await collector.get_full_participants(123)
        
        # Assert
        self.assertEqual(len(participants), 2)
        self.assertEqual(participants[0].user_id, 1)
        self.assertFalse(participants[0].is_bot)
        self.assertEqual(participants[1].user_id, 2)
        self.assertTrue(participants[1].is_bot)
        
        # Verify call arguments
        mock_client.iter_participants.assert_called_once_with(123, aggressive=True)

    async def test_compare_with_whitelist(self):
        mock_client = AsyncMock()
        collector = ParticipantCollector(mock_client)
        
        # Participants currently in chat: [1, 2, 3]
        participants = [
            ParticipantData(user_id=1, username="u1"),
            ParticipantData(user_id=2, username="u2"),
            ParticipantData(user_id=3, username="u3"),
        ]
        
        # Whitelist: [1, 3, 4]
        # Missing: 4
        # Extra: 2
        whitelist = [1, 3, 4]
        
        report = await collector.compare_with_whitelist(
            chat_id=100,
            chat_name="Test Chat",
            participants=participants,
            whitelist=whitelist
        )
        
        self.assertEqual(report.chat_id, 100)
        self.assertEqual(len(report.missing), 1)
        self.assertEqual(report.missing[0].user_id, 4)
        
        self.assertEqual(len(report.extra), 1)
        self.assertEqual(report.extra[0].user_id, 2)
        self.assertEqual(report.extra[0].username, "u2")

if __name__ == "__main__":
    unittest.main()
