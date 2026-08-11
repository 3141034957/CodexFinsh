from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aibot import WSClient, WSClientOptions

from .config import Settings
from .message import format_notification


LOGGER = logging.getLogger("codex-wecom-notifier")


async def send_payload(settings: Settings, payload: dict[str, Any]) -> None:
    authenticated = asyncio.Event()
    options: dict[str, Any] = {
        "bot_id": settings.bot_id,
        "secret": settings.bot_secret,
        # This process sends one notification and exits; it is not a daemon.
        "max_reconnect_attempts": 0,
    }
    if settings.ws_url:
        options["ws_url"] = settings.ws_url
    client = WSClient(WSClientOptions(**options))

    @client.on("authenticated")
    def on_authenticated() -> None:
        authenticated.set()

    try:
        await asyncio.wait_for(client.connect(), timeout=10)
        await asyncio.wait_for(authenticated.wait(), timeout=10)
        content = format_notification(
            payload,
            include_summary=settings.include_summary,
            max_chars=settings.max_message_chars,
        )
        await asyncio.wait_for(
            client.send_message(
                settings.target_id,
                {"msgtype": "markdown", "markdown": {"content": content}},
            ),
            timeout=10,
        )
    finally:
        client.disconnect()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="发送一次 Codex 企业微信完成通知")
    parser.add_argument("message", nargs="?", default="这是一条连通性测试。")
    parser.add_argument("--cwd", default=str(Path.cwd()))
    parser.add_argument("--model", default="manual-test")
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = parse_args()
    payload = {
        "cwd": args.cwd,
        "model": args.model,
        "last_assistant_message": args.message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    try:
        asyncio.run(send_payload(Settings.load(), payload))
    except Exception as exc:
        LOGGER.error("发送失败：%s", exc)
        return 1
    LOGGER.info("通知已发送")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
