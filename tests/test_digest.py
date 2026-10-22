import unittest
from datetime import date, datetime, timezone

from tg_monitor.digest import format_daily_digest, split_for_telegram
from tg_monitor.store import StoredMessage


class DailyDigestTests(unittest.TestCase):
    def test_empty_day_explains_that_no_topics_matched(self) -> None:
        digest = format_daily_digest(date(2026, 10, 22), [])

        self.assertIn("2026-10-22", digest)
        self.assertIn("沒有符合追蹤主題的訊息", digest)

    def test_groups_messages_by_chat_and_includes_available_source_link(self) -> None:
        messages = [
            StoredMessage(
                chat_id="-1001", message_id=5, chat_title="AI 社群", sender_name="Ada",
                text="Agent 的新框架今天發布", matched_keywords=("Agent",),
                sent_at=datetime(2026, 10, 22, 9, 5, tzinfo=timezone.utc),
                message_link="https://t.me/c/1/5",
            ),
            StoredMessage(
                chat_id="-1001", message_id=6, chat_title="AI 社群", sender_name="Ben",
                text="我會看這個 Agent 範例", matched_keywords=("Agent",),
                sent_at=datetime(2026, 10, 22, 9, 8, tzinfo=timezone.utc),
                message_link=None,
            ),
        ]

        digest = format_daily_digest(date(2026, 10, 22), messages)

        self.assertIn("AI 社群（2 則）", digest)
        self.assertIn("Agent", digest)
        self.assertIn("https://t.me/c/1/5", digest)
        self.assertIn("Ada", digest)

    def test_splits_oversized_messages_without_losing_content(self) -> None:
        text = "甲" * 8001

        chunks = split_for_telegram(text, limit=4000)

        self.assertEqual("".join(chunks), text)
        self.assertTrue(all(len(chunk) <= 4000 for chunk in chunks))


if __name__ == "__main__":
    unittest.main()
