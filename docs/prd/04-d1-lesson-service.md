# PRD ④ D1 Lesson 服务化 —— 核心资产从仓库到服务

- **状态**: ✅ **已上线（2026-08-28）** · 优先级: 🔴 高（战略核心）· 工作量: 中（3-5 天）
- **创建**: 2026-08-28 · 维护: MisakaNet

> **进度（2026-08-28 完成，D1 已创建并部署）**：
> - ✅ D1 schema：`workers/d1/schema.sql`（lessons 表 + lesson_sync_log 台账）
> - ✅ sync 脚本：`scripts/sync_lessons_to_d1.py`（314 lessons 可解析；JSON+YAML
>   frontmatter；`--sql/--dry-run/--execute/--reconcile/--prune`；幂等 upsert；
>   经 `--file` 传 SQL 规避 32KB argv 限制）
> - ✅ Worker 双源：`loadLessons()` 优先 D1、回退 GitHub/KV（search/preflight/
>   /api/lessons/get_lesson 零停机切换）
> - ✅ **D1 数据库已创建**：`misakanet-db`（b9adbe87-6bbf-4d2f-ae56-41c3487b2831），
>   database_id 已回写 `workers/wrangler.toml` 并部署
> - ✅ CI：`.github/workflows/d1-bootstrap.yml`（幂等 bootstrap）+ `sync-d1.yml`
>   （增量/每日，DB 自愈重建）
> - ✅ 测试：`workers/d1-lesson-service.test.mjs`（12 用例）、
>   `workers/mcp-anonymous-read.test.mjs`（4 用例）、
>   `workers/mcp-no-match.test.mjs`（4 用例）
> - ✅ **愿景偏差修复**（2026-08-28）：
>   - **匿名读**：search/get_lesson 免认证（PR #1121 的 rate limit 此前从未
>     对匿名用户生效——在 auth 之后才执行；现放行 + 共享 5 次/天/IP 配额）
>   - **结构化查询**：`/api/lessons?domain=&status=&tag=&id=&limit=` 真 SQL 过滤
>   - **CLI 远程化**：`search_knowledge.py --remote` 直查 D1（免 clone、
>     免本地配额；`--local` 保持原行为）；AGENTS.md 已把 `--remote` 列为首选
> - ✅ **生产验证**（2026-08-28）：
>   - `GET /api/lessons` 免认证直查 → 314 lessons；`?domain=rag` → 9 行
>   - 匿名 `misakanet_search` / `misakanet_get_lesson` → 成功；配额触发限流
>   - `search_knowledge.py --remote` → 314 docs BM25 排名正常
>   - 幂等：重跑 sync 后仍 314 行、无重复；reconcile 零差异
> - ⏳ 后续：llms-full.txt / agent-card D1 数据驱动、FTS5 全文检索、统计看板

## 1. 背景与问题

lesson 是 MisakaNet 的核心资产，当前存储在 GitHub 仓库（Git-backed），查询依赖 GitHub API/raw 代理（需 token 或公开 raw）。关键缺陷：

- **必须 git clone 或走 GitHub 代理**才能访问 lesson（对 agent 有门槛）
- 数据更新依赖 data sync（GitHub Actions 快照），非实时
- 无法结构化查询（按 domain/tags/质量/时间过滤）
- 仓库=服务耦合，未来服务能力（统计/检索/推荐）受限于 Git 结构

**洞察**：lesson 应"服务化" —— Cloudflare **D1（SQLite）** 作为查询层，仓库保留为"源 + 审核"。

## 2. 目标

- lesson 全量入 D1，成为**免 clone、免注册、HTTP/MCP 直查**的服务
- 查询实时（发布即查）、结构化（SQL 过滤）
- 仓库仍为权威源（Git 历史/审核/贡献），D1 为服务层（同步）

## 3. 需求细节

### 3.1 数据模型（D1 表）

```sql
CREATE TABLE lessons (
  id TEXT PRIMARY KEY,          -- slug
  title TEXT NOT NULL,
  domain TEXT,
  status TEXT DEFAULT 'published',
  language TEXT,
  tags TEXT,                    -- JSON array
  path TEXT,                    -- repo path
  problem TEXT,                 -- 前 2000 字符
  root_cause TEXT,
  solution TEXT,
  verification TEXT,
  content_md TEXT,              -- 完整 markdown
  frontmatter TEXT,             -- 原始 frontmatter JSON
  updated_at TEXT,
  created_at TEXT
);
CREATE INDEX idx_lessons_domain ON lessons(domain);
CREATE INDEX idx_lessons_status ON lessons(status);
CREATE INDEX idx_lessons_updated ON lessons(updated_at);
```

### 3.2 同步

- 触发：lesson 合入 main（GitHub Actions）或定时（每日）
- 逻辑：parse lessons/*.md → upsert D1（幂等，按 id）
- 增量：仅同步变更（git diff 检测）

### 3.3 查询服务

- MCP `misakanet_search` → 查 D1（替代 GitHub raw 代理）：SQL LIKE/BM25（SQLite FTS5 可选）
- `misakanet_get_lesson` → D1 按 id 取
- HTTP：`/api/lessons` → D1（实时，替代 GitHub 快照）
- llms-full.txt / agent-card → D1 数据驱动

### 3.4 非功能需求

- 免认证公开读（与现状一致）+ 限流
- 脱敏（内容已脱敏，同步时校验）
- 一致性：仓库与 D1 可对账（checksum）

## 4. 技术方案

```
GitHub 仓库（源/审核）→ sync workflow/action → D1（服务层）→ MCP/HTTP/WebMCP
依赖：
- D1 database（Cloudflare）
- workers/ 绑定 D1（new binding）
- sync 脚本（scripts/sync_lessons_to_d1.py 或 workflow）
```

## 5. 验收标准

- [x] D1 表建好，312+ lesson 全量同步成功（可对账）—— **314 lessons 同步，可对账（checksum）**
- [x] `misakanet_search` 查 D1 返回结果（与 GitHub 代理结果一致）—— **已验证（source=worker-search）**
- [x] `/api/lessons` 从 D1 实时返回（发布新 lesson 后立即可见，无需等 data sync）—— **已验证（免认证直查 314 条）**
- [x] 免认证 HTTP 直查（curl 无 token 成功）—— **已验证**
- [x] 增量同步幂等（重跑不重复）—— **已验证（重跑后仍 314 行）**

## 6. 战略价值（为何"放 D1 而非仓库"）

| 维度 | 仓库（现状） | D1（目标） |
|------|-------------|-----------|
| 访问 | git clone / GitHub 代理 | **HTTP/MCP 直查（免 clone）** |
| 实时性 | data sync 快照（滞后） | **发布即查** |
| 查询 | 文件系统/全文扫描 | **SQL 结构化过滤** |
| 门槛 | 需 GitHub 访问 | **免注册、免认证** |
| 扩展 | 受 Git 结构限制 | **服务能力（统计/推荐/分析）** |

## 7. 依赖

- Cloudflare D1（Workers Paid？免费额度需验证）
- Worker D1 binding + 部署
- 同步机制（Actions 或 Workflows）

## 8. 后续增强

- SQLite FTS5 全文检索（替代/增强 BM25）
- lesson 统计/质量看板（D1 聚合）
- 推荐系统（同 domain/tags 关联）
- 与 PRD ③ Workflows 集成（草稿 → D1 → 审核 → 发布）
