# Handoff — 2026-09-05 审计与项目改进轮（PR #1482）

> 合并：`fdedda454`（Merge PR #1482，25 个提交）→ main 现 HEAD `88a8426df`。
> 会话产物（详细报告/执行日志，gitignore 本地保留）：`.audit-reports-20260905/`。
> 相关：`docs/CI.md`、`docs/maintenance.md`、`docs/maintainer/handoff-2026-09-05.md`。

---

## 1. 会话概览

- **目标**：对“自己 + 主项目”执行多仓库并行审计，并据此做分阶段改进。
- **方法**：2 个只读审计 subagent 并行（范围不重叠）→ 合并交付文档 → 按
  QW/M0-M3/T2.x 里程碑逐项执行 → 每步验证 → 单分支 PR 合入。
- **范围**：`MisakaNet`（深度审计 B）+ `@deepseek-ai/dsh`（harness 审计 B+，改进留待上游 PR）。
- **成果**：25 个提交合入 main；`search_knowledge.py` 1075→519 行；索引去重后 359 条唯一课程；
  4 个 dependabot 告警清除；真实测试回归（1 个，已修）。

## 2. 审计结论速览（详细见 .audit-reports-20260905/01·02）

| 仓库 | 健康 | Top 风险（已处理 → 未处理） |
|---|---|---|
| MisakaNet | B | 版本号分裂→T2.1 通道策略+工具；`MisakaNetSearchEngine` 导入缺失→QW4 facade；BM25/服务静默降级→QW4/doctor；根目录垃圾→QW1-2/hook |
| dsh | B+ | 60+ rc 依赖/零测试/README 安全提示——**未处理，需上游 PR**（见 §7） |

## 3. 合入 main 的改动（按逻辑分组）

### 快速修复（QW1–6）
- `a1b64de4c` 根目录卫生：删 12 垃圾目录 + `.gitignore` glob + pre-commit hook（`scripts/hygiene_check.sh`）
- `0d26c9a7c` **QW4**：engine 新增公共门面 `MisakaNetSearchEngine`（MCP/HTTP 的 `HAS_BM25` 恢复为 True；
  SAG 兼容 dict 输出）
- `cd9bf4476` **QW5**：`search_knowledge --heal` 默认 dry-run（`--heal --write` 才写 fixture）
- `42c9c9a3b` **QW3**：`make doctor` 预检（KV 占位符/misakanet_core/远端可达）
- `41e48a4a3` **QW6**：`{{LESSONS_COUNT}}` 计数自动刷新（update_lessons_json + 每日 workflow 提交）

### M0 安全网
- `320db6960` 版本一致性测试（tests/test_version_consistency.py）
- `230822fc1` deploy-worker CI 前置 KV 门禁（doctor `--kv-only`）

### M1 拆分（T1.1）
- `4dff6a324` heal/diagnose → `misakanet/cli/heal.py`（stage 1）
- `5b2accdc8` remote/typo/graphql/harvest → `misakanet/cli/{remote,typo,graphql_repl,harvest}.py`（stage 2-4）
- 效果：`search_knowledge.py` **1075 → 519 行**；全部符号在入口 re-export（测试/console script 不变）
- 注意：Shape Guard 规则对 search_knowledge.py 删除 >100 行会拦截——未来大重构需先放宽规则或 admin 合并

### M2 索引策略（用户拍板：“图书馆”全可见 + 去重）
- `3dc4c5993` / `44056401a`：`misakanet/lesson_index.py` 自动发现所有含课文的子目录
  （en/ 61 篇英文课此前**不可见**），索引 324→392
- `23eb4ef03` / `604796fbe`：`canonical_lessons()` 按 stem 去重（core>contrib>其他），镜像不进索引 →
  **392→358 唯一**
- `7ce502239`：`docs/CI.md`（53 workflow 全量清单 + 失败修复表）
- `5bf023f75`：D1 同步/SAG jsonl/MCP(stdio+HTTP)/reputation/fix_frontmatter/benchmark 全部对齐 canonical
- 合并树再生成：`2c928982c` → **359 条**（main 新增 1 篇；含 main 的 `evidence_refs` 字段）

### M3 润色
- `aeb5c500e` quality_scorer：draft/模板 TODO 豁免——**评审后收紧**：仅 harvester/template 来源或
  templates/ 目录豁免（普通 draft 仍标记；修复 `test_placeholder_detected`）
- `998aacaf8`：README.zh-CN 补齐 dsh/Python 接入、计数 289→358；新增 `docs/maintenance.md`
- `7cf63eca5`（评审响应）：facade 每次 search 经 L2 缓存刷新语料；`_log_zero_result` 改 json 解析匹配；
  同上 quality 收紧

### T2.1 版本通道统一 + 依赖安全 + 归档清理
- `80890185e`：`scripts/align_versions.py`（`--check`/`--registry`/`--source`）+ `make check-versions`；
  `docs/maintenance.md` 记录**四通道策略**（registry 2.27.1 / repo-release 2.27.1 / npm-bundle 2.23.x /
  pypi 实况 2.18.0）
- `89c35ac8d`（合并 main 后适配）：server pypi 条目→2.27.1；R2 改为 npm-bundle ≤ manifest；
  R5 上限用 manifest
- `cdae7533d`：**chromadb 从 hub extras 移除 + uv.lock 重生成（-1806/+37）**——关闭 dependabot #17-#20
  （GHSA-2wm9/36p7/f4j7/xph7，上游 ≤1.5.9 无修复；仓库零 import）
- `47539cc01` + `91c8ae379`：清理 `lessons/_archive/` 共 50 篇（4 损坏半导入 + 46 自动归档产物，
  产品决策删除；git 历史可回溯）

## 4. 验证与门禁

- 跨平台 test 矩阵、lint、CodeQL、DCO、pr-agent 全绿（GitHub CI）
- 本会话本地回归：55/64/48 组子集通过；版本门禁 `make check-versions` OK
- 合并后一致性：canonical == data/lessons.json == **359**；chromadb 在 uv.lock 0 引用
- 合并前修复的 1 个真回归：quality_scorer TODO 豁免过宽（本地/CI 均复现）
- 本地环境噪音（非代码问题）：mcp 包版本与 CI 不一致、embedding 服务返回 'down'

## 5. 新文件清单（合入后）

`misakanet/lesson_index.py`、`misakanet/cli/{__init__,heal,remote,typo,graphql_repl,harvest}.py`、
`scripts/doctor.py`、`scripts/align_versions.py`、`scripts/hygiene_check.sh`、
`tests/test_lesson_index_discovery.py`、`tests/test_version_consistency.py`、
`docs/CI.md`、`docs/maintenance.md`、`docs/_lessons_count.txt`；修改：engine.py、search_knowledge.py、
update_lessons_json.py、sync_lessons_to_d1.py、export_okf.py、mcp_http_server.py、server/resources.py、
handlers/get_lesson.py、reputation.py、fix_frontmatter.py、benchmark_workers_ai.py、quality_scorer.py、
pyproject.toml、uv.lock、server.json、Makefile、.gitignore、.pre-commit-config.yaml、多个 workflow/文档。

## 6. 运维影响与日常命令

```bash
python3 scripts/update_lessons_json.py   # 刷新 data/lessons.json + {{LESSONS_COUNT}}（359）
make doctor                              # 部署前预检（KV 占位符未填会 exit 1 —— 需填真实 ID）
make check-versions                      # 版本四通道不变量门禁
python3 scripts/align_versions.py --registry 2.28.0   # 下次发版“对齐”一键完成
python3 scripts/sync_lessons_to_d1.py --sql           # 预览 D1 同步（canonical 359）
python3 -m pytest tests/test_lesson_index_discovery.py tests/test_version_consistency.py -q
```

- 每日 cron：`update-lessons.yml` 提交 lessons.json/计数；`sync-d1.yml` 同步 D1（与本地一致 359）
- `lessons/_archive/` 已清空：今后勿放入文件（lesson_index 视其为脚手架排除）

## 7. 未决事项（Open Items）

1. **DSH 上游改进**（B+ 审计 `02-dsh-harness-audit.md`）：`dsh doctor`、`engines.node`、README Security &
   Trust、`config lint`、HMR 抑制——需提交 deepseek-ai/deepseek-harness `apps/cli/` 的 PR（本仓库只读副本）。
2. **wrangler.jsonc KV 占位符**：`YOUR_KV_NAMESPACE_ID` 仍待填真实 ID（root 静态站部署时必失败；
   `make doctor` 持续提示）。
3. **PyPI 发布滞后**：pypi.org 实际 2.18.0，pyproject/清单已到 2.27.1——若需恢复 PyPI 发布，
   跑 `release-pypi.yml`（手动）前先确认版本与内容。
4. **Shape Guard 阈值**：search_knowledge.py 删除 >100 行即拦截；若未来继续重构，
   建议先小 PR 放宽规则或加豁免注释。
5. **dependabot 关闭确认**：chromadb 告警 #17-#20 应在合并后自动关闭（Security 页核对）。
6. 历史遗留（与本会话无关）：GitHub 曾提示默认分支 4 个 dependabot 漏洞——已全部指向 chromadb 并清除。

## 8. 回滚

- 整体：`git revert fdedda454`（或按需 revert 个别提交；数据类提交（lessons.json/uv.lock）与其
  feat 提交成对 revert 更稳）。
- 索引回 324（旧行为）：需同时回滚 lesson_index/engine 发现与去重 + 再生成 lessons.json。

---
*本 handoff 由 2026-09-05 会话整理；详细证据与逐条验证见 `.audit-reports-20260905/01·02·03`。*
