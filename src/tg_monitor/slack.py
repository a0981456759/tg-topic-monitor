"""Minimal Slack Incoming Webhook delivery without a Slack account session."""

from __future__ import annotations

import asyncio
import json
from urllib.request import Request, urlopen


def slack_payload(text: str) -> bytes:
    return json.dumps({"text": text}, ensure_ascii=False).encode("utf-8")


async def post_webhook(webhook_url: str, text: str) -> None:
    await asyncio.to_thread(_post, webhook_url, text)


def _post(webhook_url: str, text: str) -> None:
    request = Request(
        webhook_url,
        data=slack_payload(text),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urlopen(request, timeout=15) as response:
        if not 200 <= response.status < 300:
            raise RuntimeError(f"Slack webhook failed with HTTP {response.status}")
