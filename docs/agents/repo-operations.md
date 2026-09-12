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

# 改了任何公开计数 / 站点文案：计数 SSOT 门禁（快，无依赖）
python3 scripts/sync_lesson_count.py --check

# 改了 lesson / data/lessons.json：生成页面门禁（课程页/主题页/sitemap 是否与索引一致）
python3 scripts/build_lesson_pages.py --check    # 不一致时：跑不带 --check 的同一命令

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

> 推 main 的固定动作：**先 commit**（有未提交改动时 `git rebase` 会被直接拒绝）→
> `git fetch origin main` → `git rebase origin/main` → `git push`。远端有 bot 提交
> （leaderboard 快照等）时几乎必然需要 rebase，别直接 push。

| 对象 | 方式 | 备注 |
|---|---|---|
| `misakanet-register-proxy`（主 worker，含 `/mcp`）| **push main 自动部署** | `deploy-worker.yml`：wrangler + `workers/wrangler.toml`（含 `[triggers]` cron 定义） |
| `misakanet-web`（站点，assets = `docs/`）| **自动**：Cloudflare **Workers Builds**（Git 集成，**任何 push main 都触发**，不是 GitHub Actions） | 结果看 commit 上的 `Workers Builds: misakanet-web` check-run（由 Cloudflare app 发出，含 Version ID）；配置在 CF 控制台，不在仓库里。手工 `npx wrangler deploy`（根 `wrangler.jsonc`）只当应急/本地预览用 |
| `email-register` worker | `npm run deploy:email` | 独立 worker |
| `docs/lessons/**`、`docs/topics/**`、`docs/sitemap.xml` | `python3 scripts/build_lesson_pages.py`（幂等；`--check` 是门禁） | **生成物自己的清单**是 `docs/.generated-pages.json`：脚本只会删自己生成的页面（带 `Back to MisakaNet` 标记），手写文件永不删除。接线前它没人跑，站点因此有 205/378 个课程页、88 个失效页、主题页计数停在 176（实际 330）——见 handoff-2026-09-12 |
| `data/lessons.json` | `python3 scripts/update_lessons_json.py` | **不要**用 `scripts/misakanet-index.py`：它缺 `preview/triggers/verified` 等字段，会静默回滚线上统计（#1374；CI 已有 schema 校验） |
| 全站公开计数（README / ARCHITECTURE / 站点 meta / issue 模板 …） | `python3 scripts/sync_lesson_count.py`（幂等）· 门禁 `--check` | 由 `update_lessons_json.py` 在每日 `update-lessons.yml` 里自动跑；新增/改写受管句子后要同步更新脚本里的 `SITES` 注册表，`tests/test_lesson_count_ssot.py` 会锁住"能重复刷新"与"改写就报错"两条不变量 |
| `data/badges/*.json` | 由各 badge workflow 生成到 `data` 分支 | 例如 smithery 徽章由 `update-smithery-badge.yml` 产出 |
| 版本发布 | release-please 自动开 release PR | **不要手改** `.release-please-manifest.json`；PyPI 另走 `release-pypi.yml` 的 workflow_dispatch |
| CF MCP 凭证（查 worker 日志等）| `python3 scripts/cf_mcp_auth.py --server cloudflare-observability [--refresh\|--verify]` | 一键完成 discovery/DCR/PKCE/换 token/验证 |

### 部署后的验证习惯

- 主 worker：改完可 `curl https://misakanet.org/api/health`；MCP 改动直接发一次 JSON-RPC 探针
- 站点：`curl -sI https://misakanet.org/<新页面>/` 应 200
  - **注意尾斜杠**：目录式路径 `curl .../privacy` 会返回 **307**（跳 `/privacy/`），这不是 404。
    判断"页面没上线"前先加 `-L` 或补上尾斜杠，否则会得出错误结论（本仓真实踩过）
  - 静态 md（如 `docs/agents/repo-operations.md`）会直接以 `/agents/repo-operations.md` 提供，
    是检验"push 后站点是否真的重新部署了"的最快探针
- 涉及 intake 的改动：提交一个明确标注的测试 intake，确认 issue 行为（创建后关闭）——参考
  issue #1621 的探针做法

## 4. 排错手册（真实踩过的坑）

| 症状 | 原因 / 处理 |
|---|---|
| MCP 请求 `403 Forbidden: invalid Origin` | **值不被接受**（MCP 规范要求，防 DNS rebinding）。实测 2026-09-12：**缺席=200 放行**，只有带**非法值**（如 `https://evil.example.com`）才 403——别把「没带」当成故障在查；照标准写法带 `-H 'Origin: https://misakanet.org'` 即可 |
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
| "站点没更新/新页面 404" | 先排除**尾斜杠误判**（无尾斜杠 → 307 不是 404）；再看 commit 上有没有 `Workers Builds: misakanet-web` check-run 及其结论/Version ID。CF Workers Builds 是**异步**的，push 完立刻 curl 可能还是旧版本 |
| git 协议连不上 github.com | 不只是慢：实测 `Failed to connect to github.com port 443 after 134359 ms`。别手搓四步 curl 了，用 `scripts/gh_push_via_api.py --branch <br> --message-file <msg> <files>`（同一套 Git Data API，带"分支不在 base 上就拒绝"的保护）；细节见上一行 |
| PR 的 CI 全卡在 `action_required`（"awaiting approval"） | 该 PR 分支最近被 **bot 推过**（`Auto-Merge Docs PRs` 把 main 合进分支、`/fix-dco` 的 force-push 等）——这类 run 会挂起等人工批准。批准：Actions 页点 "Review pending deployments"，或 `POST /repos/{owner}/{repo}/actions/runs/{run_id}/approve`（owner 权限即可，本仓实测返回 201）。**注意**：bot 每再推一次都会重新挂起，批完要再确认一次 |
| release PR 的 DCO / audit 永远红 | release-please 生成的提交默认**不带 `Signed-off-by:`**，而 DCO 是硬门禁 → 每个 release PR 必红。`release-please-config.json` 顶层的 `signoff` 必须是**字符串** `"misakanet-bot <bot@misakanet.dev>"`（PR #1628 + `03f66f86d`）。⚠️ **不要**写成 `true`：schema 里那个 `"signoff": true` 是 JSON Schema 的**布尔子模式**（"任意值合法"），不是推荐值；填 `true` 会让 main 上每次 push 都 `release-please failed: The format of 'true' is not a valid email address with display name`（连挂四次）。改完这个文件**立刻看它自己的下一次运行**。临时救急可在 PR 里评论 `/fix-dco`（同仓 PR 会 rebase --signoff 后 force-push） |
| `leaderboard-watch` 失败：`fatal: You are not currently on a branch` + 日志里有 `CONFLICT ... data/leaderboard_meta.json` | 两次 push 间隔太近 → 两个 watch run 并发，各自提交同一份**生成物**并互相 rebase 冲突；脚本里的 `git pull --rebase ... \|\| true` 把冲突吞掉，仓库停在 detached HEAD，随即 `git push` 报上面那句。已在 workflow 加 `concurrency`（串行化）+ `-X theirs`（生成物以本次快照为准）+ 显式 `git rebase --abort` 并对失败返回非零 |
| 每日 `update-lessons.yml` 在 `Commit and push` 步骤失败：`refusing to allow a GitHub App to create or update workflow ... without \`workflows\` permission` | 该 job 的提交里含 `.github/workflows/**` 文件。`GITHUB_TOKEN` **永远**没有 `workflows` 权限（设计如此），所以"用 bot 维持 workflow 文件里的某个值"必然在值变化的那天炸——而且整个重新生成都会被丢弃。修法：把值从 workflow 里搬走，改成运行时读（如 `docs/_lessons_count.txt`，见 `pr-thank-you.yml`），或给该 job 换带 `workflows` 权限的 PAT/App（属安全决策）。计数 SSOT 已把这个文件从注册表移除并写明原因 |
| 站点课程页/主题页缺失或计数陈旧（例：`docs/topics/contrib` 写 176、实际 330） | `python3 scripts/build_lesson_pages.py --check` 看清单，再跑一次不带 `--check` 的生成。生成物由每日 job 维护；**不要手改** `docs/lessons/**`、`docs/topics/**`、`docs/sitemap.xml`（`docs.yml` 的 push 门禁会红） |
| 需要看某个脚本的用途 | `ls scripts/` + `<script> --help`；`scripts/doctor.py` 做整体自检 |
| 站点/README 上的课程数对不上（例如 meta description 写 435、实际 378） | 跑 `python3 scripts/sync_lesson_count.py --check` 看漂移清单，再跑不带 `--check` 的同一命令修好。若某条报 `matched 0× ... The sentence was reworded`，说明受管句子被改写：改文件或更新脚本里的 `SITES` 注册表——**不要**把该行删掉当成"没事"（旧机制就是这么静默失效的，见脚本 docstring） |
| 需要看 worker 线上错误 | 用 `cf_mcp_auth.py` 拿 CF 凭证 → Cloudflare observability MCP 查（worker 的 `[observability]` 需启用） |

## 5. 相关文档

- 使用方规则：`AGENTS.md`（§1–§5）+ `docs/agents/retrieval-and-contribution.md`
- 维护者流程：`docs/maintainer/intake-triage.md`（**修复后必须给报料者回执**）、
  `docs/maintainer/handoff-*.md`（逐轮交接与待办快照）
- 安全：`docs/agents/content-injection-defense.md`（威胁模型 + L1–L4 防护层）
- 架构与接口：`ARCHITECTURE.md`、`API.md`
