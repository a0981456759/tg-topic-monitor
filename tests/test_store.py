import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

from tg_monitor.store import MessageStore, StoredMessage


class MessageStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.store = MessageStore(Path(self.directory.name) / "messages.sqlite3")

    def tearDown(self) -> None:
        self.store.close()
        self.directory.cleanup()

    def test_records_a_message_once_using_chat_and_message_ids(self) -> None:
        message = StoredMessage(
            chat_id="-100123",
            message_id=42,
            chat_title="投資討論",
            sender_name="Ada",
            text="AI agent 值得留意",
            matched_keywords=("AI Agent",),
            sent_at=datetime(2026, 10, 22, 9, 0, tzinfo=timezone.utc),
            message_link="https://t.me/c/123/42",
        )

        self.assertTrue(self.store.record(message))
        self.assertFalse(self.store.record(message))

    def test_reads_a_day_in_chronological_order(self) -> None:
        later = StoredMessage(
            chat_id="2", message_id=2, chat_title="B", sender_name="B",
            text="later", matched_keywords=("AI",),
            sent_at=datetime(2026, 10, 22, 10, 0, tzinfo=timezone.utc), message_link=None,
        )
        earlier = StoredMessage(
            chat_id="1", message_id=1, chat_title="A", sender_name="A",
            text="earlier", matched_keywords=("投資",),
            sent_at=datetime(2026, 10, 22, 8, 0, tzinfo=timezone.utc), message_link=None,
        )
        other_day = StoredMessage(
            chat_id="3", message_id=3, chat_title="C", sender_name="C",
            text="other", matched_keywords=("AI",),
            sent_at=datetime(2026, 10, 23, 8, 0, tzinfo=timezone.utc), message_link=None,
        )
        self.store.record(later)
        self.store.record(earlier)
        self.store.record(other_day)

        messages = self.store.messages_for_day(date(2026, 10, 22))

        self.assertEqual([message.text for message in messages], ["earlier", "later"])

    def test_keeps_a_failed_alert_pending_for_retry(self) -> None:
        message = StoredMessage(
            chat_id="-100123", message_id=7, chat_title="投資討論", sender_name="Ada",
            text="AI agent 值得留意", matched_keywords=("AI Agent",),
            sent_at=datetime(2026, 10, 22, 9, 0, tzinfo=timezone.utc), message_link=None,
        )

        self.assertTrue(self.store.record(message, queue_alert=True))
        self.assertEqual(self.store.pending_alerts(), [message])
        self.store.mark_alert_sent(message.chat_id, message.message_id)

        self.assertEqual(self.store.pending_alerts(), [])

    def test_tracks_telegram_and_slack_alert_delivery_independently(self) -> None:
        message = StoredMessage(
            chat_id="-100123", message_id=8, chat_title="投資討論", sender_name="Ada",
            text="AI agent 值得留意", matched_keywords=("AI Agent",),
            sent_at=datetime(2026, 10, 22, 9, 0, tzinfo=timezone.utc), message_link=None,
        )
        self.store.record(message, queue_telegram=True, queue_slack=True)

        self.store.mark_telegram_sent(message.chat_id, message.message_id)

        self.assertEqual(self.store.pending_telegram_alerts(), [])
        self.assertEqual(self.store.pending_slack_alerts(), [message])

    def test_uses_sydney_calendar_boundaries_for_daily_reads(self) -> None:
        sydney_midnight = StoredMessage(
            chat_id="1", message_id=11, chat_title="A", sender_name="A", text="local day",
            matched_keywords=("AI",),
            sent_at=datetime(2026, 10, 21, 13, 30, tzinfo=timezone.utc), message_link=None,
        )
        self.store.record(sydney_midnight)

        messages = self.store.messages_for_local_day(date(2026, 10, 22), "Australia/Sydney")

        self.assertEqual([message.text for message in messages], ["local day"])


if __name__ == "__main__":
    unittest.main()
