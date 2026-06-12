---
{"title": "Ccswitch", "domain": "general", "source": "skill-pipeline", "status": "draft", "tags": [], "created": "2026-05-09", "updated": "2026-05-09"}
---


## 背景

（此 lesson 从 skill `ccswitch` 自动提取，待补全）

## 根因

（待补充）

## 修复


# ccswitch — Claude Code 模型切换

## 是什么

`~/ccswitch` — 一键切换 Claude Code 模型和代理上游的 bash 脚本。
同时更新 `~/.claude/settings.json`（WSL）和 `C:/Users/User/.claude/settings.json`（Windows），并重启代理。

## 用法

```bash
ccswitch list              # 查看所有可用模型
ccswitch status             # 当前配置
ccswitch ds-flash           # 切换模型
ccswitch proxy on           # 启动代理 (DeepSeek)
ccswitch proxy off          # 关代理，直连 mify
ccswitch proxy status       # 代理状态
```

## 模型清单

| 命令 | 模型 | 上游 | 特点 |
|------|------|------|------|
| `ds-flash` | deepseek-v4-flash | DeepSeek | **默认**，极快 1-3s，日常用 |
| `ds-pro` | deepseek-v4-pro | DeepSeek | 强推理，适合复杂任务 |
| `mimo-2.5-pro` | xiaomi/mimo-v2.5-pro | Mioffice | 小米旗舰 |
| `mimo-2.5` | xiaomi/mimo-v2.5 | Mioffice | 便宜版 2.5 |
| `mimo-2-pro` | xiaomi/mimo-v2-pro | Mioffice | V2 Pro |
| `mimo-flash` | xiaomi/mimo-v2-flash | Mioffice | 轻量 |

## 切换原理

切换时自动执行三步：

1. **改 settings.json** — 更新 WSL + Windows 两侧的 `ANTHROPIC_DEFAULT_OPUS/SONNET/HAIKU_MODEL`
2. **重启代理** — `~/anthropic-openai-proxy.py` 用新上游启动（DeepSeek 或 Mioffice）
3. **对调 fallback** — DeepSeek 为主时 Mioffice 做 fallback，反之亦然

## 代理模式 (proxy on/off)

ccswitch 支持两种 Claude Code 连接模式：

| 模式 | 命令 | Claude 连接方式 | 适用场景 |
|------|------|-----------------|---------|
| **代理模式** (默认) | `ccswitch proxy on [model]` | Claude → localhost:8765 → DeepSeek/mioffice | 用 DeepSeek/mimo 等非 Anthropic 模型 |
| **直连模式** | `ccswitch proxy off` | Claude → mify (Anthropic 格式) → ppio/pa/claude-opus-4-6 | 用 mify 的 Claude 模型 |

### proxy off (mify 直连) 工作原理

1. 停止代理进程
2. 创建 `~/.local/bin/claude` 的 `--bare` wrapper（跳过 bootstrap，因为 mify 不支持 `api.anthropic.com` 的 bootstrap 调用）
3. settings.json 切换到 mify Anthropic 端点 + mify API key

### proxy on 工作原理

1. 恢复 claude 原生二进制（去掉 --bare wrapper）
2. settings.json 切换到 localhost:8765 + sk-proxy-local
3. 启动代理进程（ThreadingHTTPServer，多线程）

### Windows 桌面快捷方式

- `Desktop/start-claude-proxy.bat` — 一键启动代理
- `Desktop/stop-claude-proxy.bat` — 一键关闭代理 (切 mify 直连)

## 性能注意事项

- 代理使用 `ThreadingHTTPServer`（多线程），不会阻塞并发工具调用
- 代理本身额外延迟 ~5-10ms（可忽略），真正瓶颈是上游 API
- 代理格式转换：Anthropic Messages API ↔ OpenAI Chat Completions
- 技术细节见 `references/proxy-architecture.md`

## 代理进程存活陷阱

代理用 `nohup python3 ... &` 启动，但**如果启动它的 shell 退出，代理进程可能一起被杀**（取决于 shell 配置）。症状：过一会儿 `ccswitch proxy status` 显示未运行，Claude 连不上。

**正确做法：**
- 用 `ccswitch proxy on` 启动（内含 nohup）
- 或用桌面 bat：`start-claude-proxy.bat`（通过 wsl bash -lc 启动，进程脱离终端）
- 验证：`ss -tlnp | grep 8765` 确认端口在监听

**DEEPSEEK_API_KEY 可能未设置：** 代理在启动时从环境变量读取 key。如果新 shell 没有 `source` 过 key，代理会以空 key 启动（请求 401）。验证方法：`cat /proc/$(pgrep -f anthropic-openai-proxy)/environ | tr '\0' '\n' | grep UPSTREAM_KEY`

## 相关文件

| 文件 | 用途 |
|------|------|
| `~/ccswitch` | 切换脚本本体 |
| `~/.claude/settings.json` | WSL 侧 Claude 配置 |
| `C:/Users/User/.claude/settings.json` | Windows 侧 Claude 配置 |
| `~/anthropic-openai-proxy.py` | 本地代理（双上游 fallback） |
| `/tmp/proxy_env.sh` | Mioffice API key + MIOFFICE_API_KEY |

## Hermes 自身模型配置

在 `~/.hermes/config.yaml` 中配置了完整 fallback 链：

```yaml
model:
  default: deepsee

## 验证

（待补充）
