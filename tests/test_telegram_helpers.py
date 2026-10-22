import unittest

from tg_monitor.telegram_client import build_message_link, chat_is_allowed


class TelegramHelperTests(unittest.TestCase):
    def test_builds_public_and_private_channel_links(self) -> None:
        self.assertEqual(build_message_link("public_group", 77, None), "https://t.me/public_group/77")
        self.assertEqual(build_message_link(None, 77, 123456), "https://t.me/c/123456/77")

    def test_returns_no_link_for_basic_group_messages(self) -> None:
        self.assertIsNone(build_message_link(None, 77, None))

    def test_chat_allowlist_accepts_username_or_telegram_peer_id(self) -> None:
        self.assertTrue(chat_is_allowed(("@my_group",), -100123, "my_group"))
        self.assertTrue(chat_is_allowed(("-100123",), -100123, None))
        self.assertFalse(chat_is_allowed(("@my_group",), -100123, "other_group"))


if __name__ == "__main__":
    unittest.main()
