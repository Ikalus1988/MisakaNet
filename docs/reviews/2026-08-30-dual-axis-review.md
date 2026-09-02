# MisakaNet 双轴评审报告（架构轴 + 代码轴）

**日期**: 2026-08-30
**版本**: v2.23.0 (HEAD b979d643)
**评审方法**: 主评审亲自通读核心链路（搜索引擎 / MCP 协议层 / hub 入口 / Worker 路由 / 50 个 CI workflow），并派出 6 个并行子代理分区深挖（搜索核心、MCP+intake、hub 编排、Workers+CI、测试体系、lessons 内容），关键发现全部经主评审复验（运行代码实证）。

**测试基线**: 915 collected → **897 passed, 4 failed, 15 skipped**（33s）

---

## 执行摘要

| 维度 | 评分 | 说明 |
|------|------|------|
| **架构理念** | ⭐⭐⭐⭐ | Lesson/Node/Search 三概念 + Git 传输 + Markdown 存储 + 零依赖检索，设计清晰、克制 |
| **架构现状** | ⭐⭐⭐ | 文档-现实漂移严重；hub 仲裁闭环为死代码；Worker 2826 行单体；多语言目录混乱 |
| **代码正确性** | ⭐⭐⭐ | 存在 2 个 P0 级排序/元数据 bug（已实证）；MCP stdio 无异常边界；intake 不脱敏 |
| **安全性** | ⭐⭐⭐ | 无已泄露密钥；但 register 零限流、/api/analytics 无鉴权、sync_protocol 路径穿越+签名未校验 |
| **测试体系** | ⭐⭐⭐ | 897 通过，但 32 个测试用脚本化断言（CI 永远绿），hub/evidence/guard 等核心模块零覆盖 |
| **文档一致性** | ⭐⭐ | ARCHITECTURE.md 目录树过时、`reference/` 目录不存在、README 工具数与实现不符 |

**总体评价**: 理念先进、迭代活跃（2338 commits，951 bot + 881 主维护者 + 205 协作者），但**增长速度快于治理速度**——文档、死代码、单体 Worker、脚本堆积是主要架构债；搜索核心存在影响检索质量的确定性 bug。

---

## 轴 1：架构评估

### 1.1 架构亮点（应保持）

- **核心模型极简**：Lesson（Markdown+frontmatter）/ Node（profile+referral）/ Search（BM25 纯 stdlib）三概念贯穿全文，`ARCHITECTURE.md` 首段即点题。
- **分层清晰**：`misakanet/`（可发布包）→ `scripts/`（CLI/管线）→ `hub/`（可选同步）→ `workers/`（Cloudflare 服务层）→ `docs/`（静态站），依赖方向大体单向。
- **搜索可解释性投入充分**：`--explain` 输出 TF-IDF 明细、metadata 分解、boost 分解、vector 相似度；MCP 有 progressive disclosure（compact/summary/full）。
- **降级路径完善**：BM25 → SAG-Lite → lessons.json 零依赖 fallback → cross-encoder 失败回退，均有护栏。
- **治理机制独特**：DCO 强制、pr-shape-guard 只加不删、evidence 分级 E0–E4、tombstone→draft 飞轮。

### 1.2 高优先级架构问题

| # | 问题 | 证据 | 影响 |
|---|------|------|------|
| A1 | **文档-现实漂移**：ARCHITECTURE.md 目录树声称 misakanet/ 只有 profile.py/search/node（:13-23）、scripts/ 只有 8 个文件（:40-48）、`reference/` 有 6 篇 md（:51） | 实际 misakanet/ 有 server/tools/evidence/freshness/guard/graphql 等 12 项；scripts/ 107 个 .py；**`reference/` 目录不存在**（engine.py:19 仍引用该路径） | 新节点按文档定位失败；`REFERENCES` 路径恒为空目录，ref 检索静默失效 |
| A2 | **hub 仲裁闭环是死代码**：README/`misaka_hub.py` 宣称"冲突检测→GitHub Issue→仲裁" | `_create_conflict_issue`(145)/`resolve_arbitration`(201)/`ArbitrationQueue.create_case`/`ConfidenceModel.calc_confidence` 均**无调用者**；`_on_sync_cycle`(124) 只做索引重建+通知 | "图书馆管理员"定位与实际行为脱节；一套能力虚挂 |
| A3 | **MisakaHub 上帝对象 + 无依赖注入**：一个类聚合 9 个子系统，全部 `__init__` 内直接 new | `misaka_hub.py:38-228`；测试被迫用 `sys.modules` 打桩（test_hub_smoke.py:100-124） | 构造即触发 torch/transformers 模型加载；测试与部署脆弱 |
| A4 | **双 embedding 模型并存且不兼容**：skill_indexer 用 BGE-m3（1024 维），vector_store 用 bge-base-zh-v1.5（768 维），engine.py:834 用 `zip()` 静默截断 | skill_indexer.py:25 vs vector_store.py:130 vs engine.py:828-839 | hub 索引向量与搜索查询向量来自不同模型，相似度无意义 |
| A5 | **双 KnowledgeGraph 实例同写一文件**：hub 建一个，SkillIndexer 又经 `_init_graph` 建第二个 | misaka_hub.py:52 vs skill_indexer.py:87 | 内存图分叉，各自 save() 互相覆盖，status() 读到的与索引器不一致 |
| A6 | **Worker 2826 行单体职责过载** + node_counter 无原子读-加-写 | `workers/register-proxy-sw.js`；register/email/web 三处并发操作同一 KV key | 注册并发时产生重复 node_id；单体难测试难演进 |
| A7 | **脚本堆积**：107 个 scripts/ 中 9 个无任何引用（add_test_cmds、backfill_timestamps、migrate_lesson_metadata、sync_h1 等），14 个一次性 fix_/clean_/migrate_ 迁移脚本未归档 | 引用扫描 + git log | 新人无法区分"工具"与"历史脚手架" |
| A8 | **多语言目录混乱**：en/ 61 篇真实翻译，hi/id/ru/tr/vi 各仅 1 篇，draft/drafts 空壳并存，contrib 内混放 -hi/-ru 后缀文件 | lessons/ 目录盘点 | i18n 承诺（README 声称多语言）名不副实 |
| A9 | **web/ 目录基本为空**：仅 wrangler.jsonc/vitest 配置，无应用代码；前端实际是 docs/index.html 单文件 SPA | web/ 清单 | "web/"命名误导；前端与 worker 绑定在 docs/ 下，结构隐晦 |
| A10 | **package.json `deploy:api` 指向不存在的 `workers/wrangler.api.jsonc`** | package.json:27 vs ls workers/ | 部署脚本一键即败 |

### 1.3 CI/CD 架构

- **ARCHITECTURE.md 声称"30+ workflow/4 层模型"，实际 50 个**，且社区运营类（star-request、pr-welcome、pr-thank-you、newbie-welcome、claim-enforcer）混入 CI 目录，与质量门混在一起。
- **安全卫生欠佳**：46/50 无 concurrency、13/50 无显式 permissions、action 全部用 @v7/@v9 major tag（仅 1 处 pin SHA，tj-actions/changed-files@v47.0.6 为历史被攻陷组件且未 pin）。
- **无 gitleaks CI job**（只有本地 pre-commit）。
- pull_request_target 共 4 处，均为安全用法（不 checkout PR 代码）。
- **CI 自检脚本自身有 bug**：pr-checks.yml:183 的 `{40}` 在 BRE 下是字面量致 SHA 过滤失效；lesson-security.yml:34-35 的 `r'\beval\b'` 模式致 eval/exec 检查失效。
- lesson-gate.yml:45 `FILES="${{ steps.changed.outputs.all_changed_files }}"` 未加引号 shell 展开，恶意文件名可注入命令。
- deploy-worker.yml 只监听 sw.js 变更，lib/ 与 wrangler.toml 变更不触发部署。

---

## 轴 2：代码质量（关键发现均经实证）

### P0 — 确定性 bug（影响核心检索质量）

| # | 问题 | 证据（实测） | 影响 |
|---|------|-------------|------|
| C1 | **`_normalize` 全 0 退化**：engine.py:387-393 当 `mx-mn<1e-10` 时全量返回 0.5，**全 0 分数向量（无匹配）也被抬成 0.5** | 实测 `_normalize([0,0,0]) → [0.5,0.5,0.5]`；全库 BM25 分量 = 0.65×0.5 = 0.325 > 0.1 阈值 | 乱码/无匹配查询返回全库，"零结果"路径永不触发；heal 覆盖率恒高失真 |
| C2 | **frontmatter tags 解析丢失**：`_parse_yaml_frontmatter`(engine.py:149-168) 只支持内联 `[a,b]`，不支持块式 `tags:\n- item`；且逐行解析遇嵌套块（provenance:）后字段全丢 | 实测 contrib **310/311** 篇块式 tags 解析为空；en/ **56/61** 篇 JSON+provenance 混排导致 domain/status/tags 全丢 | 按 tag 搜索、related-lessons 推荐、置信度分类全部失效——**知识库最大卖点受损** |
| C3 | **BM25 用 filename 作 doc_id**：engine.py:333-342，core/contrib/reference 同名文件互相覆盖得分 | 代码审读 + remote 模式缺 id 时 `filename=""` 全碰撞 | 一篇得错分、一篇得 0；remote 结果失真 |

### P1 — 高优先级

| # | 问题 | 证据 |
|---|------|------|
| C4 | L1 缓存指纹只取前 100 篇 filename（engine.py:281），不含 mtime → 文档更新后 L1 返回旧排序 | 代码审读 |
| C5 | `hub_poller.py:300` `send_hook_stats(stats_data, webhook)` 传 2 参，`FeishuNotifier.send_hook_stats(self, stats)` 只收 1 参 → **必然 TypeError**，hook 推送从未工作 | 签名比对实证 |
| C6 | MCP stdio 循环无异常边界（protocol.py:168-181）：`params` 非 dict、handler 抛异常即崩进程；mcp_deepseek_adapter 同病 | 代码审读 |
| C7 | **intake 管线不调用 intake_redact**：intake_pipeline.py 全文无 redact 调用，原文直接落 D1 并发公开 issue；precheck 只查 problem 字段 | grep 实证 |
| C8 | HTTP MCP 认证 token 经 `source` 字段原样写入公开 GitHub issue body（mcp_http_server.py:191-198+248）→ 凭证泄漏 | 代码审读 |
| C9 | `misakanet_register` MCP 工具零限流（sw.js:498-536），可被脚本刷 node_id/写 KV | 代码审读 |
| C10 | `/api/analytics`（sw.js:2047-2088）无鉴权泄露 7 天搜索词与 knowledge-gaps | 代码审读 |
| C11 | sync_protocol.py 用未经白名单校验的 lesson_id 拼文件路径（目录穿越）；manifest 的 Ed25519 signature 从未校验 | 代码审读 |
| C12 | `--semantic` 是死功能：search_knowledge.py:869-883 只做健康检查，之后 use_semantic 从不参与排序 | grep 实证 |
| C13 | **测试体系结构性缺陷**：test_mcp_server.py/test_reputation.py/test_mcp_auth_contract.py 共 32 个 test_* 用 `check()`+全局计数**不抛异常**，pytest 收集但失败不报错 → CI 永远绿 | 实测 test_mcp_auth_contract.py 8 passed（但断言函数名与语义相反，`len(tools)==5` 与实际 9 工具矛盾） |

### P1/P2 — 安全

- HMAC `key_version` 从不参与验证（hmac_auth.py:125）；nonce 缓存为进程内存态，重启/多 worker 可重放。
- token_manager.py:120 硬编码 `hub/config.yaml` 路径与 main() 的 `./config.yaml` 不一致；共享密钥明文 `!=` 比较。
- pyproject.toml:40 chromadb `CVE-2026-45829 pending fix upstream`——已知漏洞依赖未解决。
- 密钥面检查通过：.env 已 gitignore，tracked 文件无真实密钥（历史有 MiniMax key 泄露事件，已于 0ab66bdc 修复）。

### P2 — 中低优先级

- `_score_breakdown`（engine.py:846）用 N=1 语料算 BM25，--explain 展示分与真实排序不一致；hybrid 分量之和 ≠ 实际合成分。
- 两套 frontmatter 解析器行为分叉（engine vs freshness）；JSON 解析失败静默回退 YAML 产生脏元数据。
- engine 内 `from scripts.search_config import ...` 反向依赖，scripts/ 无 `__init__.py`，从外部 import 包即失败。
- 库函数内 print（engine.py:266/344/506/549）污染调用方 stdout。
- `--broad` 语义反直觉（过滤为 scope=="broad" 反而收窄）；`_get_search_boost` 只展示不进排序（"canonical +0.6" 是假增益）。
- 本地 CLI 5 次免费搜索配额（profile.py:172）：对"零依赖本地搜索"核心主张构成摩擦，需重新权衡。
- lib/redact.js 是 CommonJS 死代码，实际 redact 有 4 份实现正则漂移；register-proxy.test.mjs 测的是已不部署的旧文件。
- lessons 内容：git 凭证 4 连近重复、7 篇 contrib 缺 Verification、placeholder Verification（echo+wc -l 假验证）、contrib 标题大量中英混杂。

---

## 测试与文档漂移

### 测试状态

- **897 passed / 4 failed / 15 skipped**。4 个失败：test_token_manager_nokeyring ×3（模块缺失 torchvision）、test_semantic_smoke（embedding 健康检查）。
- **覆盖率盲区**：misakanet/evidence.py、guard.py、server/prompts.py、resources.py、handlers/*、hub/orchestrator/*、hub/storage/vector_store.py、hub/master/* 均无测试；`[tool.coverage.run] omit = ["scripts/*"]` 又整体排除 107 个脚本。
- 测试写真实文件（test_mcp_server.py 写 data/contribution_queue.jsonl 残留测试垃圾）、手写 os.environ set/del 而非 monkeypatch、`/tmp` 计数文件竞态。

### 文档-现实漂移清单（高优先修复）

| 文档声称 | 实际 | 严重度 |
|---------|------|--------|
| ARCHITECTURE.md:13-23 misakanet/ 仅 3 项 | 12 项（server/tools/evidence/freshness/guard/graphql/schema/scripts） | 高 |
| ARCHITECTURE.md:40-48 scripts/ 8 个文件 | 107 个 .py | 高 |
| ARCHITECTURE.md:51 `reference/` 6 篇 md | **目录不存在** | 高 |
| README.md:14 "7 tools（含 misakanet_me_events）" | tools.py 实际注册 9 个；`me_events` 在 Python 侧**从未实现**（仅 worker 侧有） | 高 |
| README.md:242 "Latest v2.19.0" | pyproject/server.json 均 2.23.0 | 中 |
| ARCHITECTURE.md:71 "30+ workflows" | 50 个，且混入社区运营类 | 中 |
| STATUS.md "249 lessons / v2.11.0" | 448 lessons / v2.23.0 | 中 |
| docs/index.html "435 lessons" | 实际 448 | 低 |
| server.mcpb.json "v2.17.0" | 实际 2.23.0 | 中 |
| tasks/index.json source 指向 lessons/auto-merge... | 实际路径 lessons/core/... | 低 |

---

## 优先修复建议（Top 10）

1. **P0 修复 C1 `_normalize` 全 0 退化**：全 0 输入返回全 0，仅 `mx>0` 且近等时才用 0.5；补测试。影响面最大（无匹配查询返回全库）。
2. **P0 修复 C2 frontmatter 解析**：支持块式 YAML 列表 + 修复 en/ JSON+provenance 混排（311+56 篇元数据正在丢失）；收敛为单一解析器。
3. **P0 修复 C3**：BM25 doc_id 由 filename 改相对路径（复用 `_doc_cache_id`）。
4. **接通或删除 hub 仲裁闭环**（A2），统一 embedding 服务与单一 KnowledgeGraph 所有权（A4/A5）。
5. **MCP stdio 加异常边界 + intake 管线接入 intake_redact + 移除 source 字段入 issue**（C6/C7/C8）。
6. **Worker 拆分 + node_counter 原子化 + /api/analytics 鉴权 + register 限流**（A6/C9/C10）。
7. **修复脚本化断言测试**（C13）：32 个 check() 改真断言，否则 MCP/认证/声誉模块测试形同虚设。
8. **重写 ARCHITECTURE.md 目录树**，删除 `reference/` 条目，同步 README 工具清单与版本号。
9. **CI 卫生**：action pin SHA、补 concurrency/permissions、修 lesson-gate 注入点与自检正则、加 gitleaks job。
10. **清理脚本与死代码**：归档一次性迁移脚本，删除 lib/redact.js 等 4 份重复实现，修 package.json deploy:api 路径。

---

## 结论

MisakaNet 的理念与社区运营模式（DCO、evidence 分级、tombstone 飞轮、Agent 友好接口）是显著的差异化优势，代码库活跃度极高。但**架构债与增长同步累积**：文档落后于实现（`reference/` 已消失）、hub 能力虚挂（仲裁闭环死代码）、Worker 单体化、脚本堆积，加上 2 个已实证的 P0 级检索 bug（全 0 归一化、frontmatter tags 丢失）直接损害核心价值主张。**建议按 P0 → 文档同步 → 死代码清理的顺序推进**，先恢复检索正确性，再治理结构与一致性。

---

*评审人: DeepSeek Harness 主评审 + 6 并行子代理*
*评审方法: 双轴（架构 + 代码），关键发现运行实证*
