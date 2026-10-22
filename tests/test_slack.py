import json
import unittest

from tg_monitor.slack import slack_payload


class SlackPayloadTests(unittest.TestCase):
    def test_encodes_plain_unicode_message_as_slack_text(self) -> None:
        payload = json.loads(slack_payload("🔔 AI 討論命中").decode("utf-8"))

        self.assertEqual(payload, {"text": "🔔 AI 討論命中"})


if __name__ == "__main__":
    unittest.main()
