# Codex 完成任务后通过企业微信通知

Codex 每次完成主线程任务时，`Stop` Hook 临时连接企业微信智能机器人 WebSocket，完成鉴权并主动推送一条 Markdown 消息，然后立即断开。

```text
Codex 完成任务
      │ Stop Hook
      ▼
临时连接 → aibot_subscribe → aibot_send_msg → 断开
                                      │
                                      ▼
                               企业微信用户/群聊
```

没有常驻服务、心跳进程或开机启动项。一次通知通常只会让 Codex 的任务结束阶段多等待数秒；网络或企业微信不可用时，本次通知会失败，但不会改变 Codex 的任务结果。

## 这和 `response_url` 有什么区别

"接收消息"文档中的 `response_url` 只会在用户先向机器人发消息后出现，适合对该消息进行临时回复。Codex 独立完成任务时没有对应的用户消息，因此本工具使用长连接协议中的 `aibot_send_msg` 主动推送。连接只在发送期间存在。

## 系统要求

> **当前仅支持 macOS。** Windows / Linux 用户暂时无法使用安装器，欢迎贡献对应平台的安装脚本。

| 要求 | 说明 |
|------|------|
| 操作系统 | macOS |
| Python | 3.10+ |
| 包管理器 | [uv](https://docs.astral.sh/uv/getting-started/installation/)（推荐）或 pip |
| 企业微信 | 管理员权限，用于创建智能机器人 |

### 安装 uv（如未安装）

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

安装完成后重启终端，或执行 `source $HOME/.cargo/env`。验证：

```bash
uv --version
```

### 使用 pip 代替 uv

如果无法使用 uv，可以用 pip 安装依赖后直接运行模块：

```bash
pip install "wecom-aibot-python-sdk>=1.0.1,<2"
```

手动安装方式不会自动注册 hook，需要参照下方的「手动配置 hook」章节自行编辑 `~/.codex/hooks.json`。

## 安装

### 步骤 1：创建企业微信智能机器人

在企业微信管理后台，进入「应用管理 → 智能机器人 → API 模式 → 长连接」，创建机器人。记录以下信息：

- **Bot ID**：机器人的唯一标识
- **Secret**：机器人的鉴权密钥

### 步骤 2：运行安装器

**方法 A：自动获取接收目标（推荐）**

如果不知道自己的 userid 或群 chatid，安装器可以自动获取：

```bash
uv sync
uv run python scripts/install_macos.py --bot-id '你的 Bot ID'
```

安装器会通过隐藏输入读取 Secret（不会写入 shell 历史），随后临时建立 WebSocket 连接。此时你需要在 120 秒内：

- **发送给个人**：私聊机器人发任意文本
- **发送到群**：在目标群里 @机器人发任意文本

安装器从消息中提取 `from.userid` 或 `chatid` 作为通知接收目标。

**方法 B：直接指定接收目标**

如果已经知道目标：

```bash
uv run python scripts/install_macos.py \
  --bot-id '你的 Bot ID' \
  --target-id '你的 userid 或 chatid'
```

也可以通过环境变量传入 Secret，避免交互输入：

```bash
export WECOM_BOT_SECRET='你的 Secret'
uv run python scripts/install_macos.py --bot-id '你的 Bot ID' --target-id '你的 userid'
```

### 步骤 3：安装后检查

安装器完成后，会输出写入的文件路径：

```
配置已写入：~/.config/codex-wecom-notifier/config.json（权限 0600）
Codex Hook 已写入：~/.codex/hooks.json
```

确认两处文件均已生成。

### 步骤 4：在 Codex 中启用 Hook

1. **重启 Codex**
2. 在 Codex 对话框中输入 `/hooks`
3. 在弹出面板中找到 `codex_wecom_notifier.hook`，审核内容后点击**信任**
4. Hook 状态应变为绿色/已启用

> 安装器只会替换 `hooks.json` 中本工具的旧条目，不会影响已有的其他 Hook。

### 步骤 5：手动验证

```bash
uv run codex-wecom-send '这是一条连通性测试。'
```

命令会建立一次连接、发送消息、断开；成功时输出：

```
通知已发送
```

你应该在企业微信中收到来自机器人的测试消息。如果失败，检查：

- Bot ID / Secret 是否正确
- target_id 是否为有效的 userid 或 chatid
- 机器人是否已在企业微信后台启用
- 网络是否能访问企业微信 WebSocket 地址

至此安装完成。之后每次 Codex 完成主线程任务，你都会在企业微信收到通知。

---

## 手动配置 hook（不使用安装器）

如果无法运行安装器，可以手动编辑 `~/.codex/hooks.json`：

```json
{
  "description": "User-level Codex lifecycle hooks.",
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/path/to/python -m codex_wecom_notifier.hook",
            "timeout": 35,
            "statusMessage": "正在发送企业微信完成通知"
          }
        ]
      }
    ]
  }
}
```

将 `/path/to/python` 替换为当前 Python 解释器的绝对路径（通过 `which python` 查看）。同时确保 `~/.config/codex-wecom-notifier/config.json` 已正确配置。

---

## 凭证安全

| 文件 | 路径 | 权限 |
|------|------|------|
| 配置文件 | `~/.config/codex-wecom-notifier/config.json` | `0600`（仅所有者可读写） |
| 配置目录 | `~/.config/codex-wecom-notifier/` | `0700`（仅所有者可访问） |
| Hook 配置 | `~/.codex/hooks.json` | 跟随原有权限 |

Bot Secret 只保存在上述配置文件中。**不要把真实配置复制到项目、聊天、截图或 shell 命令中**；如果 Secret 曾经被发到聊天中，请先在企业微信后台重置。

---

## 配置

配置文件示例（`~/.config/codex-wecom-notifier/config.json`）：

```json
{
  "bot_id": "你的 Bot ID",
  "bot_secret": "你的 Secret",
  "target_id": "userid 或 chatid",
  "include_summary": true,
  "max_message_chars": 3500
}
```

| 字段 | 说明 | 默认值 |
|------|------|--------|
| `bot_id` | 智能机器人 Bot ID | 必填 |
| `bot_secret` | 智能机器人 Secret | 必填 |
| `target_id` | 接收人的 userid 或群聊 chatid | 必填 |
| `include_summary` | 是否附带不超过 200 字的完成摘要 | `true` |
| `max_message_chars` | 通知最大字符数 | `3500` |
| `ws_url` | 私有部署企业的 WebSocket 地址 | 官方公网地址 |

通知默认包含项目、模型、完成时间、当前一轮不超过 200 字的用户提示词，以及不超过 200 字的完成摘要。把 `include_summary` 改为 `false` 可关闭完成摘要；当前提示词仍会发送。

也可以通过环境变量覆盖配置（环境变量优先级高于配置文件）：

| 环境变量 | 对应字段 |
|----------|----------|
| `WECOM_BOT_ID` | `bot_id` |
| `WECOM_BOT_SECRET` | `bot_secret` |
| `WECOM_TARGET_ID` | `target_id` |
| `WECOM_WS_URL` | `ws_url` |
| `CODEX_WECOM_MAX_MESSAGE_CHARS` | `max_message_chars` |
| `CODEX_WECOM_INCLUDE_SUMMARY` | `include_summary` |

---

## 开发与测试

```bash
uv sync
uv run pytest
```

没有真实 Bot ID/Secret 时，单元测试不会连接企业微信。

---

使用 Hook 方案实现，兼容 Codex、CodeBuddy、Claude Code 等支持 lifecycle hooks 的工具。
