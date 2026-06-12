---
{"title": "OpenClaw优先CLI和官方策略", "domain": "agentops", "source": "unknown", "status": "draft", "tags": ["openclaw", "cli", "policy", "config"], "created": "2026-06-12 18:46:23 UTC", "updated": "2026-06-12 18:46:23 UTC"}
---


## 背景
直接修改配置文件（临时hack）容易变成默认模型，导致官方路径退化。

## 根因
官方CLI和策略面有健康检查和版本管理；直改文件没有。

## 修复
1. 优先用 `openclaw config` / `gateway` 工具等官方接口操作配置
2. 临时hack只作fallback，不作默认模型
3. 恢复时先恢复官方路径，再拆除临时hack

## 验证
配置操作通过官方CLI完成，系统行为与配置一致
