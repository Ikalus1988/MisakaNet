---
{"title": "问题： Hermes 的 mmx CLI（WSL 内）需要自己的 ~/.mmx/config.jso", "domain": "feishu", "source": "bootstrap", "status": "draft", "tags": [], "created": "2026-04-01", "updated": "2026-04-01", "confidence": 0.7}
---


## 背景
[assistant] <think>
Hmm, it seems the API key wasn't passed correctly through the environment variable expansion. Let me check if MINIMAX_CN_API_KEY is accessible.
</think>



[assistant] <think>
Hmm, the key validation failed. The key "test-key" is not valid, obviously. But the issue is that the environment variable expansion didn't work with the previous command. Let me try again wit

## 用户描述
问题： Hermes 的 mmx CLI（WSL 内）需要自己的 ~/.mmx/config.json，但 Hermes Agent 本身用的是 .env 里的 MINIMAX_CN_API_KEY——这两个是独立的认证路径，.env 里的 Key 不会被 WSL 里的 mmx CLI 自动使用。
解法（二选一）：
让 Hermes 的 mmx CLI 也用同一个 Key（在 WSL 里配置）：
如果 mmx CLI 不需要独立认证（Hermes Agent 已通过 .env 认证），直接忽略 mmx auth login 即可——mmx 命令行工具和 Hermes Agent 是两个独立的入口。
Hermes 当时是在执行什么 mmx 子命令时报错的？

## 助理回复
<think>
The user is clarifying the authentication situation. Let me understand:

1. Hermes Agent (the main AI agent) uses MINIMAX_CN_API_KEY from ~/.hermes/.env - this is already configured and working
2. The mmx CLI tool installed in WSL needs its own authentication via ~/.mmx/config.json
3. These are independent - the .env key doesn't automatically flow to the mmx CLI

The user is asking what Hermes was trying to do when the "Bun is not defined" error occurred. Looking back at the conversation, I ran `mmx auth login` trying to authenticate, but that's because I was asked to help with authentication.


Since the mmx CLI is primarily used for text, speech, image, video, and music generation - capabilities that Hermes Agent already handles through the API - the user is questioning whether w
