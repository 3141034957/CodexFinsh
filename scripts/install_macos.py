#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import os
import shlex
import sys
import tempfile
from pathlib import Path
from typing import Any

from aibot import WSClient, WSClientOptions


APP_NAME = "codex-wecom-notifier"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="安装 Codex → 企业微信任务完成通知（macOS）"
    )
    parser.add_argument("--bot-id", required=True, help="企业微信智能机器人 Bot ID")
    parser.add_argument(
        "--target-id",
        help="接收通知的企业微信 userid 或群聊 chatid；省略时会引导自动获取",
    )
    parser.add_argument(
        "--no-summary", action="store_true", help="通知中不包含 Codex 最后一条回复"
    )
    return parser.parse_args()


def atomic_private_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    fd, temporary_name = tempfile.mkstemp(prefix=".config-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.chmod(temporary_name, 0o600)
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def install_hook(python: Path) -> Path:
    hooks_path = Path.home() / ".codex" / "hooks.json"
    hooks_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if hooks_path.exists():
        with hooks_path.open(encoding="utf-8") as handle:
            document = json.load(handle)
        if not isinstance(document, dict):
            raise ValueError(f"现有 Hook 配置不是 JSON 对象：{hooks_path}")
    else:
        document = {"description": "User-level Codex lifecycle hooks."}

    hooks = document.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError(f"现有 hooks 字段不是 JSON 对象：{hooks_path}")
    stop_groups = hooks.setdefault("Stop", [])
    if not isinstance(stop_groups, list):
        raise ValueError(f"现有 hooks.Stop 字段不是数组：{hooks_path}")

    module_marker = "codex_wecom_notifier.hook"
    stop_groups[:] = [
        group
        for group in stop_groups
        if module_marker not in json.dumps(group, ensure_ascii=False)
    ]
    command = f"{shlex.quote(str(python))} -m {module_marker}"
    stop_groups.append(
        {
            "hooks": [
                {
                    "type": "command",
                    "command": command,
                    "timeout": 35,
                    "statusMessage": "正在发送企业微信完成通知",
                }
            ]
        }
    )
    atomic_private_json(hooks_path, document)
    return hooks_path


async def discover_target(bot_id: str, secret: str) -> str:
    authenticated = asyncio.Event()
    loop = asyncio.get_running_loop()
    discovered: asyncio.Future[str] = loop.create_future()
    client = WSClient(
        WSClientOptions(
            bot_id=bot_id,
            secret=secret,
            max_reconnect_attempts=0,
        )
    )

    @client.on("authenticated")
    def on_authenticated() -> None:
        authenticated.set()

    @client.on("message.text")
    def on_message(frame: dict[str, Any]) -> None:
        body = frame.get("body", {})
        chat_id = body.get("chatid")
        user_id = body.get("from", {}).get("userid")
        target = chat_id or user_id
        if target and not discovered.done():
            discovered.set_result(str(target))

    try:
        await asyncio.wait_for(client.connect(), timeout=10)
        await asyncio.wait_for(authenticated.wait(), timeout=10)
        print("连接成功。请在 120 秒内私聊机器人发送任意文本；若在群里 @机器人，将保存该群 chatid。")
        return await asyncio.wait_for(discovered, timeout=120)
    finally:
        client.disconnect()


def main() -> int:
    if sys.platform != "darwin":
        print("此安装器仅支持 macOS。其他系统请按 README 手动启动服务。", file=sys.stderr)
        return 2
    args = parse_args()
    secret = os.environ.get("WECOM_BOT_SECRET") or getpass.getpass(
        "企业微信机器人 Secret（输入不会回显）："
    )
    if not secret.strip():
        print("Secret 不能为空。", file=sys.stderr)
        return 2

    target_id = (args.target_id or "").strip()
    if not target_id:
        try:
            target_id = asyncio.run(discover_target(args.bot_id.strip(), secret.strip()))
        except Exception as exc:
            print(f"自动获取接收目标失败：{exc}", file=sys.stderr)
            return 1
        print(f"已从刚才的消息获取接收目标：{target_id}")

    # Keep the virtual-environment path; resolving the symlink can select a
    # base interpreter that cannot import this installed package.
    python = Path(sys.executable).absolute()
    config_path = Path.home() / ".config" / APP_NAME / "config.json"
    atomic_private_json(
        config_path,
        {
            "bot_id": args.bot_id.strip(),
            "bot_secret": secret.strip(),
            "target_id": target_id,
            "include_summary": not args.no_summary,
            "max_message_chars": 3500,
        },
    )
    hooks_path = install_hook(python)

    print(f"配置已写入：{config_path}（权限 0600）")
    print(f"Codex Hook 已写入：{hooks_path}")
    print("没有安装后台服务。请重启 Codex，然后用 /hooks 审核并信任新 Hook。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
