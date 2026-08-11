from __future__ import annotations

import asyncio
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import Settings
from .sender import send_payload


async def handle(raw: str) -> None:
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("Hook 输入必须是 JSON 对象")
    if payload.get("hook_event_name") not in {None, "Stop"}:
        return
    session_context = _load_session_context(payload)
    payload["session_prompt"] = str(
        payload.get("session_prompt")
        or session_context.get("session_prompt")
        or payload.get("prompt")
        or "未获取到当前对话提示词。"
    )
    if not payload.get("model") and session_context.get("model"):
        payload["model"] = session_context["model"]
    payload["timestamp"] = datetime.now(timezone.utc).isoformat()
    await send_payload(Settings.load(), payload)


def _load_session_context(payload: dict[str, Any]) -> dict[str, str]:
    transcript = _find_transcript(payload)
    if transcript is None:
        return {}

    context: dict[str, str] = {}
    try:
        with transcript.open(encoding="utf-8") as handle:
            for line in handle:
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                _collect_session_context(entry, context)
    except OSError:
        return {}
    return context


def _find_transcript(payload: dict[str, Any]) -> Path | None:
    configured = payload.get("transcript_path")
    if configured:
        path = Path(str(configured)).expanduser()
        if path.is_file():
            return path

    session_id = str(payload.get("session_id") or "").strip()
    if not session_id or not all(char.isalnum() or char in "-_" for char in session_id):
        return None
    sessions = Path.home() / ".codex" / "sessions"
    try:
        matches = list(sessions.glob(f"*/*/*/rollout-*{session_id}.jsonl"))
        return max(matches, key=lambda path: path.stat().st_mtime) if matches else None
    except OSError:
        return None


def _collect_session_context(entry: object, context: dict[str, str]) -> None:
    if not isinstance(entry, dict):
        return
    payload = entry.get("payload")
    if not isinstance(payload, dict):
        return

    if entry.get("type") == "turn_context":
        model = str(payload.get("model") or "").strip()
        if model:
            context["model"] = model

    if (
        entry.get("type") == "response_item"
        and payload.get("type") == "message"
        and payload.get("role") == "user"
    ):
        content = payload.get("content")
        if not isinstance(content, list):
            return
        text = "\n".join(
            str(item.get("text") or "")
            for item in content
            if isinstance(item, dict) and item.get("type") == "input_text"
        )
        prompt = _without_environment_context(text)
        if prompt:
            context["session_prompt"] = prompt


def _without_environment_context(text: str) -> str:
    remaining = text.strip()
    while remaining.startswith("<environment_context>"):
        stripped = re.sub(
            r"\A<environment_context>.*?</environment_context>\s*",
            "",
            remaining,
            count=1,
            flags=re.DOTALL,
        )
        if stripped == remaining:
            break
        remaining = stripped.strip()
    return remaining


def main() -> int:
    try:
        asyncio.run(handle(sys.stdin.read()))
    except Exception as exc:
        # Notification failures must never fail or continue the Codex turn.
        print(f"codex-wecom-hook: {exc}", file=sys.stderr)
    # Stop hooks require valid JSON on stdout when exiting successfully.
    print("{}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
