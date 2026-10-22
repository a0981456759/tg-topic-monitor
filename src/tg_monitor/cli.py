"""Command line interface for the local Telegram topic monitor."""

from __future__ import annotations

import argparse
import asyncio
import os
from datetime import date, datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import Settings
from .digest import format_daily_digest
from .store import MessageStore
from .telegram_client import TelegramMonitor


def load_env(path: Path) -> dict[str, str]:
    """Load simple KEY=VALUE entries without echoing private values."""
    values = dict(os.environ)
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Private MTProto Telegram topic monitor")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--session", type=Path, default=Path("session/telegram"))
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("login", help="Log in and create a local Telegram session")
    scan = subparsers.add_parser("scan-history", help="Scan matching messages since a UTC date")
    scan.add_argument("--since", required=True, type=date.fromisoformat, help="YYYY-MM-DD")
    subparsers.add_parser("monitor", help="Keep monitoring new messages until stopped")
    digest = subparsers.add_parser("digest", help="Send the selected day's digest to configured destinations")
    digest.add_argument("--date", type=date.fromisoformat, help="YYYY-MM-DD")
    return parser


async def run(arguments: argparse.Namespace) -> None:
    settings = Settings.from_env(load_env(arguments.env_file))
    store = MessageStore(arguments.data_dir / "messages.sqlite3")
    monitor = TelegramMonitor(settings, store, arguments.session)
    try:
        await monitor.connect()
        if arguments.command == "login":
            print("登入成功；session 檔案已留在本機。")
        elif arguments.command == "scan-history":
            since = datetime.combine(arguments.since, time.min, tzinfo=timezone.utc)
            recorded = await monitor.scan_history(since)
            print(f"完成掃描，新增 {recorded} 則命中訊息。")
        elif arguments.command == "monitor":
            print("開始監控；按 Ctrl+C 停止。")
            await monitor.monitor_forever()
        elif arguments.command == "digest":
            digest_day = arguments.date or date.today(ZoneInfo(settings.timezone))
            digest = format_daily_digest(
                digest_day, store.messages_for_local_day(digest_day, settings.timezone), settings.timezone
            )
            await monitor.send_notifications(digest)
            print("每日摘要已送到設定的通知目的地。")
    finally:
        await monitor.disconnect()
        store.close()


def main() -> None:
    arguments = create_parser().parse_args()
    asyncio.run(run(arguments))


if __name__ == "__main__":
    main()
