from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


APP_DIR_NAME = "codex-wecom-notifier"


def default_config_path() -> Path:
    configured = os.environ.get("CODEX_WECOM_CONFIG")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".config" / APP_DIR_NAME / "config.json"


@dataclass(frozen=True)
class Settings:
    bot_id: str
    bot_secret: str
    target_id: str
    ws_url: str | None = None
    max_message_chars: int = 3500
    include_summary: bool = True

    @classmethod
    def load(cls, path: Path | None = None) -> "Settings":
        config_path = path or default_config_path()
        data: dict[str, Any] = {}
        if config_path.exists():
            _require_private_file(config_path)
            with config_path.open(encoding="utf-8") as handle:
                loaded = json.load(handle)
            if not isinstance(loaded, dict):
                raise ValueError(f"配置文件必须是 JSON 对象：{config_path}")
            data.update(loaded)

        env = os.environ
        _apply_env(data, env)
        missing = [
            key
            for key in ("bot_id", "bot_secret", "target_id")
            if not str(data.get(key, "")).strip()
        ]
        if missing:
            names = ", ".join(missing)
            raise ValueError(f"缺少必要配置：{names}（配置文件：{config_path}）")

        max_chars = int(data.get("max_message_chars", 3500))
        if max_chars < 200:
            raise ValueError("max_message_chars 不能小于 200")

        return cls(
            bot_id=str(data["bot_id"]).strip(),
            bot_secret=str(data["bot_secret"]).strip(),
            target_id=str(data["target_id"]).strip(),
            ws_url=_optional_text(data.get("ws_url")),
            max_message_chars=max_chars,
            include_summary=_as_bool(data.get("include_summary", True)),
        )


def _apply_env(data: dict[str, Any], env: Mapping[str, str]) -> None:
    mapping = {
        "WECOM_BOT_ID": "bot_id",
        "WECOM_BOT_SECRET": "bot_secret",
        "WECOM_TARGET_ID": "target_id",
        "WECOM_WS_URL": "ws_url",
        "CODEX_WECOM_MAX_MESSAGE_CHARS": "max_message_chars",
        "CODEX_WECOM_INCLUDE_SUMMARY": "include_summary",
    }
    for env_name, key in mapping.items():
        if env_name in env:
            data[key] = env[env_name]


def _require_private_file(path: Path) -> None:
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        raise PermissionError(
            f"配置文件权限过宽（当前 {mode:o}）：{path}。请执行 chmod 600。"
        )


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"无法识别布尔值：{value!r}")


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
