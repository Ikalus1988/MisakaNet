# 仓库操作手册（在本仓工作的 agent）

> `AGENTS.md` 只保留**每次会话都必须知道**的红线；这里是完整细节——改代码、跑测试、
> 部署、排错时按需查阅。使用方 agent（只是来检索/贡献知识）不需要读本文件。

## 1. 环境与构建

```bash
git clone https://github.com/Ikalus1988/MisakaNet.git && cd MisakaNet
pip install -r requirements.txt        # core deps **and this checkout** (`-e .`): misakanet-core, jsonschema, mcp, pyyaml
npm install                            # devDep: wrangler（部署 worker 用）
```

- **Python ≥ 3.10**（库、脚本、stdio server 的下限；ruff 的 `target-version` 也是 `py310`）；**跑测试套件需要 3.11+**——`tests/` 里有 `import tomllib`（3.11 才进标准库），3.10 下 pytest 会在**收集阶段**就退出（`ModuleNotFoundError`，exit 2）：那不是「测试失败」，而是「一个都没跑」。CI 的必需矩阵是 3.11 / 3.12 / 3.13 × ubuntu / macos / windows。⚠️ 这个下限是**推导**出来的，**不要手写数字**：`tests/test_workflow_python_floors.py` 从 `tests/` 的导入里算出它，并断言每个跑 pytest 的 job 都不低于它（2026-09-25：`pr-checks.yml` 曾钉 3.10，于是**每个 PR** 都带着红的 auditor，3 个待合 PR 因此卡住）
- Python 侧**零外部依赖**是核心设计目标（`requirements.txt` 就那四个包）——新增依赖前先问是否必要
- **Worker 侧是纯 JS**（Cloudflare Workers，无构建步骤、无 bundler）。不要试图在 worker 里
  import Python；Python 脚本若要在 worker 复用逻辑，只能移植（见 `injection_scan.py` → worker
  的 `INTAKE_INJECTION_RULES` 这个先例）
- 需要跑测试时另装：`pip install pytest pytest-cov`
- 自检：`python3 scripts/doctor.py`（三条检查：wrangler 配置无占位符 id、`misakanet_core` 可导入、远端
  `/mcp` 能完成 MCP 握手）。两个子集标志给调用方用：`--kv-only <path>` 只查配置（部署前）、
  `--remote-only` 只探远端（部署后）——**每个检查都必须有 CI 调用点**，
  `tests/test_doctor_reach.py` 从 workflow 的命令行里反推并断言这一点（#1822）
- 动手前同步：`git pull --ff-only`（在**你的** clone 目录里执行）

### 目录导航

| 路径 | 内容 |
|---|---|
| `workers/register-proxy-sw.js` | **主 worker**（`misakanet.org` 的 `/mcp`、`/api/*`、cron）；绝大多数线上行为在这里 |
| `workers/*.test.mjs` | worker 的 `node:test` 测试（无框架依赖，直接 `node --test`） |
| `workers/email-register/` | 邮件 intake worker（独立部署） |
| `scripts/` | 维护/分析脚本（`lesson_gate.py`、`injection_scan.py`、`cf_mcp_auth.py`、`doctor.py` …） |
| `lessons/{core,contrib,en,...}/` | 课程语料（本仓的"产品"） |
| `data/` | 生成物：`lessons.json`、`leaderboard*.json` 等（`counter.json` 已于 2026-09-28 删除，连同它的镜像 workflow；那个数字的单一来源是 worker 的 D1/KV 计数器）|
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

# 改安装器（packages/misakanet-setup/**）：先跑单测，再跑**打包产物**的 e2e
node --test workers/misakanet-setup.test.mjs
npm pack --pack-destination /tmp --cache .npm-cache   # 在 packages/misakanet-setup 下
npm install -g --prefix /tmp/mn-prefix /tmp/misaka-net-misakanet-setup-*.tgz
node packages/misakanet-setup/scripts/e2e-packaged-install.mjs --prefix /tmp/mn-prefix --live

# DSH 客户端半身：真宿主 + 真浏览器的行为回归（来源门禁只看"注册了什么"，
# 这条才看"到底发生了什么"）。一次性 DSH_HOME，库请求被拦截，不依赖公网。
# 2026-10-02 起随 PR 跑（客户端半身改动才跑，判定在 job 内部）；
# 仍不在必需检查里（要装一份钉住的 DSH + Chromium）；`--keep` 会保留宿主供排查。
LD_LIBRARY_PATH=/snap/chromium/current/usr/lib/x86_64-linux-gnu \
  python3 tests/e2e/run_client_e2e.py --out /tmp/e2e-shots --keep

# 每个断言都必须能变红：--inject 会故意破坏一条承诺并要求对应检查失败
node packages/misakanet-setup/scripts/e2e-packaged-install.mjs --prefix /tmp/mn-prefix --inject leftover-temp

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

# 改了任何自动化写入（workflow 里的 git push / 落盘通道）
python3 -m pytest tests/test_no_workflow_pushes_to_main.py -q
```

**上线后（需要线上服务，不进 CI）**：检索改动合并并部署后，用同一份基准表对**线上**跑一遍，看
它和本地地板差多少——地板的语料是仓内 `data/lessons.json`（418 课、`summary+preview`），线上是 D1
的 426 课、`rich` 投影，**两者本来就不该相等**。实测 2026-09-28：线上英文 13/20 · 18/20、中文
11/22 · 14/22，对应地板 16/19 与 11/15。

```bash
python3 scripts/bench_production_recall.py            # 打印两边 + 两份语料的规模（差异的混淆项）
python3 scripts/bench_production_recall.py --json     # 机器可读
```

> 本地 `pytest` 若报 `mcp.server.mcpserver` 之类导入错误，多半是**本地依赖漂移**（本地 mcp 版本
> 与 `requirements.txt` 不符），不是代码坏了——以 CI 为准。

> **测试不得改写仓库里已发布的面**（2026-09-26）：`tests/conftest.py` 在 import 期把索引生成器的输出
> 重定向到临时目录，并在**每个测试**前后对「已发布面」（计数 SSOT 注册表里的文件 + `data/lessons.json`
> + `docs/_lessons_count.txt`）取 `(size, mtime_ns)` 快照；谁改了就以**测试 nodeid** 报错。写测试时
> 不要「快照-还原」——那会掩盖写入；要么给它一个重定向路径（env / `tmp_path`），要么把调用打桩。

### PR 上的硬阻断门禁

| 门禁 | 何时跑 | 失败原因示例 |
|---|---|---|
| **DCO** | 所有 PR | 提交缺 `Signed-off-by:`（用 `git commit --signoff`） |
| **audit** | 所有 PR | DCO 违规、secret 扫描（`scripts/check_worker_secrets.py`）、依赖审计、PR 体积超限 |
| **audit-shape**（shape guard） | 所有 PR | 在源码/测试里粘贴 diff 或 markdown；改动越出标题声称的范围 |
| **lesson-gate** | 变更 `lessons/**` | frontmatter 缺字段、标题重复、domain 不在白名单、正文 <100 字符 |
| **lesson-security** | 变更 `lessons/**` | 代码块外的危险命令；注入/污染扫描 high 级命中 |
| **tests** | 所有 PR | ubuntu/macos/windows × 3.11–3.13 任一失败 |
| **unit / e2e**（`misakanet-setup-ci.yml`） | 变更 `packages/misakanet-setup/**`、`workers/misakanet-setup.test.mjs`、`integrations/agent-autostart/**` | 安装器单测或打包产物 e2e 任一失败；某个 `--inject` 没能让对应检查变红 |
| **CodeQL** | push main + PR + 每周 | 安全查询命中 |
| `pr-agent` / `pr-genius` | 所有 PR | **非阻断**（评审参考） |

### 三类改动的标准步骤

- **改 worker**：改 `workers/register-proxy-sw.js` → `node --check` → `node --test workers/*.test.mjs`
  → 提交（DCO）→ PR → 合并后**自动部署**（`deploy-worker.yml`）
- **改 lesson**：`lessons/contrib/<name>.md`（frontmatter 必填 `title/domain/tags/status/evidence_level`，
  E0–E4）→ `lesson_gate.py` + `injection_scan.py` → PR（lesson-gate 会再跑一次）
- **改 workflow**：YAML + 内嵌 JS 双重检查 → 注意 shape guard 对 workflow 改动会标 `workflow-change`
  并要求更严格的评审 → 若这个 workflow 会往 `main` 写东西，用 `scripts/ci/land_change.py`
  （**不要**写 `git push`：ruleset 会拒，`tests/test_no_workflow_pushes_to_main.py` 也会拦住你）

## 3. 部署与数据生成

> **`main` 不能直接 push——对任何人都不行（2026-09-23 起）**。ruleset
> `23826057 main: the deterministic gates` 要求三个状态检查（`DCO / Signed-off-by`、
> `test (ubuntu-latest, 3.11)`、`gate`），且 `bypass_actors` 是**空的**：GitHub 对 push 也评估这些
> 检查，新提交没有它们就被拒。实测（用维护者自己的 PAT，同一个 token）：
> `remote: - 3 of 3 required status checks are expected.` / `! [remote rejected] main -> main`。
>
> 所以人类和自动化的固定动作都是**开 PR**：
>
> ```bash
> git commit --signoff -m "…"          # DCO 是三个必需检查之一
> git push origin HEAD:refs/heads/<branch>
> gh pr create --base main --fill       # 然后等三个必需检查变绿再合并
> ```
>
> 自动化写入**不用**手写这段：调 `scripts/ci/land_change.py`（分支 → PR → 开启 squash
> auto-merge，检查一变绿 GitHub 自己合并），完整说明与故障对照表见
> **`docs/maintainer/automation-lands-via-pr.md`**。`tests/test_no_workflow_pushes_to_main.py`
> 会拦住"又回去 push main"的 workflow。

| 对象 | 方式 | 备注 |
|---|---|---|
| `misakanet-register-proxy`（主 worker，含 `/mcp`）| **push main 自动部署** | `deploy-worker.yml`：wrangler + `workers/wrangler.toml`（含 `[triggers]` cron 定义） |
| `misakanet-web`（站点，assets = `docs/`）| **自动**：Cloudflare **Workers Builds**（Git 集成，**任何 push main 都触发**，不是 GitHub Actions） | 结果看 commit 上的 `Workers Builds: misakanet-web` check-run（由 Cloudflare app 发出，含 Version ID）；配置在 CF 控制台，不在仓库里。手工 `npx wrangler deploy`（根 `wrangler.jsonc`）只当应急/本地预览用。**这条流水线不在规则集必查项里，check-run 又不带日志与 annotations** → 它红了没人必须看：`workers-builds-watch.yml` 在它红时开 issue（标签 `site-build-red`，只报**状态变化**、不刷屏）；要读构建日志则 dispatch `cf-diagnostics`（其中 `Workers Builds` 步骤打印 trigger + 最近构建 + 失败构建的日志，凭据见 credentials 文档 §4.4/§4.5）|
| `email-register` worker | `npm run deploy:email` | 独立 worker |
| `docs/lessons/**`、`docs/topics/**`、`docs/sitemap.xml` | `python3 scripts/build_lesson_pages.py`（幂等；`--check` 是门禁） | **生成物自己的清单**是 `docs/.generated-pages.json`：脚本只会删自己生成的页面（带 `Back to MisakaNet` 标记），手写文件永不删除。接线前它没人跑，站点因此有 205/378 个课程页、88 个失效页、主题页计数停在 176（实际 330）——见 handoff-2026-09-12 |
| `data/lessons.json` | `python3 scripts/update_lessons_json.py` | **不要**用 `scripts/misakanet-index.py`：它缺 `preview/triggers/verified` 等字段，会静默回滚线上统计（#1374；CI 已有 schema 校验） |
| 公开计数：只有 `docs/index.html`（meta + 首屏降级）与两份 `llms.txt` 保留字面 | `python3 scripts/sync_lesson_count.py`（幂等）· 门禁 `--check` | 由 `update_lessons_json.py` 在每日 `update-lessons.yml` 里自动跑；其余表面（README×3、ARCHITECTURE、ROADMAP、JOIN、skill.md、integrations、`.well-known/*.json`、issue 模板…）改**指向**：GitHub 渲染的用 shields 动态徽章，其余在散文里写来源。`tests/test_lesson_count_ssot.py` 锁住"能重复刷新"、"改写就报错"、**面数上限**（8 行 / 3 文件，防止面数再长回去）与"已去数字的表面不得把数字写回来"四条不变量；要加面先改那个上限并写明理由 |
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
| 探针脚本 `403` 而同样的 `curl` 是 `200` | 边缘对 **Python urllib 的默认 UA**（`Python-urllib/3.x`）直接 403。实测 2026-09-28：同一 URL、同一段 urllib 代码，**只把 UA 换成 `misakanet-maintainer/1.0` 就从 403 变 200**（另测 `python-requests/2.31.0`、`curl/*`、空 UA 均 200，所以不是"非浏览器 UA 一律拦"）。**手搓探针一律显式设 `User-Agent`**。仓内已发布的客户端都设了（`misakanet/remote.py` 的 `misakanet-cli/*`、`scripts/site_health_check.py`、`scripts/cf_mcp_auth.py`——后者注释记的是同一类 WAF 规则），所以这是**手搓探针的坑，不是产品缺陷**；不知道这条时，一个跑满基准表的脚本会安静地每行"失败" |
| MCP 请求 `405` | 方法用错：写操作用 `POST`；SSE 长连接用 `GET` + `Accept: text/event-stream`（响应会提示正确用法） |
| 工具输出被客户端拒绝 `missing required property "value.structuredContent"` | 客户端（如 DSH/cordis harness）校验结构化输出。worker 已按 MCP 2025-06-18 同时返回 `structuredContent`；若复现，检查是否走了旧的部署版本 |
| `ImportError: cannot import name 'Client' from 'mcp'` / `No module named 'mcp.server.mcpserver'` | 本地依赖漂移（本地 mcp 版本 ≠ `requirements.txt`）。以 CI 为准；本地要复现就先按 requirements 装 |
| `npm`/`npx` 报 `EACCES ... /.npm/_cacache` | 受限环境写不了 `~/.npm`：加 `--cache ./.npm-cache` |
| `git push` 挂起 / `GnuTLS recv error (-110)` / 连接超时 | git 协议对 github.com 不稳（REST 通常仍可用）。**Git Data API 推送法**：`POST /git/blobs`（内容 base64；用 `curl --data-binary @file`，否则会 `Argument list too long`）→ `POST /git/trees`（`base_tree` = main 的 tree）→ `POST /git/commits`（parent = main head，message 带 sign-off）→ `POST /git/refs` 建分支 |
| CF MCP / MCP registry 授权反复失败 | **每个 CF MCP 产品有独立 OAuth 域**（`observability.mcp.cloudflare.com` 自带 authorize/token/register），token 绑 audience 不可混用；WSL 下浏览器回调到不了 WSL，需从地址栏抓 `code` 再手工换 token。用 `scripts/cf_mcp_auth.py` 一步完成，别手搓（详 `lessons/contrib/cloudflare-observability-mcp-oauth-separate-domain.md`） |
| **`dsh web` 在跑时用 CLI 改 profile → 插件静默不加载**：MCP 报 `server is disconnected`、该插件提供的工具/界面消失、插件页关掉再打开也**救不回来** | **运行中的宿主用 GUI 装/卸插件，CLI 只用于已停止的宿主。**`dsh plugin --profile web add …` 绕过运行中的宿主直接改 `package.json` 与 `node_modules`；实测 2026-10-01：此后宿主不再加载该插件，且 GUI 开关无法恢复（`dsh.profile.bundles` 里仍有它，容易误判为已启用）。**修复：重启 `dsh web`**（先停止旧进程；见下一条） |
| 重启 `dsh web` 报 **`dsh: startup failed: N required plugins did not activate`** 起不来 | 先抓**报错原文**再判断：宿主 stdout，或 `~/.dsh/logs/startup-*.log`（该文件顶部就写着 「Raw diagnostics …」）。已记录的两种真实原因：① **旧进程仍占着端口** → `Failed plugins (1): Error: listen EADDRINUSE: address already in use 127.0.0.1:3080`（2026-09-29 的日志实例，占端口与插件无关）；② 某个 profile bundle 的激活抛错。对②，本仓已加固：`index.js` 的 `apply()` 现在整段被守卫，默认**任何失败都不会逃出去**（只 `logger.warn`），只有显式 `failOnStartupError: true` 才抛 —— 因为激活失败会连带整个宿主起不来，而我们的最坏情况应该只是「工具没挂上」。**别把「`cordis.yml` 里没有该插件的条目」当作故障证据**：健康安装里它本来也不在那儿（2026-10-01 实测，disposable profile 同样为空） |
| wrangler 登录失败（WSL 回调不通） | 同上；CF 侧也可用 API Token（`CLOUDFLARE_API_TOKEN`）替代 OAuth 登录 |
| release-please 一直不开 release PR | 看 run 日志是否 `There are untagged, merged release PRs outstanding - aborting`：某个已合并 release PR 的标签停在 `autorelease: pending`（应为 `autorelease: tagged`），且对应 GitHub Release 缺失 |
| badge 显示 `resource not found` | shields.io endpoint badge 读的 JSON 不存在（例如 workflow 从未成功产出）。先手工补数据文件，再修 workflow |
| lesson PR 被 shape-guard 拦"markdown/diff 泄露" | 测试文件里粘了 markdown/patch。把示例移入**代码围栏**，或参考 #1604 的测试文件豁免规则 |
| issue 被莫名关闭 | 某个合并的 PR 正文/提交写了 `Closes #N`。长期开放 issue（#1550/#1258）有守护 workflow 会自动 reopen；交付报告类 PR 用 `Refs #N` |
| "站点没更新/新页面 404" | 先排除**尾斜杠误判**（无尾斜杠 → 307 不是 404）；再看 commit 上有没有 `Workers Builds: misakanet-web` check-run 及其结论/Version ID。CF Workers Builds 是**异步**的，push 完立刻 curl 可能还是旧版本。**要判断"到底冻在哪一版"**：拿一个仓库里的文件去 curl（例如 `/maintainer/credentials-and-environments.md`），逐 commit `git show <sha>:<path>` 比对，能精确定位最后一个成功部署的 commit。实测 2026-09-24：站点冻结在 `7fcebbf2a`，之后 ~25 个 commit 全部没上线 |
| 站点构建全红：日志只有三行、`Failed: The build token selected for this build has been deleted or rolled` | **不是仓库的问题，是 CF 面板里的 build token 失效了**。build token 派生自 API token，**轮换 API token 会同时作废它**（2026-09-23 那次轮换就作废了，站点因此停更一天，见 #2136）。修法：Worker → `misakanet-web` → Settings → Builds → API token 重新选/建一个 build token，然后在面板重跑一次构建；再复核站点真的变了。仓库侧无法代劳（Builds API 的写操作要 Edit 权限，且它自己就是被轮换作废的那类凭据）。完整记录见 credentials 文档 §4.5 |
| git 协议连不上 github.com | 不只是慢：实测 `Failed to connect to github.com port 443 after 134359 ms`。别手搓四步 curl 了，用 `scripts/gh_push_via_api.py --branch <br> --message-file <msg> <files>`（同一套 Git Data API，带"分支不在 base 上就拒绝"的保护）；细节见上一行 |
| **用 `gh_push_via_api.py` 推完，main 上的东西被"悄悄回退"了** | 它是**内容推送器**：写的是**本地字节**。你的工作副本只要比远端旧一次（发版、bot 改计数、别的会话在写），被推文件里**任何受管行都会被静默回退**，而分支自己是自洽的 → 分支上**没有测试能看见**。已发生过两次：发版分支的 `docs/index.html` 把徽章从 2.35.0 退回 2.34.0（只有 `test_version_consistency.py` 抓到）；`workers/register-proxy-sw.js` 那行 `x-release-please-version` 带着旧值推上去而**全绿**（测试只断言注解在不在，不断言值对不对）。**固定动作**：推之前 `python3 scripts/push_preflight.py <要推的文件...>`——它逐文件打印"**main 有而你的副本没有**"的行，并对"**措辞相同、数字不同**"的行直接判红（措辞也不同 = 正常编辑，不算回退；这条区分是它能用的原因，否则改一次计数句就会被它拦住）。另有 `--all` 给全树漂移图（**2 次 API 调用**覆盖 2200+ 个 blob，本地用 `git hash-object` 对比），它会在"main 上有而本地缺"时判红——那正是"再推就危险"的状态 |
| PR 的 CI 全卡在 `action_required`（"awaiting approval"） | **根因：分支上最后一次 push 用的是 `GITHUB_TOKEN`**（内置 token 的 push 所触发的 run 会以 `actor=github-actions[bot]` 建出来并挂起等批准）。要区分两种情况：`auto-merge-docs.yml` / `auto-sync-prs.yml` 已经改用 `SHELDON_PAT`（普通用户 push → run 正常执行）；而 **`fix-dco.yml` 一直用 `GITHUB_TOKEN` force-push**，于是"签核自动修复"这个动作本身把该 PR 的 run 全部挂起——`DCO / Signed-off-by` 是**必需**检查，挂起 = 永远停在 "Expected — waiting for status"，帮人修 DCO 反而把 PR 锁死（实测 2026-09-25，PR #2201/#2202）。已修：`fix-dco.yml` 改用 `SHELDON_PAT`，秘密为空时**只警告不 push**（挂起的 head 比红的 head 更糟——红的还能手改）。**存量已挂起的 run** 仍需人工批准：Actions 页点 "Review pending deployments"，或 `POST /repos/{owner}/{repo}/actions/runs/{run_id}/approve`（owner 权限即可，本仓实测返回 201）；先查清单：`GET /repos/{owner}/{repo}/actions/runs?status=action_required&per_page=50`。⚠️ **只批同仓分支**，fork PR 的挂起是安全边界，不要批。同一形状尚未修的还有 `adopt-pr.yml`（用 `GITHUB_TOKEN` push 并 `gh pr create`，被采纳的 PR 会没有任何 run——它至今 0 次真实使用） |
| 合并报 `Required status check "DCO / Signed-off-by" is expected`，但那个 check **是绿的** | 规则集要的是「这个必需的 context 被报过」，而**check run 与 commit status 两种形态都可能被它接受**——实测 2026-09-25 #2209：head 上 `DCO / Signed-off-by` check run 成功（补报过两次也一样），规则集仍回 `405 Repository rule violations found ... is expected.`、`mergeable_state: blocked`；用状态 API 报**同一个裁决**（`POST /repos/{o}/{r}/statuses/{sha}`，`context="DCO / Signed-off-by"`、`state=success`）立刻合并成功（200, squash）。两边的 check suite 与 check run 结构完全相同，**机制未查明**；因此 `dco-check.yml` 现在**两种形态都报**（同一裁决、同一 context），这就是为什么本仓的「合并幽灵」不该再出现。⚠️ 报 status 时必须用 check 步骤算出的 `passed` 输出，**不能**用 `steps.<id>.outcome`：那一步在 DCO 失败时也是 success（红 check 是「报告」不是「报错」），用它会把未签核的提交变成绿 context |
| 用 PAT 推分支，run 还是被挂起（`action_required`） | **`actions/checkout` 会把 `GITHUB_TOKEN` 存两处**：`http.https://github.com/.extraheader`，以及一个通过 `includeIf.gitdir:…path` 引用的 credentials 文件。只 `git config --unset-all` 掉 header **不够**——实测 2026-09-25 release PR：PAT 在 URL 里、header 也清了，那次 push 仍被算成 `github-actions[bot]`，新 head 上 13 个 run 全部挂起（含必需检查 `DCO / Signed-off-by`）。正解与 `auto-sync-prs.yml` 一致：checkout 加 **`persist-credentials: false`**，每次 push 自己带凭据——`AUTH_HEADER="AUTHORIZATION: basic $(printf 'x-access-token:%s' "$PAT" | base64 -w0)"` + `git -c http.extraheader="$AUTH_HEADER" push origin …` |
| release PR 的 DCO / audit 永远红 | release-please 生成的提交默认**不带 `Signed-off-by:`**，而 DCO 是硬门禁 → 每个 release PR 必红。`release-please-config.json` 顶层的 `signoff` 必须是**字符串** `"misakanet-bot <bot@misakanet.dev>"`（PR #1628 + `03f66f86d`）。⚠️ **不要**写成 `true`：schema 里那个 `"signoff": true` 是 JSON Schema 的**布尔子模式**（"任意值合法"），不是推荐值；填 `true` 会让 main 上每次 push 都 `release-please failed: The format of 'true' is not a valid email address with display name`（连挂四次）。改完这个文件**立刻看它自己的下一次运行**。临时救急可在 PR 里评论 `/fix-dco`（同仓 PR 会 rebase --signoff 后 force-push） |
| `leaderboard-watch` 失败：`fatal: You are not currently on a branch` + 日志里有 `CONFLICT ... data/leaderboard_meta.json` | 两次 push 间隔太近 → 两个 watch run 并发，各自提交同一份**生成物**并互相 rebase 冲突；脚本里的 `git pull --rebase ... \|\| true` 把冲突吞掉，仓库停在 detached HEAD，随即 `git push` 报上面那句。已在 workflow 加 `concurrency`（串行化）+ `-X theirs`（生成物以本次快照为准）+ 显式 `git rebase --abort` 并对失败返回非零 |
| 每日 `update-lessons.yml` 在 `Commit and push` 步骤失败：`refusing to allow a GitHub App to create or update workflow ... without \`workflows\` permission` | 该 job 的提交里含 `.github/workflows/**` 文件。`GITHUB_TOKEN` **永远**没有 `workflows` 权限（设计如此），所以"用 bot 维持 workflow 文件里的某个值"必然在值变化的那天炸——而且整个重新生成都会被丢弃。修法：把值从 workflow 里搬走，改成运行时读（如 `docs/_lessons_count.txt`，见 `pr-thank-you.yml`），或给该 job 换带 `workflows` 权限的 PAT/App（属安全决策）。计数 SSOT 已把这个文件从注册表移除并写明原因 |
| 站点课程页/主题页缺失或计数陈旧（例：`docs/topics/contrib` 写 176、实际 330） | `python3 scripts/build_lesson_pages.py --check` 看清单，再跑一次不带 `--check` 的生成。生成物由每日 job 维护；**不要手改** `docs/lessons/**`、`docs/topics/**`、`docs/sitemap.xml`（`docs.yml` 的 push 门禁会红） |
| **只加了 lesson 的 PR** 上 `test_repo_pages_match_the_index` 红，报 `generated pages drifted from data/lessons.json`，且点名的是**这个 PR 刚加的那几篇**页 | **不是页面漂移，是测试在写仓库**（2026-09-26 查明）：`tests/test_frontmatter_writers_agree.py` 把 `git push` 打桩成 `returncode=0`，而 `queue_lesson.write_lesson` 的**成功分支**会 `from update_lessons_json import main` 重建 `data/lessons.json`（并连带刷新 20+ 个受管计数面，实测一次套件跑完改写 **25 个 tracked 文件**）。于是**后运行**的页面门禁拿被改写的索引去比对 → 11 个"漂移"路径；**只在 PR 新增 lesson 时出现**，而 CI 的字母序保证每次都会撞上。**别照报错跑 `build_lesson_pages.py`**——那会把索引里根本没有的课程页提交上去，真因仍在。已修：生成器认 `MISAKANET_LESSONS_INDEX`（`conftest` import 期重定向，重定向时不同步计数面），`conftest` 另有逐测试的已发布面戳检查会点出**写入者**；`tests/test_no_test_writes_repo_data.py` 用 digest 锁住这两个方向 |
| 需要看某个脚本的用途 | `ls scripts/` + `<script> --help`；`scripts/doctor.py` 做整体自检 |
| 线上 `misakanet_search` 搜不到**今天刚合入的课**（但 `misakanet_get_lesson` 按 id 能取到）| **先看 `GET https://misakanet.org/api/search-index`**：`docCount` 是**已发布**的索引条数，`lastRefresh.corpusCount` 是**上一次刷新看到**的语料条数，两者不等就是「索引冻结」，`behindBy` 直接给出差值、`lastRefresh.reason` 给出原因（`storage write failed` = 行没写进去）。索引与语料都在一个 `kv_store` 行里，而 D1 单行上限 **2 MB**（实测生产形状的 rich 索引 1.63 MB ≈ 86% 上限），KV 兜底自 2026-09-22 起预算耗尽 → 写失败时**旧索引继续服务**、`builtAt` 冻结，而 `stale` 仍为 `false`（阈值 20 小时）。2026-09-26 实测：`docCount 411 / builtAt 08:16Z` 对 D1 里 417 篇。已改：索引 gzip+base64 存（1.63 MB → 0.24 MB），刷新结果写进**独立的** `worker_search_index_health` 行并作为 `lastRefresh` 暴露——诊断不能存放在「会写失败的那一行」里 |
| 站点/README 上的课程数对不上（例如 meta description 写 435、实际 378） | 跑 `python3 scripts/sync_lesson_count.py --check` 看漂移清单，再跑不带 `--check` 的同一命令修好。若某条报 `matched 0× ... The sentence was reworded`，说明受管句子被改写：改文件或更新脚本里的 `SITES` 注册表——**不要**把该行删掉当成"没事"（旧机制就是这么静默失效的，见脚本 docstring） |
| 需要看 worker 线上错误 | 用 `cf_mcp_auth.py` 拿 CF 凭证 → Cloudflare observability MCP 查（worker 的 `[observability]` 需启用） |

### 计数器：KV → D1（2026-09-13，#1647–#1649）

**为什么迁**：Cloudflare KV 免费档的限额按「每天写入的**不同 key** 数」计（1,000），而**同一 key 重写是豁免的**。
所以"每次调用都要新 key"的路径最先死——2026-09-12 线上实测：`misakanet_register` 报
`KV put() limit exceeded for the day.`，而同一时刻 cron 的索引重写却成功（索引 key 当天已存在）。
注册每次要写两个新 key（`node:<id>`、`mcp_token:<token>`），而**计数器在抢同一份额度**。

**现在的分工**

| 数据 | 去哪 | 说明 |
|---|---|---|
| 反爬突发窗口（每地址每分钟）、signal 限流 | **D1** `counters`（`scope='rate_read'` / `'signal_rate'`） | 单条原子 upsert，取代 KV 的 read-modify-write（旧实现存在并发下双读同一值）。**注意口径**：匿名读自 2026-09-18 起**不限次数**，这里限制的是突发、不是配额（旧文档写的「5 次/天/IP」已过期） |
| 未命中查询（gap 遥测） | **D1** `counters`（`scope='gap'`） | 原来每个不同查询一个新 key，是**最后一个无界来源** |
| 流量计数 | **KV**（`traffic:<class>:<date>`） | **有界**（每天每类几个 key），迁移无收益，刻意不动 |
| 注册节点/token、intake、pair 等 | **KV** | 这些是要**保护**的对象，不是要迁的计数器 |
| 代理缓存 | KV（TTL 300s） | 同一 key 重写，不吃新 key 额度 |

**回退**：D1 未绑定或出错时，`bumpCounter()` 回退到 KV，并**保留旧键名**（`rate:read:<ip>:<date>`、
`rate:signal:<ip>`）——回滚或未绑定部署看到的是同一批计数器。计数器失败一律 **fail open**（存储问题不该阻断读取），
并把失败计入 `/api/health` 的 `counters.failures`。

**怎么查（无需推理）**
```bash
# 只读、dispatch-only：打印各 scope 的桶数/总量/最后更新，并检查 rate_read/gap 是否有行
gh workflow run d1-counters-report.yml
# 应用 schema（幂等，只应用 workers/d1/schema.sql，不部署 worker）
gh workflow run apply-d1-schema.yml
```
`/api/health` 的 `counters` 是**每 isolate 的内存统计**：它能回答"这个 isolate 在用 D1 吗"，
不能回答"迁移生效了吗"——后者用上面那个 report。

**改 schema 时要记得**：`workers/d1/schema.sql` 与 worker 的 SQL 由不同机制改动（一个 workflow 应用、一个随代码部署），
`tests/test_d1_counters_schema.py` 会解析 schema 并断言 worker 用到的列都已声明——否则会以"请求路径上的运行期 SQL 错误"暴露。

## 5. 相关文档

- 使用方规则：`AGENTS.md`（§1–§5）+ `docs/agents/retrieval-and-contribution.md`
- 维护者流程：`docs/maintainer/intake-triage.md`（**修复后必须给报料者回执**）、
  `docs/maintainer/automation-lands-via-pr.md`（**自动化怎么把改动落到 main**：分支 → PR →
  auto-merge，含故障对照表与两个刻意不转换的 workflow）、
  `docs/maintainer/handoff-*.md`（逐轮交接与待办快照）
- **接手第一份**：`docs/maintainer/state-of-the-repo.md`（**可公开的仓库现状**：哪些自动化在飞、哪些等 owner 审批、门禁信任边界、积压形状、待 owner 拍板项、更新时机）
- 安全：`docs/agents/content-injection-defense.md`（威胁模型 + L1–L4 防护层）
- 架构与接口：`ARCHITECTURE.md`、`API.md`
