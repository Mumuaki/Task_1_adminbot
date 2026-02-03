import unittest
from datetime import datetime
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.models.data import Incident, IncidentCategory, Severity, MessageData

class TestModels(unittest.TestCase):
    def test_incident_creation(self):
        """Проверка создания и сериализации инцидента"""
        incident = Incident(
            message_id=123,
            chat_id=-100,
            chat_name="Test Chat",
            category=IncidentCategory.LEAK,
            severity=Severity.HIGH,
            description="API key found",
            confidence=0.95
        )
        
        self.assertEqual(incident.category, "leak")
        data = incident.to_dict()
        self.assertEqual(data["category"], "leak")
        self.assertEqual(data["severity"], "high")
        self.assertEqual(data["confidence"], "95.00%")
        
    def test_message_data(self):
        """Проверка валидации MessageData"""
        msg = MessageData(
            chat_id=-100,
            message_id=1,
            timestamp=datetime.now(),
            text="Hello"
        )
        self.assertFalse(msg.has_voice)
        self.assertIsNone(msg.voice_path)

if __name__ == "__main__":
    unittest.main()
