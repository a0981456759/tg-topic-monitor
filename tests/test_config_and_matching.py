import unittest

from tg_monitor.config import ConfigurationError, Settings
from tg_monitor.matching import find_matches


class SettingsTests(unittest.TestCase):
    def test_reads_required_credentials_and_normalizes_keywords(self) -> None:
        settings = Settings.from_env(
            {
                "TG_API_ID": "12345",
                "TG_API_HASH": "secret-hash",
                "TG_PHONE": "+61400000000",
                "TG_KEYWORDS": " AI Agent, 投資 ,ai agent,  ",
                "TG_CHATS": "-1001, -1002",
                "TG_TIMEZONE": "Australia/Sydney",
            }
        )

        self.assertEqual(settings.api_id, 12345)
        self.assertEqual(settings.keywords, ("AI Agent", "投資"))
        self.assertEqual(settings.chats, ("-1001", "-1002"))
        self.assertEqual(settings.timezone, "Australia/Sydney")

    def test_rejects_missing_required_credentials(self) -> None:
        with self.assertRaises(ConfigurationError):
            Settings.from_env({"TG_API_ID": "12345", "TG_KEYWORDS": "AI"})

    def test_defaults_shared_setup_to_beijing_time(self) -> None:
        settings = Settings.from_env(
            {"TG_API_ID": "12345", "TG_API_HASH": "secret-hash", "TG_PHONE": "+8613800000000", "TG_KEYWORDS": "AI"}
        )

        self.assertEqual(settings.timezone, "Asia/Shanghai")

    def test_reads_optional_telegram_and_slack_notification_destinations(self) -> None:
        settings = Settings.from_env(
            {
                "TG_API_ID": "12345", "TG_API_HASH": "secret-hash", "TG_PHONE": "+8613800000000",
                "TG_KEYWORDS": "AI", "TG_NOTIFY_CHAT": "@topic_alerts",
                "SLACK_WEBHOOK_URL": "https://hooks.slack.com/services/a/b/c",
            }
        )

        self.assertEqual(settings.notify_chat, "@topic_alerts")
        self.assertEqual(settings.slack_webhook_url, "https://hooks.slack.com/services/a/b/c")


class MatchingTests(unittest.TestCase):
    def test_returns_every_distinct_case_insensitive_keyword_once(self) -> None:
        self.assertEqual(
            find_matches("今天 AI agent 會影響投資；ai AGENT 也被提到。", ("AI Agent", "投資")),
            ("AI Agent", "投資"),
        )

    def test_ignores_empty_keywords_instead_of_matching_every_message(self) -> None:
        self.assertEqual(find_matches("一般聊天", ("", "   ")), ())


if __name__ == "__main__":
    unittest.main()
