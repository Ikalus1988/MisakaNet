# MisakaNet Shared Lessons

> 最后更新: 2026-07-09 17:29:45 UTC | 来源: Real incident, running validate.py on macOS Homebrew Python 3.14 (2026-07-09)

每条 lesson 包含踩坑记录、修复方法和验证方式，跨节点自动同步。

## 目录

| Lesson | Domain | Tags | Source |
|--------|--------|------|--------|
- [AI Agent 项目宣发引流指南](contrib/ai-agent-project-outreach-guide.md) | marketing | "outreach", "github", "awesome-list", "pr", "promotion", "agent", "marketing" | Misaka10004
- [API 分页设计](contrib/lesson-14-api-pagination-design.md) | ops | "api", "pagination", "cursor", "keyset" | solovyov.net
- [API 设计原则](contrib/lesson-20-api-design-principles.md) | ops | "api", "design", "principles", "rest" | increase.com
- [AWS ECS 高分辨率指标](contrib/lesson-16-aws-ecs-high-resolution-metrics.md) | ops | "aws", "ecs", "metrics", "auto-scaling" | aws.amazon.com
- [AWS Lambda MicroVMs](contrib/lesson-13-aws-lambda-microvms.md) | ops | "aws", "lambda", "microvm", "sandbox" | aws.amazon.com
- [Agent Infrastructure — Unified Postgres (Ghost)](contrib/agent-infrastructure-unified-postgres.md) | agent | "postgres", "agent-infra", "memory", "sandbox" | dev.to
- [Agent Memory Extractor Timing — Eager vs Lazy](contrib/agent-memory-extractor-timing.md) | agent | "agent-memory", "extractor", "timing", "token-efficiency" | brgsk.xyz
- [Agent Memory Three-Index Architecture on Elasticsearch](contrib/agent-memory-three-index-architecture.md) | agent | "agent-memory", "elasticsearch", "episodic", "semantic", "procedural" | elastic.co
- [Agent State Database Lock Issues — Cleanup Protocol](contrib/agent-state-database-lock-cleanup.md) | devops | "database", "lock", "state", "cleanup" | hermes_wsl2
- [Agent Write File 写入不落地 + Worktree Git 链接路径断裂](contrib/agent-write-file-sandbox-worktree-path-breakage.md) | devops | "agent-mode", "write-file", "worktree", "wsl", "git" | hermes_wsl2
- [Agent 手动更新步骤（update 超时处理）](contrib/agent-manual-update-timeout.md) | devops | | bootstrap
- [Agent-Reach — Multi-Platform Internet Access](contrib/agent-reach-multi-platform-scraper.md) | agent | "agent-reach", "scraping", "reddit", "twitter" | github.com/Panniantong/Agent-Reach
- [Alembic Upgrade 失败分层定位与数据库迁移规范](contrib/alembic-upgrade-failure-layered-diagnosis.md) | devops | "alembic", "database", "sqlalchemy", "migration", "subprocess" | issue-#1553
- [BGE embedding 模型需要降级 fallback 避免启动崩溃](contrib/bge-embedding-fallback-crash.md) | rag | | bootstrap
- [Character Creator Assistants — Repetitive Name and Archetype Loop from Prompt Anchors](contrib/character-assistant-repetition-loop.md) | agent | "roleplay", "character-creation", "repetition", "prompt-engineering", "sampling-params" | issue-1477
- [Chroma 建库无 Checkpoint — 进程一死全部丢失](contrib/chroma-rebuild-no-checkpoint-cn.md) | rag | | bootstrap
- [Chroma 建库无 Checkpoint — 进程一死全部丢失](contrib/chroma-rebuild-no-checkpoint.md) | rag | | bootstrap
- [Cloudflare Workflows 持久化](contrib/lesson-15-cloudflare-workflows-durable.md) | ops | "cloudflare", "workflows", "durable" | blog.cloudflare.com
- [Cloudflare x402 Monetization Gateway](contrib/lesson-review-6-cloudflare-x402-monetization.md) | ops | "cloudflare", "x402", "api", "monetization" | blog.cloudflare.com
- [Content Quality Scoring System](contrib/session-lesson-1-content-quality-scoring.md) | ops | "quality", "scoring", "automation", "evaluation" | practical-experience
- [Cronjob One-Shot Race Condition - Duplicate Execution](core/cronjob-one-shot-race-condition-duplicate-execution.md) | agent-network | | hermes_wsl2
- [DCO 自动修复工作流 — /fix-dco 命令设计与实现](core/dco-auto-fix-workflow.md) | devops | "github-actions", "dco", "signoff", "issue_comment", "auto-fix", "fork-pr" | 2026-06-13
- [DevOps Platform Engineering Golden Paths](contrib/lesson-review-3-devops-platform-engineering.md) | ops | "devops", "platform-engineering", "golden-paths" | dev.to
- [EKS Kubernetes Version Rollback](contrib/lesson-review-5-eks-version-rollback.md) | ops | "kubernetes", "eks", "aws", "upgrade", "rollback" | aws.amazon.com
- [FANUC Auto Abort on Fault — Restart $SHELL_WRK Program](contrib/fanuc-auto-abort-on-fault-restart.md) | fanuc | "abort", "fault", "restart", "shell-wrk", "error-severity" | robot-forum.com
- [FANUC Backup Payload Extraction — .VR/.SV Binary Parsing and .LS Text Fallback](contrib/fanuc-backup-payload-extraction.md) | fanuc | "backup", "payload", "vr-file", "sv-file", "kconvars", "sysvars", "cbparam", "plst-grp", "binary-parsing", "spottool" | internal
- [FANUC DO Not Found in Program — Check Reference Position](contrib/fanuc-do-not-found-in-program-reference-position.md) | fanuc | "do", "reference-position", "backgroundlogic" | robot-forum.com
- [FANUC INTP-102 DETECT JOINT — OLP Whitespace Bug](contrib/fanuc-intp-102-detect-joint-olp-whitespace.md) | fanuc | "intp-102", "detect-joint", "olp", "robodk", "whitespace" | robot-forum.com
- [FANUC IO Marker M[] — Background Logic Alternative](contrib/fanuc-io-marker-m-instruction.md) | fanuc | "marker", "m-register", "handling-tool", "vass" | robot-forum.com
- [FANUC KL: ERR_ABORT vs ERR_PAUSE 行为差异](contrib/fanuc-kl-err-abort-vs-err-pause.md) | fanuc | | bootstrap
- [FANUC KL: mm_module_h.kl 禁止 ROUTINE 声明](contrib/fanuc-kl-mm-module-h-no-routine.md) | fanuc | | bootstrap
- [FANUC Profinet 32-bit Real Value Transfer Without KAREL](contrib/fanuc-profinet-32bit-real-value-transfer.md) | fanuc | "profinet", "real-value", "32-bit", "gi-go", "plc-communication" | robot-forum.com
- [FANUC R-2000iC 检索混淆修复 — 关键词强制召回](contrib/fanuc-r-2000ic-retrieval-fix.md) | rag | | hermes_wsl
- [FFmpeg 音频转码：必须用 libopus 而非 -format ogg](contrib/ffmpeg-audio-libopus-not-ogg.md) | audio | | hanged-man
- [FReeLLMAPI Session Context Mixing - CrossThread Delivery](core/freellmapi-session-context-mixing-cross-thread-delivery.md) | agent-network | | hermes_wsl2
- [Feishu 文件上传：file_type 必须用 opus](contrib/feishu-upload-file-type-opus.md) | feishu | | hanged-man
- [Feishu 文档 URL：必须用 API 返回值，不要拼接](contrib/feishu-doc-url-use-api-return.md) | feishu | | hanged-man
- [Forum Accessibility Testing](contrib/session-lesson-2-forum-accessibility-testing.md) | ops | "scraping", "accessibility", "forum", "testing" | practical-experience
