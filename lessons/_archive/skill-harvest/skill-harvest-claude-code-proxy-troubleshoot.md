---
{"title": "Claude Code Proxy Troubleshoot", "domain": "general", "source": "skill-pipeline", "status": "draft", "tags": [], "created": "2026-05-09", "updated": "2026-05-09"}
---


## 背景

（此 lesson 从 skill `claude-code-proxy-troubleshoot` 自动提取，待补全）

## 根因

（待补充）

## 修复


# Claude Code 代理故障诊断

## 触发场景

- Claude 报 `Unable to connect to API (ConnectionRefused)`
- Claude 卡在 `Retrying in 3s · attempt N/10`
- 用户问"代理怎么开关"、"连不上了"
- `ccswitch proxy status` 显示代理未运行

## 快速诊断流程

```bash
# 1. 三行诊断
ccswitch proxy status                    # 代理是否在跑 + 当前模式
ss -tlnp | grep 8765                     # 端口是否在监听
ps aux | grep anthropic-openai-proxy | grep -v grep  # 进程是否存在
```

## 常见问题 & 修复

### 问题 1：代理进程不在了（最常见）

代理进程可能因 shell 退出、系统休眠、OOM 等原因消失。

```bash
# 重启代理（确保 DEEPSEEK_API_KEY 可用）
ccswitch proxy on
# 或手动启动：
UPSTREAM_BASE="https://api.deepseek.com/v1" \
UPSTREAM_KEY="$DEEPSEEK_API_KEY" \
DEFAULT_MODEL="deepseek-v4-flash" \
FALLBACK_BASE="https://api.deepseek.com/v1" \
FALLBACK_KEY="$DEEPSEEK_API_KEY" \
FALLBACK_MODEL="deepseek-v4-flash" \
python3 ~/anthropic-openai-proxy.py &
```

### 问题 2：DEEPSEEK_API_KEY 环境变量为空

代理进程启动时从 shell 继承环境变量。如果启动代理的 shell 没设 DEEPSEEK_API_KEY，代理会带着空 key 去调 DeepSeek → 401。

```bash
# 检查代理进程实际拿到的 key
cat /proc/<PID>/environ | tr '\0' '\n' | grep DEEPSEEK
# 如果为空，source 后重启
source /tmp/proxy_env.sh  # 或 export DEEPSEEK_API_KEY=xxx
ccswitch proxy on
```

### 问题 3：settings.json 被改成 mify 直连但代理没跑

`ccswitch proxy off` 会把 settings.json 改成 mify 直连模式。如果之后想用代理但忘了切回来：

```bash
# 看当前 settings 指向哪
python3 -c "import json; d=json.load(open('~/.claude/settings.json')); print(d['env']['ANTHROPIC_BASE_URL'])"
# 如果是 model.mify.ai.srv → 说明是直连模式
# 如果是 127.0.0.1:8765 → 说明是代理模式

# 切回代理模式
ccswitch proxy on
```

### 问题 4：mify 直连模式下 Claude onboarding 弹窗

Claude 启动时检测到自定义 API key，弹出 "Do you want to use this API key?" 选择框。

- **选 1. Yes** — 使用 mify key
- 如果 bootstrap 报错 → 需要 `--bare` 模式（`ccswitch proxy off` 会自动创建 wrapper）

### 问题 5：代理在跑但 Claude 仍然连不上

可能是 Claude 进程在代理启动之前就启动了，连接已失败。

```bash
# 退出当前 claude，重新启动
exit  # 或 Ctrl+C
claude
```

## 两种模式速查

| 模式 | 命令 | ANTHROPIC_BASE_URL | 用途 |
|------|------|--------------------|----|
| 代理 ON | `ccswitch proxy on` | `http://127.0.0.1:8765` | DeepSeek/mimo 模型 |
| 代理 OFF | `ccswitch proxy off` | `http://model.mify.ai.srv/anthropic` | mify Claude 直连 |

## 代理架构

```
Claude Code (Anthropic 格式)
    ↓ localhost:8765
anthropic-openai-proxy.py (ThreadingHTTPServer)
    ↓ 格式转换: Anthropic Messages → OpenAI Chat Completions
DeepSeek API / Mioffice API (OpenAI 格式)
    ↓ 响应转换回来
Claude Code
```

- 代理额外延迟 ~5-10ms（可忽略）
- ThreadingHTTPServer 多线程，不会阻塞并发工具调用
- 双上游 fallback：主挂了自动切备

## 相关命令

```bash
ccswitch proxy status    # 查看代理状态
ccswitch proxy on        # 开代理
ccswitch proxy off       # 关代理（mify 直连）
ccswitch status          # 查看完整配置（模型+代理）
ccswitch list            # 可用模型列表
```

## 相关文件

| 文件 | 用途 |
|------|------|
| `~/anthropic-openai-proxy.py` | 代理脚本（ThreadingHTTPServer :8765） |
| `~/ccswitch` | 模型+代理切换脚本 |
| `~/.claude/settings.json` | WSL 侧 Claude 配置 |
| `C:/Users/User/.claude/settings.json` | Windows 侧 Claude 配置 |
| `/tmp/proxy_env.sh` | API key 环境变量 |
| `~/Desktop/start-claude-proxy.bat` | Windows 桌面一键开代理 |
| `~/Desktop/stop-claude-proxy.bat` | Windows 桌面一键关代理 |


## 验证

（待补充）
