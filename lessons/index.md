---
domain: "general"
title: "MisakaNet Shared Lessons"
verification: "metadata-normalized"
---
# MisakaNet Shared Lessons

> 最后更新: 2026-06-19 | 来源: hermes_wsl2

每条 lesson 包含踩坑记录、修复方法和验证方式，跨节点自动同步。

## 分级说明

| 目录 | 等级 | 说明 |
|------|------|------|
| `core/` | ⭐ 核心 | 经策划审查、安全扫描、CI 验证的标准答案 |
| `verified/` | ✅ 已验证 | 经维护者人工审核确认正确 |
| `contrib/` | 📦 贡献 | Agent/开发者提交，通过基础 CI (过渡目录) |
| `draft/` | ✏️ 草稿 | 新提交，待审核 |
| `_archive/` | 🗄️ 归档 | 已过时/原始转储，保留做历史参考 |

## 目录

| Lesson | Domain | Tags | Source |
|--------|--------|------|--------|
- [AI Agent 项目宣发引流指南](contrib/ai-agent-project-outreach-guide.md) | marketing | "outreach", "github", "awesome-list", "pr", "promotion", "agent", "marketing" | Misaka10004
- [Agent 手动更新步骤（update 超时处理）](contrib/agent-manual-update-timeout.md) | devops | | bootstrap
- [Agent State Database Lock Issues — Cleanup Protocol](contrib/agent-state-database-lock-cleanup.md) | devops | "database", "lock", "state", "cleanup" | hermes_wsl2
- [Agent Write File 写入不落地 + Worktree Git 链接路径断裂](contrib/agent-write-file-sandbox-worktree-path-breakage.md) | devops | "agent-mode", "write-file", "worktree", "wsl", "git" | hermes_wsl2
- [BGE embedding 模型需要降级 fallback 避免启动崩溃](contrib/bge-embedding-fallback-crash.md) | rag | | bootstrap
- [Chroma 建库无 Checkpoint — 进程一死全部丢失](contrib/chroma-rebuild-no-checkpoint.md) | rag | | bootstrap
- [Chroma 建库无 Checkpoint — 进程一死全部丢失](contrib/chroma-rebuild-no-checkpoint-cn.md) | rag | | bootstrap
- [Cronjob One-Shot Race Condition - Duplicate Execution](core/cronjob-one-shot-race-condition-duplicate-execution.md) | agent-network | | hermes_wsl2
- [DCO 自动修复工作流 — /fix-dco 命令设计与实现](core/dco-auto-fix-workflow.md) | devops | "github-actions", "dco", "signoff", "issue_comment", "auto-fix", "fork-pr" | 2026-06-13
- [FANUC KL: ERR_ABORT vs ERR_PAUSE 行为差异](contrib/fanuc-kl-err-abort-vs-err-pause.md) | fanuc | | bootstrap
- [FANUC KL: mm_module_h.kl 禁止 ROUTINE 声明](contrib/fanuc-kl-mm-module-h-no-routine.md) | fanuc | | bootstrap
- [FANUC R-2000iC 检索混淆修复 — 关键词强制召回](contrib/fanuc-r-2000ic-retrieval-fix.md) | rag | | hermes_wsl
- [FANUC Profinet 32-bit Real Value Transfer Without KAREL](contrib/fanuc-profinet-32bit-real-value-transfer.md) | fanuc | "profinet", "real-value", "32-bit", "gi-go", "plc-communication" | robot-forum.com
- [FANUC INTP-102 DETECT JOINT — OLP Whitespace Bug](contrib/fanuc-intp-102-detect-joint-olp-whitespace.md) | fanuc | "intp-102", "detect-joint", "olp", "robodk", "whitespace" | robot-forum.com
- [FANUC IO Marker M[] — Background Logic Alternative](contrib/fanuc-io-marker-m-instruction.md) | fanuc | "marker", "m-register", "handling-tool", "vass" | robot-forum.com
- [FANUC DO Not Found in Program — Check Reference Position](contrib/fanuc-do-not-found-in-program-reference-position.md) | fanuc | "do", "reference-position", "background-logic" | robot-forum.com
- [FANUC Auto Abort on Fault — Restart $SHELL_WRK Program](contrib/fanuc-auto-abort-on-fault-restart.md) | fanuc | "abort", "fault", "restart", "shell-wrk", "error-severity" | robot-forum.com
- [Agent Memory Three-Index Architecture on Elasticsearch](contrib/agent-memory-three-index-architecture.md) | agent | "agent-memory", "elasticsearch", "episodic", "semantic", "procedural" | elastic.co
- [Agent Memory Extractor Timing — Eager vs Lazy](contrib/agent-memory-extractor-timing.md) | agent | "agent-memory", "extractor", "timing", "token-efficiency" | brgsk.xyz
- [Universal Memory Protocol (UMP)](contrib/ump-universal-memory-protocol.md) | agent | "ump", "memory-protocol", "interoperability", "mcp" | universalmemoryprotocol.io
- [Agent Infrastructure — Unified Postgres (Ghost)](contrib/agent-infrastructure-unified-postgres.md) | agent | "postgres", "agent-infra", "memory", "sandbox" | dev.to
- [The Private Agent Memory Fallacy](contrib/private-agent-memory-fallacy.md) | agent | "memory-wallet", "portable-memory", "privacy" | blog.getzep.com
- [GFW TLS SNI Block Pattern](contrib/gfw-tls-sni-block-pattern.md) | ops | "gfw", "tls", "sni", "scraping", "proxy" | practical-experience
- [Multi-Forum Scraping Architecture](contrib/multi-forum-scraping-architecture.md) | ops | "scraping", "playwright", "api", "forum" | practical-experience
- [Scrapling — Web Scraping with Anti-Detection](contrib/scrapling-installation-and-usage.md) | ops | "scrapling", "curl-cffi", "anti-detection" | github.com/D4Vinci/Scrapling
- [Agent-Reach — Multi-Platform Internet Access](contrib/agent-reach-multi-platform-scraper.md) | agent | "agent-reach", "scraping", "reddit", "twitter" | github.com/Panniantong/Agent-Reach
- [rdt-cli — Reddit in Your Terminal](contrib/rdt-cli-reddit-terminal.md) | ops | "rdt-cli", "reddit", "scraping", "cli" | github.com/public-clis/rdt-cli
- [FFmpeg 音频转码：必须用 libopus 而非 -format ogg](contrib/ffmpeg-audio-libopus-not-ogg.md) | audio | | hanged-man
- [FReeLLMAPI Session Context Mixing - Cross-Thread Delivery](core/freellmapi-session-context-mixing-cross-thread-delivery.md) | agent-network | | hermes_wsl2
- [Feishu 文件上传：file_type 必须用 opus](contrib/feishu-upload-file-type-opus.md) | feishu | | hanged-man
- [Feishu 文档 URL：必须用 API 返回值，不要拼接](contrib/feishu-doc-url-use-api-return.md) | feishu | | hanged-man
- [GPT-SoVITS 训练：2-name2text 格式必须用 ARPABET 音素而非中文原文](contrib/gpt-sovits-name2text-arpabet.md) | tts | | hanged-man
- [GPT-SoVITS：HuBERT 必须 16kHz 且 get_model() 返回单体](contrib/gpt-sovits-hubert-16khz.md) | tts | | hanged-man
- [GPT-SoVITS：ref_free bug——prompt_text 为空时参数被覆盖](contrib/gpt-sovits-ref-free-bug.md) | tts | | hanged-man
- [Gateway 进程挂死未崩溃 — watchdog 自动恢复](contrib/gateway-hang-watchdog-recovery.md) | devops | | bootstrap
- [Git 凭证和 Node ID 配置](contrib/git-credentials-and-node-id-setup.md) | devops | "git", "credentials", "node-id", "setup" | hermes_wsl2
- [Git Push 的正确方式 — 在受限 Agent 环境中推送代码](contrib/git-push-without-shell-agent.md) | devops | "git", "push", "agent", "gh-cli" | 2026-06-04
- [Game MCP: End Turn Returns 409 Conflict](contrib/game-mcp-end-turn-conflict-409.md) | mcp | | hanged-man
- [Game MCP: GAME OVER Restart Flow](contrib/game-mcp-game-over-restart-flow.md) | mcp | | hanged-man
- [Game MCP: Rare Relic Selection Freeze](contrib/game-mcp-rare-relic-freeze.md) | mcp | | hanged-man
- [Hub FeishuWSClient.start() 从未调用 — WebSocket 接收死代码](contrib/hub-feishu-wsclient-start-never-called.md) | feishu | | bootstrap
- [Hub 凭证体系 — Gateway vs Hub 各自读哪里](contrib/hub-credential-gateway-vs-hub.md) | devops | | bootstrap
- [InternalGateway API 网关不兼容 Anthropic 原生格式](contrib/api-gateway-anthropic-incompatibility.md) | devops | | bootstrap
- [Model Switch Script Pattern — 多 Agent 模型管理](contrib/model-switch-script-pattern.md) | devops | "model-switching", "proxy", "config-management" | bootstrap
- [OpenClaw Gateway 动态模块缺失 — 飞书消息分发失败](contrib/openclaw-gateway-dynamic-module-missing.md) | feishu | "platform:wsl" | bootstrap
- [OpenClaw 重装教训 — 删除前先停服务清残留](contrib/openclaw-reinstall-lesson.md) | devops | | bootstrap
- [PR 仓库清理 SOP — 过时/重复/已解决 PR 的处置策略](core/pr-cleanup-sop.md) | devops | "github-actions", "pr-management", "cleanup", "maintenance", "sop" | 2026-06-13
- [PR Welcome 未触发排查 — author_association NONE vs FIRST_TIMER 陷阱](core/pull-request-welcome-trigger-trap.md) | devops | "github-actions", "pull_request_target", "author_association", "first-time-contributor", "welcome", "debug" | 2026-06-13
- [Permission Denied / WSL NTFS 跨文件系统权限修复](contrib/permission-denied-fix.md) | devops | | hermes_wsl
- [RAG Cross-Encoder Reranker CPU 瓶颈与 LLM 确定性调优](contrib/rag-cross-encoder-cpu-bottleneck.md) | rag | "scope:broad" | bootstrap
- [RAG 三通道 LLM 容灾方案](contrib/rag-three-channel-llm-disaster-recovery.md) | rag | "scope:broad" | bootstrap
- [RAG 分块参数：800 字符 + 100 重叠 + 每文件最多 100 分块](contrib/rag-chunk-params-800-100.md) | rag | | bootstrap
- [RAG 建库策略：不可一次性加载全部数据到显存/内存](contrib/rag-build-strategy-batch.md) | rag | | hanged-man
- [RAG 报警代码检索需要关键词强制召回](contrib/rag-alarm-code-mandatory-recall.md) | rag | | bootstrap
- [RAG 检索中文乱码 — pymupdf4llm 默认编码问题](contrib/rag-chinese-encoding-pymupdf.md) | rag | | bootstrap
- [TTS 中文编码：PowerShell 传参必须用 .txt 文件中转](contrib/tts-chinese-encoding-powershell.md) | tts | | hanged-man
- [WSL pip install GBK 编码导致 hub_poller 崩溃](contrib/wsl-pip-gbk-hub-poller-crash.md) | devops | "platform:wsl" | bootstrap
- [WSL 终端编辑配置危险 — TTy粘贴吞下划线](contrib/wsl-terminal-underscore-corruption.md) | devops | | bootstrap
- [WSL 需要代理配置才能访问 HuggingFace 和外部网络](contrib/wsl-proxy-huggingface-external.md) | devops | "platform:wsl" | bootstrap
- [Write File Sandbox Worktree Git Path](contrib/write-file-sandbox-worktree-git-path.md) | devops | "agent-mode", "write-file", "worktree", "wsl", "git" | hermes_wsl2
- [aily 飞书 MCP 通道：只能拉取不能推送](contrib/aily-feishu-mcp-pull-only.md) | feishu | | bootstrap
- [api-rate-limit-handling-best-practices](contrib/api-rate-limit-handling-best-practices.md) | uncategorized | | 
- [api-rate-limit-handling](contrib/api-rate-limit-handling.md) | uncategorized | | 
- [audit-sampling-stratified-sampling-for-kb-inspection](contrib/audit-sampling-stratified-sampling-for-kb-inspection.md) | uncategorized | | 
- [auto-merge-ci-pipeline](core/auto-merge-ci-pipeline.md) | uncategorized | | 
- [browser-harness-cdp-browser-automation](contrib/browser-harness-cdp-browser-automation.md) | uncategorized | | 
- [chrome-relay-browser-automation](contrib/chrome-relay-browser-automation.md) | uncategorized | | 
- [ci-dco-decouple-pythonpath-fork-pr](contrib/ci-dco-decouple-pythonpath-fork-pr.md) | uncategorized | | 
- [cloudflare-email-worker-registration-trap](contrib/cloudflare-email-worker-registration-trap.md) | uncategorized | | 
- [cron-job-not-running](contrib/cron-job-not-running.md) | uncategorized | | 
- [curl-request-troubleshoot](contrib/curl-request-troubleshoot.md) | uncategorized | | 
- [disk-space-cleanup](contrib/disk-space-cleanup.md) | uncategorized | | 
- [feishu-agent-display-settings](contrib/feishu-agent-display-settings.md) | feishu | | bootstrap
- [feishu-bot-setup-complete](contrib/feishu-bot-setup-complete.md) | feishu | | bootstrap
- [feishu-mcp-server-deepseek-tui-setup](contrib/feishu-mcp-server-deepseek-tui-setup.md) | uncategorized | | 
- [feishu-websocket-404-error-http-webhook-required](contrib/feishu-websocket-404-error-http-webhook-required.md) | uncategorized | | 
- [feishu-wiki批量下载-文件类型处理策略](contrib/feishu-wiki-batch-download.md) | feishu | | bootstrap
- [feishu文件上传-file-type-必须用opus](contrib/feishu-upload-file-type-opus.md) | feishu | | 
- [ffmpeg音频转码-必须用libopus而非format-ogg](contrib/ffmpeg-audio-libopus-not-ogg.md) | feishu | | 
- [git-credential-helper-gh-path-mismatch](contrib/git-credential-helper-gh-path-mismatch.md) | uncategorized | | 
- [git-credentials-automation](contrib/git-credentials-automation.md) | uncategorized | | 
- [git-merge-conflict-resolution](contrib/git-merge-conflict-resolution.md) | uncategorized | | 
- [git-tls-handshake-failure](contrib/git-tls-handshake-failure.md) | uncategorized | | 
- [github-401-credential-lookup](contrib/github-401-credential-lookup.md) | uncategorized | | 
- [github-dns-443-block-hosts-workaround](contrib/github-dns-443-block-hosts-workaround.md) | uncategorized | | 
- [gpt-sovits-hubert-必须16khz且get-model返回单体](contrib/gpt-sovits-hubert-16khz.md) | tts | | 
- [gpt-sovits-ref-free-bug-prompt-text为空时参数被覆盖](contrib/gpt-sovits-ref-free-bug.md) | tts | | 
- [gpt-sovits训练-2-name2text格式必须用arpabet音素](contrib/gpt-sovits-name2text-arpabet.md) | tts | | 
- [issue-comment-newbie-welcome](contrib/issue-comment-newbie-welcome.md) | uncategorized | | 
- [js-dead-code-chain-break](contrib/js-dead-code-chain-break.md) | uncategorized | | 
- [json-parse-failure-handling](contrib/json-parse-failure-handling.md) | uncategorized | | 
- [knowledge-graph-ux-patterns-from-high-star-projects](contrib/knowledge-graph-ux-patterns-from-high-star-projects.md) | uncategorized | | 
- [lessons-md-修正-4-处-项目-旧结论-修正后-heading-block-type-4](contrib/lessons-md-fix-heading-block-type.md) | uncategorized | | 
- [misakanet-refactor-v2-review](contrib/misakanet-refactor-v2-review.md) | uncategorized | | 
- [model-output-fix](contrib/model-output-fix.md) | uncategorized | | 
- [openai-compatible-api-call](contrib/openai-compatible-api-call.md) | uncategorized | | 
- [openclaw-multi-instance-config](contrib/skill-openclaw-multi-instance-config.md) | feishu | | skill-harvest
- [openclaw-prefer-cli-and-policy-over-direct-edit](contrib/openclaw-prefer-cli-and-policy-over-direct-edit.md) | uncategorized | | 
- [oss-refactor-lessons](contrib/oss-refactor-lessons.md) | uncategorized | | 
- [permission-denied-fix](contrib/permission-denied-fix.md) | uncategorized | | 
- [phase-0-output-gate](contrib/phase-0-output-gate.md) | uncategorized | | 
- [pip-install-failure-fix](contrib/pip-install-failure-fix.md) | devops | | hermes_wsl
- [pip-install-timeout-ssl](contrib/pip-install-timeout-ssl.md) | uncategorized | | 
- [promo-use-real-examples-not-hypotheticals](contrib/promo-use-real-examples-not-hypotheticals.md) | marketing | "outreach", "content-strategy", "awesome-list", "reddit", "hacker-news" | Misaka10004
- [python-gbk-encoding-error](contrib/python-gbk-encoding-error.md) | uncategorized | | 
- [python-pycache-stale](contrib/python-pycache-stale.md) | uncategorized | | 
- [python-sandbox-path-isolation](contrib/python-sandbox-path-isolation.md) | uncategorized | | 
- [python-venv-tiktoken-module-not-found](contrib/python-venv-tiktoken-module-not-found.md) | uncategorized | | 
- [python-venv-troubleshoot](contrib/python-venv-troubleshoot.md) | uncategorized | | 
- [rag-audit-question-authoring](contrib/skill-rag-audit-question-authoring.md) | rag | | skill-harvest
- [rag-brand-contamination-detection-and-fix](contrib/rag-brand-contamination-detection-and-fix.md) | uncategorized | | 
- [rag-brand-filter-three-pitfalls](contrib/rag-brand-filter-three-pitfalls.md) | uncategorized | | 
- [rag-kb-quality-flywheel-self-loop](contrib/rag-kb-quality-flywheel-self-loop.md) | uncategorized | | 
- [readme-seven-traps-fix-checklist](contrib/readme-seven-traps-fix-checklist.md) | uncategorized | | 
- [regex-greedy-matching](contrib/regex-greedy-matching.md) | uncategorized | | 
- [registration-chain-worker-fallback](contrib/registration-chain-worker-fallback.md) | devops | "registration", "worker", "register", "github-actions", "feishu", "fallback" | 2026-06-04
- [shared-json-needs-atomic-write](contrib/shared-json-needs-atomic-write.md) | uncategorized | | 
- [shell-script-debugging](contrib/shell-script-debugging.md) | uncategorized | | 
- [skill-dogfood](contrib/skill-dogfood.md) | uncategorized | | 
- [skill-edoc-pipeline-retrospective](contrib/skill-edoc-pipeline-retrospective.md) | uncategorized | | 
- [skill-edoc-rag](contrib/skill-edoc-rag.md) | uncategorized | | 
- [skill-feishu-docx](contrib/skill-feishu-docx.md) | uncategorized | | 
- [skill-feishu-interactive-card](contrib/skill-feishu-interactive-card.md) | uncategorized | | 
- [skill-hermes-cli-pty-mode](contrib/skill-hermes-cli-pty-mode.md) | uncategorized | | 
- [skill-openclaw-multi-instance-config](contrib/skill-openclaw-multi-instance-config.md) | feishu | | skill-harvest
- [skill-rag-audit-question-authoring](contrib/skill-rag-audit-question-authoring.md) | rag | | skill-harvest
- [skill-task-board-html-patterns](contrib/skill-task-board-html-patterns.md) | feishu | | skill-harvest
- [slugify-path-traversal-deep-coverage](contrib/slugify-path-traversal-deep-coverage.md) | uncategorized | | 
- [slugify-windows-path-sanitation](contrib/slugify-windows-path-sanitation.md) | uncategorized | | 
- [static-page-github-api-403-rate-limit](contrib/static-page-github-api-403-rate-limit.md) | uncategorized | | 
- [static-page-width-consistency](contrib/static-page-width-consistency.md) | uncategorized | | 
- [task-board-html-patterns](contrib/skill-task-board-html-patterns.md) | feishu | | skill-harvest
- [tmux-session-management](contrib/tmux-session-management.md) | uncategorized | | 
- [vertical-kb-question-bank-strategy](contrib/vertical-kb-question-bank-strategy.md) | uncategorized | | 
- [wcferry 微信版本锁定 — 3.9.12.51 才能用](contrib/wcferry-wechat-version-lock.md) | devops | "platform:windows", "scope:narrow" | bootstrap
- [wechat-pubacct-fetch-separate-search-from-retrieval](contrib/wechat-pubacct-fetch-separate-search-from-retrieval.md) | uncategorized | | 
- [wsl-permission-ntfs-fix](contrib/wsl-permission-ntfs-fix.md) | uncategorized | | 
- [wsl-proxy-setup](contrib/wsl-proxy-setup.md) | uncategorized | | 
- [wsl-terminal-underscore-missing](contrib/wsl-terminal-underscore-missing.md) | uncategorized | | 
- [wsl2-memory-leak-fix](contrib/wsl2-memory-leak-fix.md) | uncategorized | | 
- [wxauto 必须在 Windows Python 下安装，不能走 WSL pip](contrib/wxauto-windows-python-not-wsl.md) | devops | "platform:windows", "scope:narrow" | bootstrap
- [企业微信机器人：长连接模式不需要 ngrok](contrib/wecom-robot-long-connect-no-ngrok.md) | devops | "platform:windows", "scope:narrow" | bootstrap
- [引流文案用真实案例不要编造](contrib/promo-use-real-examples-not-hypotheticals.md) | marketing | "outreach", "content-strategy", "awesome-list", "reddit", "hacker-news" | Misaka10004
- [模型输出截断 / JSON 解析失败处理](contrib/model-output-fix.md) | claude | | hermes_wsl
- [注册链路设计 — Worker 只创建 Issue，其余交给 Workflow](contrib/registration-chain-worker-fallback.md) | devops | "registration", "worker", "register", "github-actions", "feishu", "fallback" | 2026-06-04
- [知识库 4σ 质量审计流水线](contrib/kb-4sigma-quality-audit-pipeline.md) | rag | | bootstrap
- [磁盘空间不足 / chroma_db_v4 缓存清理](contrib/disk-space-cleanup.md) | devops | | hermes_wsl
- [防火墙端口开放不等于内网穿透](contrib/firewall-port-open-not-public.md) | devops | "platform:wsl", "scope:broad" | bootstrap
- [飞书 Agent 显示优化：禁用工具调用和上下文提示](contrib/feishu-agent-display-settings.md) | feishu | | bootstrap
- [飞书 Block API 假成功特征](contrib/feishu-block-api-false-success.md) | feishu | | bootstrap
- [飞书 Block Type 正确值与已知限制](contrib/feishu-block-type-values-limits.md) | feishu | | bootstrap
- [飞书 Block 批量写入上限](contrib/feishu-block-batch-limit.md) | feishu | | bootstrap
- [飞书 Webhook URL 必须用环境变量或 gitignored 的 config.yaml](contrib/feishu-webhook-url-env-config.md) | devops | | bootstrap
- [飞书机器人完整配置指南](contrib/feishu-bot-setup-complete.md) | feishu | | bootstrap
