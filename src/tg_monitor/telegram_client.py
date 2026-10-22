"""Telethon adapter for a user's own Telegram account."""

from __future__ import annotations

import asyncio
import contextlib
import os
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .config import Settings
from .digest import format_daily_digest, split_for_telegram
from .matching import find_matches
from .slack import post_webhook
from .store import MessageStore, StoredMessage


def build_message_link(username: str | None, message_id: int, private_channel_id: int | None) -> str | None:
    """Return a Telegram source URL when the chat type supports one."""
    if username:
        return f"https://t.me/{username.lstrip('@')}/{message_id}"
    if private_channel_id:
        return f"https://t.me/c/{private_channel_id}/{message_id}"
    return None


def chat_is_allowed(allowed_chats: tuple[str, ...], peer_id: int, username: str | None) -> bool:
    """Allow every group when unconfigured, otherwise match ID or username."""
    if not allowed_chats:
        return True
    candidates = {str(peer_id).casefold()}
    if username:
        candidates.add(username.lstrip("@").casefold())
        candidates.add(f"@{username.lstrip('@').casefold()}")
    return any(chat.casefold() in candidates for chat in allowed_chats)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class TelegramMonitor:
    """Read the authenticated account's ordinary group messages using Telethon."""

    def __init__(self, settings: Settings, store: MessageStore, session_path: Path) -> None:
        self._settings = settings
        self._store = store
        self._session_path = session_path
        self._client: Any | None = None
        self._session_lock: _SessionLock | None = None

    async def connect(self) -> None:
        try:
            from telethon import TelegramClient
        except ImportError as error:
            raise RuntimeError("Telethon is not installed. Run: pip install -r requirements.txt") from error
        self._session_path.parent.mkdir(parents=True, exist_ok=True)
        self._session_lock = _SessionLock(self._session_path.with_suffix(".lock"))
        self._session_lock.acquire()
        self._client = TelegramClient(str(self._session_path), self._settings.api_id, self._settings.api_hash)
        try:
            await self._client.start(phone=self._settings.phone)
        except BaseException:
            self._session_lock.release()
            self._session_lock = None
            raise

    async def disconnect(self) -> None:
        if self._client is not None:
            await self._client.disconnect()
        if self._session_lock is not None:
            self._session_lock.release()
            self._session_lock = None

    async def scan_history(self, since: datetime) -> int:
        """Record matching history on or after `since`; existing rows are skipped."""
        client = self._require_client()
        from telethon import utils

        recorded = 0
        async for dialog in client.iter_dialogs():
            if not (dialog.is_group or dialog.is_channel):
                continue
            peer_id = utils.get_peer_id(dialog.entity)
            username = getattr(dialog.entity, "username", None)
            if not chat_is_allowed(self._settings.chats, peer_id, username):
                continue
            async for message in client.iter_messages(dialog.entity):
                if _as_utc(message.date) < since:
                    break
                if await self._process_message(message, dialog.entity, peer_id, notify=False):
                    recorded += 1
        return recorded

    async def monitor_forever(self) -> None:
        """Watch new messages until interrupted."""
        client = self._require_client()
        from telethon import events, utils

        await self.retry_pending_alerts()

        @client.on(events.NewMessage)
        async def on_message(event: Any) -> None:
            chat = await event.get_chat()
            if not _is_group_or_channel(chat):
                return
            peer_id = utils.get_peer_id(chat)
            if not chat_is_allowed(self._settings.chats, peer_id, getattr(chat, "username", None)):
                return
            await self._process_message(event.message, chat, peer_id, notify=True)

        daily_task = asyncio.create_task(self._daily_digest_loop())
        try:
            await client.run_until_disconnected()
        finally:
            daily_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await daily_task

    async def send_telegram_message(self, text: str) -> None:
        for chunk in split_for_telegram(text):
            await self._require_client().send_message(
                self._settings.notify_chat, chunk, link_preview=False, parse_mode=None
            )

    async def send_notifications(self, text: str) -> None:
        await self.send_telegram_message(text)
        if self._settings.slack_webhook_url:
            for chunk in split_for_telegram(text):
                await post_webhook(self._settings.slack_webhook_url, chunk)

    async def retry_pending_alerts(self) -> None:
        for message in self._store.pending_telegram_alerts():
            await self.send_telegram_message(self._alert_text(message))
            self._store.mark_telegram_sent(message.chat_id, message.message_id)
        if self._settings.slack_webhook_url:
            for message in self._store.pending_slack_alerts():
                await post_webhook(self._settings.slack_webhook_url, self._alert_text(message))
                self._store.mark_slack_sent(message.chat_id, message.message_id)

    async def _process_message(self, message: Any, chat: Any, peer_id: int, notify: bool) -> bool:
        text = message.raw_text or ""
        matches = find_matches(text, self._settings.keywords)
        if not matches:
            return False
        sender = await message.get_sender()
        sender_name = _display_name(sender)
        chat_title = getattr(chat, "title", None) or getattr(chat, "username", None) or str(peer_id)
        private_channel_id = getattr(chat, "id", None) if _is_channel_or_supergroup(chat) else None
        stored = StoredMessage(
            chat_id=str(peer_id),
            message_id=message.id,
            chat_title=chat_title,
            sender_name=sender_name,
            text=text,
            matched_keywords=matches,
            sent_at=_as_utc(message.date),
            message_link=build_message_link(getattr(chat, "username", None), message.id, private_channel_id),
        )
        is_new = self._store.record(
            stored, queue_telegram=notify, queue_slack=notify and bool(self._settings.slack_webhook_url)
        )
        if notify and self._store.telegram_is_pending(stored.chat_id, stored.message_id):
            await self.send_telegram_message(self._alert_text(stored))
            self._store.mark_telegram_sent(stored.chat_id, stored.message_id)
        if notify and self._settings.slack_webhook_url and self._store.slack_is_pending(stored.chat_id, stored.message_id):
            await post_webhook(self._settings.slack_webhook_url, self._alert_text(stored))
            self._store.mark_slack_sent(stored.chat_id, stored.message_id)
        return is_new

    def _alert_text(self, stored: StoredMessage) -> str:
        source = f"\n{stored.message_link}" if stored.message_link else ""
        preview = stored.text[:1200] + ("…" if len(stored.text) > 1200 else "")
        return (
            f"🔔 主題命中｜{stored.chat_title}\n關鍵字：{'、'.join(stored.matched_keywords)}\n"
            f"{stored.sender_name}: {preview}{source}"
        )

    async def _daily_digest_loop(self) -> None:
        reporting_timezone = ZoneInfo(self._settings.timezone)
        target_time = time.fromisoformat(self._settings.digest_time)
        while True:
            now = datetime.now(reporting_timezone)
            target = datetime.combine(now.date(), target_time, tzinfo=reporting_timezone)
            if target <= now:
                target += timedelta(days=1)
            await asyncio.sleep((target - now).total_seconds())
            report_day = (datetime.now(reporting_timezone) - timedelta(days=1)).date()
            messages = self._store.messages_for_local_day(report_day, self._settings.timezone)
            await self.send_notifications(format_daily_digest(report_day, messages, self._settings.timezone))

    def _require_client(self) -> Any:
        if self._client is None:
            raise RuntimeError("Telegram client is not connected")
        return self._client


def _is_group_or_channel(chat: Any) -> bool:
    return chat.__class__.__name__ == "Chat" or _is_channel_or_supergroup(chat)


def _is_channel_or_supergroup(chat: Any) -> bool:
    return bool(getattr(chat, "megagroup", False) or getattr(chat, "broadcast", False))


def _display_name(sender: Any) -> str:
    if sender is None:
        return "未知發言者"
    name = " ".join(part for part in (getattr(sender, "first_name", None), getattr(sender, "last_name", None)) if part)
    return name or getattr(sender, "username", None) or "未知發言者"


class _SessionLock:
    """Exclusive process lock so Task Scheduler cannot share a Telethon session."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._handle: Any | None = None

    def acquire(self) -> None:
        self._handle = open(self._path, "a+b")
        self._handle.seek(0)
        self._handle.write(b"0")
        self._handle.flush()
        self._handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self._handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            self._handle.close()
            self._handle = None
            raise RuntimeError("Telegram session is already in use; stop the monitor before running another command.") from error

    def release(self) -> None:
        if self._handle is None:
            return
        self._handle.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        self._handle.close()
        self._handle = None
