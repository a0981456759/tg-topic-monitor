"""Local SQLite storage for topic-matched Telegram messages."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class StoredMessage:
    chat_id: str
    message_id: int
    chat_title: str
    sender_name: str
    text: str
    matched_keywords: tuple[str, ...]
    sent_at: datetime
    message_link: str | None


class MessageStore:
    """Persist unique matched messages in a local SQLite database."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(path)
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                chat_id TEXT NOT NULL,
                message_id INTEGER NOT NULL,
                chat_title TEXT NOT NULL,
                sender_name TEXT NOT NULL,
                text TEXT NOT NULL,
                matched_keywords TEXT NOT NULL,
                sent_at TEXT NOT NULL,
                message_link TEXT,
                alert_pending INTEGER NOT NULL DEFAULT 0,
                telegram_pending INTEGER NOT NULL DEFAULT 0,
                slack_pending INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (chat_id, message_id)
            )
            """
        )
        columns = {row[1] for row in self._connection.execute("PRAGMA table_info(messages)")}
        if "alert_pending" not in columns:
            self._connection.execute("ALTER TABLE messages ADD COLUMN alert_pending INTEGER NOT NULL DEFAULT 0")
        if "telegram_pending" not in columns:
            self._connection.execute("ALTER TABLE messages ADD COLUMN telegram_pending INTEGER NOT NULL DEFAULT 0")
            self._connection.execute("UPDATE messages SET telegram_pending = alert_pending WHERE alert_pending = 1")
        if "slack_pending" not in columns:
            self._connection.execute("ALTER TABLE messages ADD COLUMN slack_pending INTEGER NOT NULL DEFAULT 0")
        self._connection.commit()

    def close(self) -> None:
        self._connection.close()

    def record(
        self, message: StoredMessage, queue_alert: bool = False, queue_telegram: bool = False, queue_slack: bool = False
    ) -> bool:
        cursor = self._connection.execute(
            """
            INSERT OR IGNORE INTO messages
            (chat_id, message_id, chat_title, sender_name, text, matched_keywords, sent_at, message_link,
             alert_pending, telegram_pending, slack_pending)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                message.chat_id,
                message.message_id,
                message.chat_title,
                message.sender_name,
                message.text,
                json.dumps(message.matched_keywords, ensure_ascii=False),
                message.sent_at.isoformat(),
                message.message_link,
                int(queue_alert),
                int(queue_alert or queue_telegram),
                int(queue_slack),
            ),
        )
        self._connection.commit()
        return cursor.rowcount == 1

    def pending_alerts(self) -> list[StoredMessage]:
        return self.pending_telegram_alerts()

    def pending_telegram_alerts(self) -> list[StoredMessage]:
        return self._messages_where("telegram_pending = 1", ())

    def pending_slack_alerts(self) -> list[StoredMessage]:
        return self._messages_where("slack_pending = 1", ())

    def alert_is_pending(self, chat_id: str, message_id: int) -> bool:
        return self.telegram_is_pending(chat_id, message_id)

    def telegram_is_pending(self, chat_id: str, message_id: int) -> bool:
        row = self._connection.execute(
            "SELECT telegram_pending FROM messages WHERE chat_id = ? AND message_id = ?", (chat_id, message_id)
        ).fetchone()
        return bool(row and row[0])

    def slack_is_pending(self, chat_id: str, message_id: int) -> bool:
        row = self._connection.execute(
            "SELECT slack_pending FROM messages WHERE chat_id = ? AND message_id = ?", (chat_id, message_id)
        ).fetchone()
        return bool(row and row[0])

    def mark_alert_sent(self, chat_id: str, message_id: int) -> None:
        self.mark_telegram_sent(chat_id, message_id)

    def mark_telegram_sent(self, chat_id: str, message_id: int) -> None:
        self._connection.execute(
            "UPDATE messages SET alert_pending = 0, telegram_pending = 0 WHERE chat_id = ? AND message_id = ?",
            (chat_id, message_id),
        )
        self._connection.commit()

    def mark_slack_sent(self, chat_id: str, message_id: int) -> None:
        self._connection.execute(
            "UPDATE messages SET slack_pending = 0 WHERE chat_id = ? AND message_id = ?", (chat_id, message_id)
        )
        self._connection.commit()

    def messages_for_day(self, day: date) -> list[StoredMessage]:
        return self.messages_for_local_day(day, "UTC")

    def messages_for_local_day(self, day: date, timezone_name: str) -> list[StoredMessage]:
        local_timezone = ZoneInfo(timezone_name)
        start = datetime.combine(day, time.min, tzinfo=local_timezone).astimezone(timezone.utc)
        end = datetime.combine(day.fromordinal(day.toordinal() + 1), time.min, tzinfo=local_timezone).astimezone(timezone.utc)
        return self._messages_where("sent_at >= ? AND sent_at < ?", (start.isoformat(), end.isoformat()))

    def _messages_where(self, condition: str, parameters: tuple[object, ...]) -> list[StoredMessage]:
        rows = self._connection.execute(
            """
            SELECT chat_id, message_id, chat_title, sender_name, text, matched_keywords, sent_at, message_link
            FROM messages
            WHERE """ + condition + """
            ORDER BY sent_at ASC, chat_id ASC, message_id ASC
            """,
            parameters,
        ).fetchall()
        return [
            StoredMessage(
                chat_id=row[0],
                message_id=row[1],
                chat_title=row[2],
                sender_name=row[3],
                text=row[4],
                matched_keywords=tuple(json.loads(row[5])),
                sent_at=datetime.fromisoformat(row[6]),
                message_link=row[7],
            )
            for row in rows
        ]
