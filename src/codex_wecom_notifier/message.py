from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any


SUMMARY_MAX_CHARS = 50


def format_notification(
    payload: dict[str, Any], *, include_summary: bool = True, max_chars: int = 3500
) -> str:
    cwd = str(payload.get("cwd") or "未知目录")
    project = Path(cwd).name or cwd
    model = str(payload.get("model") or "未知模型")
    timestamp = _display_time(payload.get("timestamp"))
    session_prompt = _compact(
        payload.get("session_prompt") or "未获取到当前对话提示词。",
        SUMMARY_MAX_CHARS,
    )
    summary = _compact(
        payload.get("last_assistant_message") or "任务已完成。",
        SUMMARY_MAX_CHARS,
    )

    parts = [
        f"# {project}",
        f"> **项目：** {project}",
        f"> **模型：** {model}",
        f"> **时间：** {timestamp}",
        "",
        "**任务内容（50字内）**",
        session_prompt,
    ]
    if include_summary:
        parts.extend(["", "**完成摘要（50字内）**", summary])
    content = "\n".join(parts)
    return truncate(content, max_chars)


def _single_line(value: object) -> str:
    return " ".join(str(value).split())


def _compact(value: object, max_chars: int) -> str:
    text = _single_line(value)
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def truncate(content: str, max_chars: int) -> str:
    if len(content) <= max_chars:
        return content
    marker = "\n\n…（内容过长，已截断；请回到 Codex 查看完整结果）"
    return content[: max_chars - len(marker)].rstrip() + marker


def _display_time(value: object) -> str:
    if value:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return parsed.astimezone().strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")
