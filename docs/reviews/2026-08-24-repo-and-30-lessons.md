# MisakaNet 仓库 & 30 Lessons 评审报告

> 评审日期: 2026-08-24 | 基准: origin/main @ ccb03417 (v2.20.1)
> 评审人: AI 评审 agent（代码子代理深度评审 + 自动化工具 + lesson 质量清单）

---

## 一、仓库状态与拉取

- **仓库已同步**：本地 `main` 已重置对齐 `origin/main`（ccb03417, v2.20.1, 2026-08-24）。
- **背景**：本地原分支与远端历史完全分叉（本地 135 commits vs 远端 1088 commits，无共同祖先；远端历史 6 月重建过）。按用户指示"以远程为准"，本地旧历史已保全在备份分支 `backup/pre-pull-local-main`（可随时删除）。
- **遗留清理**：陈旧 rebase 状态已 `--quit`；stash（opire lesson 条目）已备份至 `/tmp/misakanet-backup/stash-opire-lesson.diff`；工作区有少量未跟踪文件（`.nodes/`、`STATUS.md` 等本地遗留）。

## 二、Aider 配置

| 项 | 值 |
|---|---|
| 版本 | aider 0.86.2（Python 3.12，安装在 `.uv-tools/bin/aider`） |
| Provider | MiniMax OpenAI 兼容端点（复用本地 Hermes Gateway key，已验证可用） |
| Model | `openai/MiniMax-M2.5` |
| 配置文件 | `.aider.conf.yml`（gitignored）+ `.env`（gitignored，存 OPENAI_API_BASE/KEY，chmod 600） |
| 验证 | `aider --message` 已成功往返（"CONFIG_OK"） |

> ⚠️ 注意：本地无 DeepSeek key（用户最初选择 DeepSeek，但本地环境实际可复用的是 MiniMax key，已按"复用本地环境"指示配置）。

## 三、仓库评审

### 3.1 总体评价

**架构意图清晰、治理机制认真，但存在"死代码冒充活功能"的维护债**。核心搜索链路（`misakanet/search/engine.py`，1046 行）质量尚可；`hub/` 已被官方 README 自己宣告 legacy 却仍以一等公民维护，开箱即崩；45 个 CI 工作流 + 82 个 Python 测试 + 8 个 JS 测试展示活跃度，但测试有效性水分不小。

### 3.2 关键发现（P1 级，8 条）

**安全/泄露类**

1. `workers/register-proxy-sw.js:504-534` — **write_lesson 内容零脱敏直发公开 GitHub issue**，token 免费注册无限流。→ 复用 redactText、逐字段限长、无 KV 拒写。
2. `workers/email-register/src/index.js:282` — 发件人完整邮箱明文进公开 issue 并明文存 KV，违反自身 intake-policy。→ 改哈希。
3. `scripts/submit_lesson.py:228,255-258` — **PAT 拼进 git remote URL + shell=True**，PAT 明文持久化进 `.git/config`；`GIT_Afailure-memory protocolASS` 变量名损坏（应为 `GIT_ASKPASS`）。→ 去 shell=True、凭据走环境变量。
4. `hub/master/master_cli.py:88,96,402` — **Master 解锁答案"贾恒龙"明文在公开源码**；token 无盐 SHA-256 存低熵 secret。→ 真正密钥交换。
5. `hub/federation/sync_protocol.py:180,239,243,248` — peer manifest 的 lesson_id 未清洗直接拼写路径 → **路径遍历任意文件写**（潜伏，仅测试调用）。
6. `scripts/verify_task.py:52-59` / `misaka_verify.py:61-68` — tasks/*.json 的 test_cmd 以 shell=True/无白名单执行 → 命令注入。
7. `scripts/build_lesson_pages.py:256` — domain 未清洗作目录名，恶意 frontmatter 可写仓库外。
8. `hub/sync/feishu_notifier.py:21` — **文件损坏**（`return Falsewebhook_url` NameError、无 class），飞书推送链路整体 ImportError。

**正确性类**

9. `misakanet/search/engine.py:267-282` — **L1 缓存键不含语料身份**（仅 query+flags），已实测复现换语料返回旧结果；长驻进程 lesson 变更不失效。
10. `hub/orchestrator/subscription.py:108` — `cursor.cursor()` 必崩（AttributeError）。
11. `hub/orchestrator/skill_indexer.py:79` — 导入路径错误 + 顶层 import torch/transformers 使 hub 无 torch 无法启动。
12. `hub/master/master_api.py:53-54` — 同步方法内 `asyncio.create_task`；add/remove_agent 空壳。

### 3.3 测试问题（P1 级）

- **3 个 fuzz 测试文件系统性 bug**：`tests/test_intake_fuzz.py`、`test_mcp_protocol_fuzz.py`、`test_search_fuzz.py` 均在导入期引用 `@given`，但 hypothesis 未安装时 try/except 吞掉 ImportError，`pytestmark = skipif` 拦不住**导入期**装饰器求值 → **整个测试套件 collection 失败**（已实测：`NameError: name 'given' is not defined`）。这是仓库 CI 最直接的破坏点。修复：安装 hypothesis，或把 @given 用法移到函数内部/加模块级防护。
- ~32 个测试用 `check()` 软断言失败不 raise（test_mcp_server.py、test_mcp_auth_contract.py、test_reputation.py），pytest 下静默通过。
- `tests/test_intake_triage.py:20-98` 测的是文件内副本函数（假测试）；`test_semantic_smoke.py:25-32` 空测试；`mcp_first_call_journey.py:26` 打真实线上 URL 且无断言。
- 覆盖率盲区：guard.py 零测试、engine.py 14+ 核心函数零引用、hub 主服务零测试、scripts/ 51/91 无测试。

### 3.4 配置/文档/依赖漂移（P2 精选）

- ARCHITECTURE.md 声称的 `reference/` 目录**不存在**（`--ref` 检索无索引源）。
- API.md 记录不存在的类/端点；README.md:205 版本号 v2.19.0 落后；版本号 6 处互相矛盾。
- requirements.txt 与 pyproject.toml 双轨漂移；`mcp` 在 uv.lock 中 0 次 → `mcp_http_server.py` 在 uv 环境必 ImportError。
- config.yaml.example 的 `storage.vector.*`、`storage.arbitration.*` 是死配置；代码读而 example 缺 `feishu.webhook_url`、`master.shared_secret`、`peers`。
- `workers/lib/redact-patterns.json:60` 信用卡正则嵌套量词 ReDoS + `[ -]` 实为字符范围（三条脱敏链共用且输入可控）。

### 3.5 亮点

1. 脱敏规则单源管理（redact-patterns.json 被 JS/Python 共享）；register-proxy-sw.js 防御最成熟（maskToken、15s 超时、Origin 白名单）。
2. `mcp_server.py:215-238` 的 lesson 路径穿越防护是教科书实现；build_sag_index.py 全参数化 SQL。
3. 知识治理机制完整：E0-E4 证据等级、lesson 质量门禁（lesson-quality.yml）、clean_pipeline 脱敏流水线。
4. 测试标杆：test_hmac_auth.py（371 行，replay/轮换/篡改全覆盖）、test_federation.py、test_intake_auto_review.py。
5. 数据层健康：`data/lessons.json` 310 条元数据字段完整、与目录零失配。

### 3.6 Top 5 行动项

1. **修 fuzz 测试 collection 崩溃**（最快见效，CI 直接红）：装 hypothesis 或重构 @given 用法。
2. **堵公开链路泄露面**：write_lesson 复用 redactText + 限长 + 无 KV 拒写；email 邮箱改哈希；修 ReDoS 正则。
3. **修提交脚本凭据处理**：submit_lesson.py 去 shell=True、PAT 不进 git URL、修 GIT_ASKPASS、master_cli token 缓存补 0600。
4. **重建 hub/ 真实性**：复活（统一 config、重写 feishu_notifier、修 skill_indexer/subscription）或按 legacy 声明整体归档。
5. **修搜索缓存正确性 + 收敛配置漂移**：L1 键加语料指纹、BM25 全路径映射；mcp/jsonschema 入 pyproject、统一版本号。

## 四、30 个 Lesson 评审

### 4.1 范围与方法

- **范围**：按 git 历史最近入库的 30 个 lesson（2026-08-04 ~ 08-23，全部在 `lessons/contrib/`）。
- **方法**：10 个子代理并行深度评审（读全文，按 6 维度打分：structure/root_cause/verify/actionability/metadata/dedup）+ 补评审 6 个 + 自动化工具交叉验证（frontmatter 解析、lint、评分脚本）。

### 4.2 总体结果

| 指标 | 值 |
|---|---|
| 平均分 | **57.1 / 100** |
| 良好 (70-84) | 3 个 |
| 及格 (55-69) | 16 个 |
| 较差 (40-54) | 8 个 |
| 不合格 (<40) | 3 个 |

> 最高 72（rag-retrieval-six-layer-silent-degradation、data-quality-three-layer-fix-pattern），最低 30（fatal-guard-cli-hardening）。**无 85+ 标杆**，整体质量中等偏下，与 8 月批量入库节奏（多批 3-7 个/天）相符——入库快但打磨不足。

### 4.3 系统性问题（跨 lesson 高频出现）

1. **frontmatter JSON+YAML 混排导致解析失败**（6/30）：`aider-api-key-leak`、`aider-litellm-model-name-rejection`、`aider-windows-unicode-error`、`bm25-vector-hybrid-search-weights`、`agent-first-node-registration-via-mcp`、`bm25-chinese-sliding-window-tuning` — JSON 对象闭合后紧跟 YAML `provenance:` 块，`json.loads()` 报 Extra data，**破坏 intake/check_lesson_quality 流水线**。
2. **缺 Verification 章节或验证不可复现**（约 20/30）：多数只有散文式断言（"验证通过"），无命令、无预期输出、无前后数据。
3. **缺 Root Cause 或根因含糊**（约 15/30）：常见"复述 Problem"而非技术机制；少数有技术性错误（如 squash-rebase-force-push-lease 把 force-with-lease 的正常拒绝说成"误判"）。
4. **去重不足**（约 12/30）：DCO、force-with-lease、BM25/RRF、mcp-intake 主题大量重叠且无交叉引用；2 个 lesson 在 `lessons/` 根目录存在**逐字重复副本**（`data-quality-three-layer-fix-pattern`、`wsl-ntfs-sqlite-update-100x-slower`，且副本 frontmatter 混排/status 冲突）。
5. **硬编码项目特定内容**：codewhale 二进制名、`C:/Users/hp/` 路径、`/home/eric_jia/.hermes/.env` 路径、真实邮箱（wrangler.jsonc:15 sheldonisspark@gmail.com）。
6. **缺 confidence 字段**（约 25/30）；部分 domain 不在规范列表（"data-engineering"、"search"）；部分未收录进 lessons/index.md。
7. **内容过薄**：多篇 < 300 词（bm25-vector-hybrid-search-weights 仅 89 词），低于质量门槛。

### 4.4 按评分分档明细

**不合格 (<40) — 建议重写或并入其他 lesson：**

| 文件 | 分 | 核心问题 |
|---|---|---|
| fatal-guard-cli-hardening.md | 30 | 无 Root Cause/Verification、无代码块、不可操作、stub |
| lesson-provenance-tracking.md | 33 | 引用的 `backfill_provenance.py` 仓库不存在、无验证 |
| aider-api-key-leak.md | 35 | frontmatter 混排、Verification 缺失、.env 未 chmod 600、论断缺证据 |

**较差 (40-54) — 需实质性修改：**

| 文件 | 分 | 核心问题 |
|---|---|---|
| bm25-vector-hybrid-search-weights.md | 44 | 非故障 lesson、仅 89 词、与 3 个既有 lesson 重复、验证全无 |
| pr-genius-issue-evaluator-for-intake.md | 47 | Root Cause 复述 Problem、硬编码 repo、验证不可复现 |
| bm25-chinese-sliding-window-tuning.md | 47 | frontmatter 混排（P0）、根因3无对应修复、验证无基线 |
| welcome-bot-mcp-intake-path.md | 50 | 代码块 yaml 标注实际是 JS、curl 与另一 lesson 逐字重复 |
| squash-rebase-force-push-lease.md | 50 | **核心论断错误**（force-with-lease"误判"）、恢复步骤自相矛盾 |
| github-actions-audit-scope-detection.md | 50 | 脚本 $SCOPE 从未赋值、门控逻辑反向、是 pr-checks.yml 已有实现的劣化副本 |
| agent-first-node-registration-via-mcp.md | 52 | frontmatter 混排、Verification 无命令 |
| search-evaluation-rank-tracking-bias.md | 52 | 引用的 evaluate_rank 仓库不存在、与 bm25 调优 lesson 疑似同源两面 |

**及格 (55-69) — 结构基本合格，补 Verification/去重即可：**

| 文件 | 分 | 核心问题 |
|---|---|---|
| yaml-inline-comment-type-coercion.md | 56 | 验证无命令、Root Cause 泛 |
| windows-ci-splitcommand-backslash-unicode-detached.md | 58 | 与既有 unicode lesson 重叠 |
| ci-security-advisory-checks.md | 58 | README 检查脚本有 bug（grep -c || echo 0 输出"0\n0"）、是 pr-checks.yml 已有实现的功能重复 |
| aider-litellm-model-name-rejection.md | 60 | 验证缺失 |
| github-contents-api-pr-pitfalls.md | 60 | 验证不可复现 |
| escrow-fee-rounding-per-provider.md | 61 | 章节名不符模板（Failure & recovery）但内容扎实 |
| remote-search-rate-limiting.md | 63 | 验证偏弱 |
| github-actions-composite-pitfalls.md | 64 | 标题名不副实、含实际代码陷阱 |
| git-worktree-dangling-commit-recovery.md | 64 | 症状与根因内部矛盾、验证缺失但恢复命令正确 |
| aider-windows-unicode-error.md | 65 | 缺 Verification、与既有 lesson 重叠 |
| dco-signoff-lost-after-force-push.md | 66 | 与 dco_signoff_force_push_pitfall.md 高度重复 |
| github-release-large-asset-download-cn.md | 66 | curl `-C -` 与 Range 头冲突、codewhale 项目噪音 |
| jieba-synonym-expansion-pitfall.md | 67 | 验证无命令、add_word 示例不严谨 |
| macos-homebrew-python-pip-install-blocked-by-pep-668-externa.md | 67 | 文件名截断、status 自相矛盾、缺验证、有根目录重复副本 |
| nodejs-missing-require-inside-try-catch.md | 68 | 缺 Verification、fallback 硬编码 /tmp |
| mcp-intake-no-account-submission.md | 66 | 验证不可复现、与 2 个 lesson 重叠 |

**良好 (70-84) — 接近标杆，小修即可：**

| 文件 | 分 | 亮点/改进点 |
|---|---|---|
| rag-retrieval-six-layer-silent-degradation.md | 72 | 六层退化分析好；**验证命令路径错误**（scripts/search_knowledge.py 不存在，实际在根目录；scripts/search_engine 不存在） |
| data-quality-three-layer-fix-pattern.md | 72 | 三层模式+Notes 极佳；**有逐字重复副本在 lessons/ 根目录** |
| wsl-ntfs-sqlite-update-100x-slower.md | 71 | 根因扎实（drvfs+WAL+NTFS 元数据）、验证可复现；**有逐字重复副本在 lessons/ 根目录** |

### 4.5 Lesson 评审 Top 行动项

1. **批量修复 6 个混排 frontmatter**：把 `provenance:` 移出 `---` 或并入 JSON，确保 `json.loads` 通过（否则 intake 流水线断）。
2. **去重 4 组**：DCO（dco-signoff-lost-after-force-push ↔ dco_signoff_force_push_pitfall）、force-with-lease 族、BM25/RRF 族、mcp-intake 族；**删除 2 个 lessons/ 根目录逐字副本**。
3. **重写或合并 3 个 <40 分 lesson**；修正 squash-rebase-force-push-lease 的错误技术论断。
4. **为全部 30 个补 Verification 章节**（可执行命令 + 预期输出），其中 2 个引用了仓库不存在的脚本/函数（backfill_provenance.py、evaluate_rank），需指向真实实现或改写作弊。
5. **补 confidence 字段 + 收录 index.md**；删除硬编码路径/用户名/邮箱（<placeholder> 化）。

---

## 五、已执行修复（2026-08-25）

> 基于本报告的 Top 行动项，已完成 3 项低风险、无争议的修复，均验证通过：

### ✅ 修复 1：3 个 fuzz 测试文件 collection 崩溃（P1）
- **文件**：`tests/test_intake_fuzz.py`、`test_mcp_protocol_fuzz.py`、`test_search_fuzz.py`
- **问题**：hypothesis 未安装时，`@given`/`@settings` 装饰器在模块导入期即被求值，直接 NameError → 整个测试套件 collection 失败（`pytestmark = skipif` 拦不住导入期错误）
- **修复**：except 分支提供 no-op stub（given/settings 返回原函数，st 为链式 stub，HealthCheck 含 too_slow）
- **验证**：修复前 collection 崩溃（NameError），修复后 824 个测试全部收集、3 个 fuzz 文件正确 skip

### ✅ 修复 2：6 个 lesson 混排 frontmatter（破坏 intake 流水线）
- **文件**：aider-api-key-leak、aider-litellm-model-name-rejection、aider-windows-unicode-error、bm25-vector-hybrid-search-weights、bm25-chinese-sliding-window-tuning、agent-first-node-registration-via-mcp
- **问题**：JSON frontmatter 闭合 `}` 后混入 YAML `provenance:` 块 → `json.loads()` 报 Extra data
- **修复**：provenance 块移出 frontmatter 到正文（带注释标记），frontmatter 保持纯 JSON
- **验证**：6 个全部 JSON 可解析、字段完整、正文零丢失、`check_lesson_quality.py` 0 错误 0 警告；全库 lint medium 从 55 → 37

### ✅ 修复 3：删除 2 个重复 lesson 副本
- **文件**：`lessons/data-quality-three-layer-fix-pattern.md`、`lessons/wsl-ntfs-sqlite-update-100x-slower.md`（根目录遗留）
- **依据**：与 `lessons/contrib/` 对应文件正文逐字一致（已 diff 验证），且 `data/lessons.json` 已指向 contrib 版本
- **验证**：`data/lessons.json` 引用完整性 0 缺失

### ⏳ 待处理（按优先级）
1. **安全类 P1**：write_lesson 零脱敏直发公开 issue、email 邮箱明文、submit_lesson.py PAT 拼 git URL
2. **hub/ 重建**：feishu_notifier.py 损坏文件、skill_indexer 导入错误、subscription cursor() 崩溃
3. **搜索缓存正确性**：engine.py L1 缓存键加语料指纹
4. **配置/依赖漂移**：mcp 入 pyproject、版本号统一、config.yaml.example 补键

---

## 六、附录

- 评审产物位置：本报告 `docs/reviews/2026-08-24-repo-and-30-lessons.md`
- 30 个 lesson 清单：`/tmp/recent-30-lessons.txt`
- 自动化数据：lint（55 medium / 0 high）、frontmatter 检查、score_lessons 脚本评分
- 子代理评审：代码质量 1 个（约 60 文件精读 + 实测复现）、lesson 评审 11 个
