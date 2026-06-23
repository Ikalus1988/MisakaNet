---
{"title": "OpenClaw优先CLI和官方策略", "domain": "agentops", "tags": ["openclaw", "cli", "policy", "config"], "domain_expert": "unknown"}
---

## Background
直接ModifyConfiguration file（临时hack）容易变成Default模型，导致官方Path退化。

## 根因
官方CLI和策略面有健康Check和Version管理；直改File没有。

## Fix
1. 优先用 `openclaw config` / `gateway` 工具等官方Interface操作Configuration
2. 临时hack只作fallback，不作Default模型
3. 恢复时先恢复官方Path，再拆除临时hack

## 验证
Configuration操作Via官方CLI完成，系统行为与Configuration一致
