---
title: "DSH Hindsight 插件守护进程反复 `daemon start timeout (180s)`、9077 ECONNREFUSED：uvx `hindsight-embed@latest` 每次冷启动都要重解析索引并整包重装"
domain: "mcp"
tags:
  - "hindsight"
  - "dsh"
  - "mcp"
  - "daemon"
  - "uvx"
  - "uv-cache"
  - "embedversion"
  - "latest-tag"
  - "cold-start-timeout"
  - "econnrefused"
status: "published"
evidence_level: "E1"
created: "2026-10-30"
updated: "2026-10-30"
source: "intake-3253"
summary_plain: "环境：DSH 桌面版 0.2.0-rc.2（`DSH_HOME=E://[REDACTED:url_credential]@host 0.8.1，装在…"
trigger: "DSH Hindsight 插件守护进程反复 `daemon start timeout (180s)`、9077 ECONNREFUSED：uvx `hindsight-embed@latest` 每次冷启动都要重解析索引并整包重装. 环境：DSH 桌面版…"
verify: "① 端口在听：`netstat -ano | Select-String ':9077'` → `TCP 127.0.0.1:9077 0.0.0.0:0 LISTENING 14924`； ② 健康检查通过：`Invoke-WebRequest http://127.0.0.1:9077/health -UseBasicParsing` → `status=200`，body…"
provenance:
  issue: "#3253"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

环境：DSH 桌面版 0.2.0-rc.2（`DSH_HOME=E://[REDACTED:url_credential]@host 0.8.1，装在 `E:\Deepseek\dsh-data\.dsh\profiles\desktop\node_modules\@vectorize-io\hindsight-coding-agents`；Hindsight 配置 `C:\Users\28481\.hindsight\coding-agent.json` 原本是 `{"serverMode":"daemon","apiPort":9077,"daemonProfile":"coding-agent"}`；profile 参数文件 `C:\Users\28481\.hindsight\profiles\coding-agent.env`；诊断日志 `C:\Users\28481\.hindsight\coding-agents-logs\diag.jsonl`。

症状：会话中 Hindsight 记忆工具全线不可用——`hindsight_sync_status` / `hindsight_list_knowledge_pages` 返回 `fetch failed: connect ECONNREFUSED 127.0.0.1:9077 (ECONNREFUSED)`，知识页永远是 “No knowledge pages yet”；`netstat -ano | Select-String ':9077'` 无任何监听行。

日志里不是偶发，而是**固定五天的复现模式**：`diag.jsonl` 中反复出现 `daemon_start_failed` + `Hindsight daemon did not become ready in time (180s elapsed)`，**紧接着几分钟后又出现 `daemon_started`**。也就是说：第一次启动必然超时失败，重试那次却成功——因为第一次已经把包装好了。

排障陷阱：`pwsh` 工具在 `workspace-write` 沙箱下会以 `[exit code: 3221225794]`（=0xC0000142）直接崩溃，连 `netstat` 都跑不了，只有 `danger-full-access` 才能执行取证命令；另外 `C:\Users\28481\.hindsight\profiles\coding-agent.log` 不是合法 UTF-8，`read` 工具会报 `invalid UTF-8 text` 拒读。

## Root Cause

证据链（均已实机复核）：

1) **插件用 `uvx hindsight-embed@<版本>` 拉起守护进程，版本默认是 `latest`**。`dist/daemon-start.js://[REDACTED:url_credential]@host 意味着**每次启动 uvx 都要去索引服务器重新解析 latest、做依赖求解，并在版本指纹变化时整包重装**。

2) **重复安装的物证**：`C://[REDACTED:url_credential]@host 让第二份缓存也无法兜底**：即使上一轮已经装好，只要索引里的 latest 指纹变了（或索引不可达导致解析退避），uvx 仍会走重装路径，缓存命中不稳定，所以问题会**周期性复发**而不是一次性。

5) **配置层级关系确认**（`daemon-start.js:468`、`:798-799`）：`CONFIG_PATH = process.env.HINDSIGHT_CONFIG || join(homedir(), ".hindsight", "coding-agent.json")`；`loadConfig` 先叠 env 层再叠**文件层（文件覆盖 env）**，因此把版本写进 `coding-agent.json` 是生效且优先级最高的做法。

6) 排除项：守护进程是以 `--idle-timeout 0 --port 9077` 启动的（永不因空闲退出），所以这次 `ECONNREFUSED` **不是**空闲超时，而是上一次 DSH 关闭时子进程被杀掉、下次冷启动又超时失败造成的。

## Fix

把 embed 版本从 `latest` 改成钉死的具体版本，让每次启动走 uv 缓存直取、不再解析索引：

1) 编辑 `C://[REDACTED:url_credential]@host serve --port 9077

## Verification

① 端口在听：`netstat -ano | Select-String ':9077'` → `TCP 127.0.0.1:9077 0.0.0.0:0 LISTENING 14924`；
② 健康检查通过：`Invoke-WebRequest http://127.0.0.1:9077/health -UseBasicParsing` → `status=200`，body `{"status":"healthy","database":"connected","db_acquire_ms":0.0,"db_pool_waiting":0,"db_pool_in_use":0,"db_pool_max":100,"db_pool_idle":5}`；
③ 版本已钉死：`Invoke-WebRequest http://127.0.0.1:9077/version` → `{"api_version":"1.0.0","features":{"observations":true,"mcp":true,"worker":true,...}}`；
④ DSH 侧通道恢复：`hindsight_sync_status` 不再返回 `ECONNREFUSED`，能正常给出 bank/workspace 同步状态；
⑤ 复发判据：`C:\Users\28481\.hindsight\coding-agents-logs\diag.jsonl` 中不再出现 `Hindsight daemon did not become ready in time (180s elapsed)`；uv 缓存中 `hindsight_embed-*.dist-info` 份数不再增长（修复前实测 0.10.3×6 + 1.0.0×2）。
