# MisakaNet 维护手册（maintenance）

> 审计 2026-09-05（T3.2 / T3.4）：scripts 命名与破坏性操作、归档治理、可再生成数据清单。
> 配套：`docs/CI.md`（workflow 索引）、`.audit-reports-20260905/`（审计与执行记录，gitignore 本地保留）。

## 1. scripts/ 命名与破坏性操作分类

现状（2026-09-05 快照）——带 `auto_` / `fix_` 前缀的脚本**只改写本地工作树文件**，
不含 git commit/push、gh、或网络写回（grep 校验 0 命中）：

| 脚本 | 作用 | 破坏性 | 建议 |
|---|---|---|---|
| `fix_frontmatter.py` | 修复损坏的 lesson frontmatter（`--fix` 才写） | 本地改写 | 保留 |
| `fix_frontmatter_mix.py` | 混合/旧格式 frontmatter 修复 | 本地改写 | 保留 |
| `fix_verification.py` | 补 Verification 段落 | 本地改写 | 保留 |
| `fix_lesson_quality_v2.py` | 按评分器批量提升 lesson 质量 | 本地改写 | 保留 |
| `auto_fix_lessons.py` | 自动修 lesson（面向 CI 反馈） | 本地改写 | 重命名候选 → `write_fix_lessons.py` |

**命名政策（新增代码遵守）**：
- 只读分析类：`audit_*` / `check_*` / `inspect_*` / `_dry` 参数
- 会改写仓库文件的脚本：前缀 `write_*` 或 `mutate_*`，默认 `--dry-run`，显式 `--apply/--fix` 才写
- 会触碰远端（git push / gh / 网络写）的脚本：前缀 `submit_*` / `sync_*`，必须在 docstring 声明
  需要哪些凭据（见 `scripts/sync_lessons_to_d1.py` 头部示例）

> 重命名 `auto_fix_lessons.py` 需先确认无 workflow/脚本引用（本次审计未发现引用，但仍建议
> 在独立 PR 中连同引用检查一起做）。

## 2. 归档与数据治理

### lessons/_archive（退役区，不入索引）
- **2026-09-05 已全部清理**（产品决策，git rm 共 50 篇）：
  - 4 个损坏半导入顶层条目（`context-compaction-*` ×2、旧版 `feishu-bot-setup-complete`、`system-note-...`）
  - 3 个归档子目录 46 篇（`conversation-dumps/` 1、`hook-raw/` 2、`skill-harvest/` 43）——
    均为 2026-08-23 批量导入的自动化产物（`contributor: Unknown`、`metadata-normalized`、
    draft/archive domain、skill-pipeline/bootstrap 来源），不入索引、非人工策展；git 历史可回溯，
    源内容仍在本地 openclaw/cc-haha/skills 源中。
- 今后请勿向 `_archive/` 新增文件（该目录在 `misakanet/lesson_index.py` 中作为脚手架排除）。

### 可再生成数据（不要手改，改源后跑脚本）
| 文件 | 生成方式 |
|---|---|
| `data/lessons.json` | `python3 scripts/update_lessons_json.py`（canonical 358 条，唯一 id） |
| `docs/_lessons_count.txt` | 同上（`{{LESSONS_COUNT}}` 占位符替换） |
| `data/okf/lessons.jsonl` | `python3 scripts/export_okf.py`（SAG/OKF 数据源） |
| `data/sag.db` | `python3 scripts/build_sag_index.py`（构建模式） |
| `docs/data/lessons.json` 等站点镜像 | 由 `sync-data.yml` 推送数据分支后刷新 |

### 可见性/去重政策（用户决策 2026-09-05）
- 索引 = 图书馆：core/contrib + 语言副本独特内容 + 生命周期目录**全部可见**
- 镜像/翻译副本（如 `en/` 与 core/contrib 同 stem 的 29 篇）**不进索引**（`misakanet/lesson_index.py::canonical_lessons`），
  文件保留、按路径可取；避免搜索结果重复
- `templates/`（脚手架）与 `_archive/`（退役）永不索引；`lesson_gate.py` 单独负责 PR 编辑门禁（含镜像目录）

## 3. 例行清理清单（发布前 5 分钟）
1. `git status` 无意外 untracked（历史垃圾目录已被 `.gitignore` + `scripts/hygiene_check.sh` 拦截）
2. `python3 scripts/update_lessons_json.py` 刷新计数；`make doctor` 全绿（或明确记录唯一失败项）
3. 数据分支镜像与 D1 与仓库一致：跑一次 `sync-d1.yml`（`workflow_dispatch`），`--reconcile` 对比
4. 删除本地临时物：`scripts/mhs_watch*` 等会话残留若不再使用可移除；`.audit-reports-*/` 已 gitignore，按需归档到 `~/audit_reports`
5. 大改后跑：`python3 -m pytest tests/test_lesson_index_discovery.py tests/test_version_consistency.py -q`

## 4. 相关决策记录
- 版本双线（registry 2.27.x vs PyPI 2.23.x）为刻意设计，见 `docs/maintainer/handoff-2026-09-05.md`；
  `tests/test_version_consistency.py` 锁两条线内部不变量
- 每日 `update-lessons.yml` 提交 `data/lessons.json` + 计数标记文档；`sync-d1.yml` 每日同步 D1（canonical 358）

## 5. 版本通道（audit T2.1 统一后的策略）

MisakaNet 有**三条刻意分开、节奏独立的版本通道**（不要试图合并成单个数）：

| 通道 | 载体 | 现状(2026-09-05) | 何时 bump |
|---|---|---|---|
| **registry 线** | `server.json`/`glama.json` `version` + API.md/JOIN.md 声明 | 2.27.1 | 每次发版 tag 后“对齐”（随 handoff 流程） |
| **repo release 线** | `pyproject.toml` + `.release-please-manifest.json`（release-please python 型随发版 bump）+ README `misakanet@` 声明 | 2.27.1 | 每次发版（release-please/tag） |
| **npm bundle 线** | `package.json` | 2.23.1（npm 已发布 2.23.0） | 仅 DSH skill bundle 实际发布 npm 时（允许滞后于 release 线） |
| **pypi 通道** | server.json pypi entry == pyproject；PyPI 实况 2.18.0（上传已滞后） | 2.27.1 | 真正发布 PyPI 时 |

统一方式 = **单一工具 + 不变量门禁**，不再手改多处：

```bash
python3 scripts/align_versions.py --check                 # 门禁：R1-R5 不变量
python3 scripts/align_versions.py --registry 2.28.0       # 升 registry 线（server/glama/API/JOIN 一次完成）
python3 scripts/align_versions.py --source 2.24.0         # 升 source 线（pyproject/package/manifest/README）
make check-versions                                       # 等价的 Makefile 入口（建议 CI 用）
```

不变量（R1-R5，与 tests/test_version_consistency.py 一致）：registry 对等；
source 线 package==manifest；pypi 源线 pyproject==server pypi entry；pyproject 允许滞后于 manifest；
文档声明不得超过当前上限。PyPI 实况可用 `scripts/align_versions.py --check` 输出对照 pypi.org 人工核对。

## 6. Dependabot 排查记录（2026-09-05）

GitHub 提示默认分支 4 条开放告警（2 critical + 2 high）。沙箱无法读 API（git 凭据无 REST 权限，401），
以下为本机可验证的排查结论：

- **npm（root）**：`npm audit` → 0 漏洞；devDependency `wrangler ^4.127.0` 干净（overrides: sharp 0.35.3）。
- **npm（packages/fatal-guard）**：`npm audit` → 0 漏洞。
- **pip 顶层直接依赖**（requirements.txt / pyproject，含可选 hub extras）：OSV batch 查询
  mcp/jsonschema/pyyaml/misakanet-core/chromadb/aiohttp/websocket-client/networkx/numpy/keyring/
  requests/scrapling/sentence-transformers → **无 critical/high**。
- **GitHub Actions**：inventory 显示均用较新版本（checkout@v7、setup-python@v7、github-script@v9、
  codeql-action@v4、stale@v11 等）；`tj-actions/changed-files@v47.0.6`、`release-please-action@v5`、
  `pypa/gh-action-pypi-publish@release/v1` 为 tag 引用（建议 SHA pin，但非安全告警本身）。
- 推断剩余告警来源：`uv.lock` 传递依赖（dependabot 现支持 uv）或某个未覆盖的 Actions。
  待维护者在 GitHub Security → Dependabot 页粘贴 4 条明细后逐条修复；修复路径模板：
  pip/uv → 升级对应约束 + `uv lock`；npm → `npm audit fix` 后提交 lock；actions → 升到已修复版本或 SHA pin。

**2026-09-05 修复（告警明细确认后）：4 条告警全部为 `chromadb`（pip · uv.lock）——
GHSA-2wm9（高, 租户越权）、GHSA-36p7（严重, 代码注入）、GHSA-f4j7（严重, 预认证代码注入）、
GHSA-xph7（高, RBAC 范围）。`last_affected = 1.5.9` 即 PyPI 最新版，上游无修复。
本仓库零 chromadb import（仅 pyproject hub extras 遗留声明）→ 已从 `hub` extras 移除并 `uv lock`
（lock -1806/+37 行），4 条告警在推送后自动关闭；外部 hub 包如确需 chromadb 由其自身清单声明。

## 7. dsh bundle（插件/工具集成，2026-09-05）

MisakaNet 现已声明 `dsh.bundle`（`package.json` + `cordis.patch.yml`），作为 dsh 插件的
默认行为：

- **git+ 安装**（`dsh plugin add git+https://github.com/Ikalus1988/MisakaNet.git`）：
  patch 行 `misakanet-mcp` 以 stdio 启动仓库自带 `scripts/mcp_server.py`，向 profile 提供
  `mcp__misakanet__misakanet_search / get_lesson / …` 工具（本地、无限额）。
- **npm 安装**（skill-only，不含 python）：该行 `failOnStartupError: false` 静默断开，
  仅提供 skill/CLI 面——要实时工具请改用 git+ 安装。

### 远端接入示例（npm 用户可选）

把下面行追加到你 profile 的用户 patch（如 `~/.dsh/profiles/web/cordis.patch.yml`），
让 `dsh-mcp-client` 直连远端（无需本地 python；token 需在 https://misakanet.org 注册）：

```yaml
- insert:
    - id: misakanet-remote
      name: '@deepseek-ai/dsh-mcp-client'
      config:
        transport: streamable-http
        serverName: misakanet-remote
        url: https://misakanet.org/mcp
        headers:
          Authorization: 'Bearer YOUR_MISAKANET_TOKEN'
        failOnStartupError: false
```

> 命名空间提示：`serverName` 唯一（`misakanet` 已被默认本地行占用，远端用
> `misakanet-remote`），工具名会以 `mcp__misakanet-remote__*` 出现。
> 契约测试：`tests/test_dsh_bundle.py`（随 PR #1484 合入 main；patch 声明/单行/字段/全局唯一 id）。
