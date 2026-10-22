import asyncio
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from tg_monitor.config import Settings
from tg_monitor.store import MessageStore
from tg_monitor.telegram_client import TelegramMonitor


class _Message:
    id = 99
    raw_text = "AI agent 有新消息"
    date = datetime(2026, 10, 22, 9, 0, tzinfo=timezone.utc)

    async def get_sender(self):
        return type("Sender", (), {"first_name": "Ada", "last_name": None, "username": None})()


class _FailOnceClient:
    def __init__(self) -> None:
        self.attempts = 0

    async def send_message(self, *args, **kwargs) -> None:
        self.attempts += 1
        if self.attempts == 1:
            raise ConnectionError("temporary outage")


class AlertRecoveryTests(unittest.TestCase):
    def test_retries_an_alert_that_failed_after_message_persistence(self) -> None:
        directory = tempfile.TemporaryDirectory()
        store = MessageStore(Path(directory.name) / "messages.sqlite3")
        settings = Settings.from_env(
            {"TG_API_ID": "1", "TG_API_HASH": "hash", "TG_PHONE": "+61400000000", "TG_KEYWORDS": "AI agent"}
        )
        monitor = TelegramMonitor(settings, store, Path(directory.name) / "session")
        client = _FailOnceClient()
        monitor._client = client
        chat = type("Channel", (), {"id": 123, "megagroup": True, "broadcast": False, "username": None, "title": "AI 社群"})()

        with self.assertRaises(ConnectionError):
            asyncio.run(monitor._process_message(_Message(), chat, -100123, notify=True))
        asyncio.run(monitor._process_message(_Message(), chat, -100123, notify=True))

        self.assertEqual(client.attempts, 2)
        self.assertEqual(store.pending_alerts(), [])
        store.close()
        directory.cleanup()


if __name__ == "__main__":
    unittest.main()
