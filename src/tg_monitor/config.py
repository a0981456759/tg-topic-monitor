"""Configuration parsing for the local Telegram monitor."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


class ConfigurationError(ValueError):
    """Raised when required local configuration is absent or invalid."""


def _unique_trimmed_csv(value: str) -> tuple[str, ...]:
    items: list[str] = []
    seen: set[str] = set()
    for raw_item in value.split(","):
        item = raw_item.strip()
        key = item.casefold()
        if item and key not in seen:
            items.append(item)
            seen.add(key)
    return tuple(items)


@dataclass(frozen=True)
class Settings:
    api_id: int
    api_hash: str
    phone: str
    keywords: tuple[str, ...]
    chats: tuple[str, ...]
    timezone: str
    digest_time: str
    notify_chat: str
    slack_webhook_url: str | None

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "Settings":
        required = ("TG_API_ID", "TG_API_HASH", "TG_PHONE", "TG_KEYWORDS")
        missing = [name for name in required if not env.get(name, "").strip()]
        if missing:
            raise ConfigurationError(f"Missing required configuration: {', '.join(missing)}")
        try:
            api_id = int(env["TG_API_ID"])
        except ValueError as error:
            raise ConfigurationError("TG_API_ID must be an integer") from error
        keywords = _unique_trimmed_csv(env["TG_KEYWORDS"])
        if not keywords:
            raise ConfigurationError("TG_KEYWORDS must contain at least one keyword")
        return cls(
            api_id=api_id,
            api_hash=env["TG_API_HASH"].strip(),
            phone=env["TG_PHONE"].strip(),
            keywords=keywords,
            chats=_unique_trimmed_csv(env.get("TG_CHATS", "")),
            timezone=env.get("TG_TIMEZONE", "Asia/Shanghai").strip() or "Asia/Shanghai",
            digest_time=env.get("TG_DIGEST_TIME", "00:05").strip() or "00:05",
            notify_chat=env.get("TG_NOTIFY_CHAT", "me").strip() or "me",
            slack_webhook_url=env.get("SLACK_WEBHOOK_URL", "").strip() or None,
        )
