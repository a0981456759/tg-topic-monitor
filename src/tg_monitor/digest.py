"""Chinese daily-digest formatting for locally stored matches."""

from collections import defaultdict
from datetime import date
from typing import Sequence
from zoneinfo import ZoneInfo

from .store import StoredMessage


def format_daily_digest(day: date, messages: Sequence[StoredMessage], timezone_name: str = "UTC") -> str:
    """Format a compact Markdown digest suitable for Telegram Saved Messages."""
    heading = f"📌 Telegram 主題摘要｜{day.isoformat()}"
    if not messages:
        return f"{heading}\n\n今天沒有符合追蹤主題的訊息。"

    by_chat: dict[str, list[StoredMessage]] = defaultdict(list)
    for message in messages:
        by_chat[message.chat_id].append(message)

    lines = [heading, f"共 {len(messages)} 則符合追蹤主題的訊息。"]
    local_timezone = ZoneInfo(timezone_name)
    for chat_messages in by_chat.values():
        chat_title = chat_messages[0].chat_title
        lines.extend(["", f"【{chat_title}（{len(chat_messages)} 則）】"])
        for message in chat_messages:
            keywords = "、".join(message.matched_keywords)
            source = f"\n  查看原文：{message.message_link}" if message.message_link else ""
            lines.append(
                f"- {message.sent_at.astimezone(local_timezone).strftime('%H:%M')} · {message.sender_name} · {keywords}\n"
                f"  {message.text}{source}"
            )
    return "\n".join(lines)


def split_for_telegram(text: str, limit: int = 4000) -> list[str]:
    """Split plain text into Telegram-safe chunks without losing characters."""
    if limit < 1:
        raise ValueError("limit must be positive")
    chunks: list[str] = []
    remaining = text
    while len(remaining) > limit:
        breakpoint = remaining.rfind("\n", 0, limit + 1)
        cut = breakpoint + 1 if breakpoint > 0 else limit
        chunks.append(remaining[:cut])
        remaining = remaining[cut:]
    if remaining or not chunks:
        chunks.append(remaining)
    return chunks
