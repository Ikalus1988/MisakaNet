# 仓库操作手册（在本仓工作的 agent）

> `AGENTS.md` 只保留**每次会话都必须知道**的红线；这里是完整细节——改代码、跑测试、
> 部署、排错时按需查阅。使用方 agent（只是来检索/贡献知识）不需要读本文件。

## 1. 环境与构建

```bash
git clone https://github.com/Ikalus1988/MisakaNet.git && cd MisakaNet
pip install -r requirements.txt        # core: misakanet-core, jsonschema, mcp>=2.1.1, pyyaml
npm install                            # devDep: wrangler（部署 worker 用）
```

- **Python ≥ 3.10**；CI 跑 3.11 / 3.12 / 3.13 × ubuntu / macos / windows 矩阵
- Python 侧**零外部依赖**是核心设计目标（`requirements.txt` 就那四个包）——新增依赖前先问是否必要
- **Worker 侧是纯 JS**（Cloudflare Workers，无构建步骤、无 bundler）。不要试图在 worker 里
  import Python；Python 脚本若要在 worker 复用逻辑，只能移植（见 `injection_scan.py` → worker
  的 `INTAKE_INJECTION_RULES` 这个先例）
- 需要跑测试时另装：`pip install pytest pytest-cov`
- 自检：`python3 scripts/doctor.py`（`--kv-only` 校验 wrangler 配置里没有占位符 id）
- 动手前同步：`git pull --ff-only`（在**你的** clone 目录里执行）

### 目录导航

| 路径 | 内容 |
|---|---|
| `workers/register-proxy-sw.js` | **主 worker**（`misakanet.org` 的 `/mcp`、`/api/*`、cron）；绝大多数线上行为在这里 |
| `workers/*.test.mjs` | worker 的 `node:test` 测试（无框架依赖，直接 `node --test`） |
| `workers/email-register/` | 邮件 intake worker（独立部署） |
| `scripts/` | 维护/分析脚本（`lesson_gate.py`、`injection_scan.py`、`cf_mcp_auth.py`、`doctor.py` …） |
| `lessons/{core,contrib,en,...}/` | 课程语料（本仓的"产品"） |
| `data/` | 生成物：`lessons.json`、`counter.json`、`leaderboard*.json` 等 |
| `docs/` | 站点静态资源（`docs/` 就是 misakanet-web 的 assets 目录）+ 面向人的文档 |
| `.github/workflows/` | CI（门禁见 §2） |

## 2. 测试与门禁

### 本地必须跑的

```bash
# Python 测试（与 CI 同命令）
pytest tests/ -v --tb=short

# Worker / Node 测试（纯 node:test）
node --test workers/*.test.mjs
node --test packages/fatal-guard/tests/*.js

# 改 lesson：结构与内容门禁
python3 scripts/lesson_gate.py lessons/contrib/your-lesson.md
python3 scripts/injection_scan.py --dir lessons        # high 级发现 → 退出码 1

# 改 workflow：YAML 解析 + 内嵌 JS 语法
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/x.yml'))"
node --check <(sed -n '/script: |/,/^$/p' .github/workflows/x.yml)
```

> 本地 `pytest` 若报 `mcp.server.mcpserver` 之类导入错误，多半是**本地依赖漂移**（本地 mcp 版本
> 与 `requirements.txt` 不符），不是代码坏了——以 CI 为准。

### PR 上的硬阻断门禁

| 门禁 | 何时跑 | 失败原因示例 |
|---|---|---|
| **DCO** | 所有 PR | 提交缺 `Signed-off-by:`（用 `git commit --signoff`） |
| **audit** | 所有 PR | DCO 违规、secret 扫描（`scripts/check_worker_secrets.py`）、依赖审计、PR 体积超限 |
| **audit-shape**（shape guard） | 所有 PR | 在源码/测试里粘贴 diff 或 markdown；改动越出标题声称的范围 |
| **lesson-gate** | 变更 `lessons/**` | frontmatter 缺字段、标题重复、domain 不在白名单、正文 <100 字符 |
| **lesson-security** | 变更 `lessons/**` | 代码块外的危险命令；注入/污染扫描 high 级命中 |
| **tests** | 所有 PR | ubuntu/macos/windows × 3.11–3.13 任一失败 |
| **CodeQL** | push main + PR + 每周 | 安全查询命中 |
| `pr-agent` / `pr-genius` | 所有 PR | **非阻断**（评审参考） |

### 三类改动的标准步骤

- **改 worker**：改 `workers/register-proxy-sw.js` → `node --check` → `node --test workers/*.test.mjs`
  → 提交（DCO）→ PR → 合并后**自动部署**（`deploy-worker.yml`）
- **改 lesson**：`lessons/contrib/<name>.md`（frontmatter 必填 `title/domain/tags/status/evidence_level`，
  E0–E4）→ `lesson_gate.py` + `injection_scan.py` → PR（lesson-gate 会再跑一次）
- **改 workflow**：YAML + 内嵌 JS 双重检查 → 注意 shape guard 对 workflow 改动会标 `workflow-change`
  并要求更严格的评审

## 3. 部署与数据生成

| 对象 | 方式 | 备注 |
|---|---|---|
| `misakanet-register-proxy`（主 worker，含 `/mcp`）| **push main 自动部署** | `deploy-worker.yml`：wrangler + `workers/wrangler.toml`（含 `[triggers]` cron 定义） |
| `misakanet-web`（站点，assets = `docs/`）| **手动**：`npx wrangler deploy`（根 `wrangler.jsonc`） | 没有自动 workflow——**新页面/合规页必须记得手动部署**，否则线上 404 |
| `email-register` worker | `npm run deploy:email` | 独立 worker |
| `data/lessons.json` | `python3 scripts/update_lessons_json.py` | **不要**用 `scripts/misakanet-index.py`：它缺 `preview/triggers/verified` 等字段，会静默回滚线上统计（#1374；CI 已有 schema 校验） |
| `data/badges/*.json` | 由各 badge workflow 生成到 `data` 分支 | 例如 smithery 徽章由 `update-smithery-badge.yml` 产出 |
| 版本发布 | release-please 自动开 release PR | **不要手改** `.release-please-manifest.json`；PyPI 另走 `release-pypi.yml` 的 workflow_dispatch |
| CF MCP 凭证（查 worker 日志等）| `python3 scripts/cf_mcp_auth.py --server cloudflare-observability [--refresh\|--verify]` | 一键完成 discovery/DCR/PKCE/换 token/验证 |

### 部署后的验证习惯

- 主 worker：改完可 `curl https://misakanet.org/api/health`；MCP 改动直接发一次 JSON-RPC 探针
- 站点：`curl -sI https://misakanet.org/<新页面>/` 应 200
- 涉及 intake 的改动：提交一个明确标注的测试 intake，确认 issue 行为（创建后关闭）——参考
  issue #1621 的探针做法

## 4. 排错手册（真实踩过的坑）

| 症状 | 原因 / 处理 |
|---|---|
| MCP 请求 `403 Forbidden: invalid Origin` | 缺 `Origin` 头或值不被接受（MCP 规范要求，防 DNS rebinding）。加 `-H 'Origin: https://misakanet.org'` |
| MCP 请求 `405` | 方法用错：写操作用 `POST`；SSE 长连接用 `GET` + `Accept: text/event-stream`（响应会提示正确用法） |
| 工具输出被客户端拒绝 `missing required property "value.structuredContent"` | 客户端（如 DSH/cordis harness）校验结构化输出。worker 已按 MCP 2025-06-18 同时返回 `structuredContent`；若复现，检查是否走了旧的部署版本 |
| `ImportError: cannot import name 'Client' from 'mcp'` / `No module named 'mcp.server.mcpserver'` | 本地依赖漂移（本地 mcp 版本 ≠ `requirements.txt`）。以 CI 为准；本地要复现就先按 requirements 装 |
| `npm`/`npx` 报 `EACCES ... /.npm/_cacache` | 受限环境写不了 `~/.npm`：加 `--cache ./.npm-cache` |
| `git push` 挂起 / `GnuTLS recv error (-110)` / 连接超时 | git 协议对 github.com 不稳（REST 通常仍可用）。**Git Data API 推送法**：`POST /git/blobs`（内容 base64；用 `curl --data-binary @file`，否则会 `Argument list too long`）→ `POST /git/trees`（`base_tree` = main 的 tree）→ `POST /git/commits`（parent = main head，message 带 sign-off）→ `POST /git/refs` 建分支 |
| CF MCP / MCP registry 授权反复失败 | **每个 CF MCP 产品有独立 OAuth 域**（`observability.mcp.cloudflare.com` 自带 authorize/token/register），token 绑 audience 不可混用；WSL 下浏览器回调到不了 WSL，需从地址栏抓 `code` 再手工换 token。用 `scripts/cf_mcp_auth.py` 一步完成，别手搓（详 `lessons/contrib/cloudflare-observability-mcp-oauth-separate-domain.md`） |
| wrangler 登录失败（WSL 回调不通） | 同上；CF 侧也可用 API Token（`CLOUDFLARE_API_TOKEN`）替代 OAuth 登录 |
| release-please 一直不开 release PR | 看 run 日志是否 `There are untagged, merged release PRs outstanding - aborting`：某个已合并 release PR 的标签停在 `autorelease: pending`（应为 `autorelease: tagged`），且对应 GitHub Release 缺失 |
| badge 显示 `resource not found` | shields.io endpoint badge 读的 JSON 不存在（例如 workflow 从未成功产出）。先手工补数据文件，再修 workflow |
| lesson PR 被 shape-guard 拦"markdown/diff 泄露" | 测试文件里粘了 markdown/patch。把示例移入**代码围栏**，或参考 #1604 的测试文件豁免规则 |
| issue 被莫名关闭 | 某个合并的 PR 正文/提交写了 `Closes #N`。长期开放 issue（#1550/#1258）有守护 workflow 会自动 reopen；交付报告类 PR 用 `Refs #N` |
| 需要看某个脚本的用途 | `ls scripts/` + `<script> --help`；`scripts/doctor.py` 做整体自检 |
| 需要看 worker 线上错误 | 用 `cf_mcp_auth.py` 拿 CF 凭证 → Cloudflare observability MCP 查（worker 的 `[observability]` 需启用） |

## 5. 相关文档

- 使用方规则：`AGENTS.md`（§1–§5）+ `docs/agents/retrieval-and-contribution.md`
- 维护者流程：`docs/maintainer/intake-triage.md`（**修复后必须给报料者回执**）、
  `docs/maintainer/handoff-*.md`（逐轮交接与待办快照）
- 安全：`docs/agents/content-injection-defense.md`（威胁模型 + L1–L4 防护层）
- 架构与接口：`ARCHITECTURE.md`、`API.md`
