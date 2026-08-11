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

“接收消息”文档中的 `response_url` 只会在用户先向机器人发消息后出现，适合对该消息进行临时回复。Codex 独立完成任务时没有对应的用户消息，因此本工具使用长连接协议中的 `aibot_send_msg` 主动推送。连接只在发送期间存在。

## 安装

先在企业微信管理后台创建“智能机器人 → API 模式 → 长连接”，准备 Bot ID 和 Secret。

如果不知道自己的 userid 或群 chatid，安装器可以自动获取：运行后按提示私聊机器人发一条文本，或者在目标群里 @机器人。

```bash
uv sync
uv run python scripts/install_macos.py --bot-id '你的 Bot ID'
```

安装器会通过隐藏输入读取 Secret，不会把它放进 shell 历史；随后会临时建立连接，等待你向机器人发送一条消息，并从消息的 `from.userid` 或 `chatid` 保存接收目标。

如果已经知道接收目标，可以直接指定：

```bash
uv run python scripts/install_macos.py \
  --bot-id '你的 Bot ID' \
  --target-id '你的 userid 或 chatid'
```

完成后：

1. 重启 Codex。
2. 在 Codex 中运行 `/hooks`。
3. 审核并信任 `codex_wecom_notifier.hook`。
4. 运行下面的手动测试，或直接完成下一次 Codex 任务。

安装器会保留 `~/.codex/hooks.json` 中已有的其他 Hook，只替换本工具自己的旧条目。

## 凭证安全

Bot Secret 只保存在 `~/.config/codex-wecom-notifier/config.json`。安装器会把目录权限设为 `0700`、文件权限设为 `0600`。不要把真实配置复制到项目、聊天、截图或 shell 命令中；如果 Secret 曾经被发到聊天中，请先在企业微信后台重置。

## 手动验证

```bash
uv run codex-wecom-send '这是一条连通性测试。'
```

命令会建立一次连接、发送、断开；成功时输出“通知已发送”。

## 配置

配置文件支持：

| 字段 | 说明 | 默认值 |
| --- | --- | --- |
| `bot_id` | 智能机器人 Bot ID | 必填 |
| `bot_secret` | 智能机器人 Secret | 必填 |
| `target_id` | 接收人的 userid 或群聊 chatid | 必填 |
| `include_summary` | 是否附带不超过 50 字的完成摘要 | `true` |
| `max_message_chars` | 通知最大字符数 | `3500` |
| `ws_url` | 私有部署企业的 WebSocket 地址 | 官方公网地址 |

通知默认包含项目、模型、完成时间、当前一轮不超过 50 字的用户提示词，以及不超过 50 字的完成摘要。把 `include_summary` 改为 `false` 可关闭完成摘要；当前提示词仍会发送。

## 开发与测试

```bash
uv sync
uv run pytest
```

没有真实 Bot ID/Secret 时，单元测试不会连接企业微信。
