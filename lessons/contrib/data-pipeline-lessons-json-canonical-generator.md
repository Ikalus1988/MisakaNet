---
title: 数据管道 lessons.json 必须用规范生成器 update_lessons_json.py
domain: data-pipeline
tags:
- lessons.json
- data-pipeline
- generator
- update_lessons_json
- misakanet-index
- evidence_level
- trust_score
status: published
created: '2026-08-29'
language: zh
source: intake-issue-1374
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---

## Problem

改 `data/lessons.json` 时如果误用 `misakanet-index.py` 重新生成：
- 新格式带 `evidence_level/trust_score` 字段，但**丢失** `preview/triggers/verified` 等老字段。
- 规范的生成器是 `scripts/update_lessons_json.py`（由 `.github/workflows/update-lessons.yml` 每日 0 点 UTC+8 自动跑）。
- 几小时内 `update-lessons.yml` 会把 `data/lessons.json` 打回旧格式（无 evidence 字段）。
- 加上 `.github/workflows/build-feed.yml` 每 3 小时 `cp data/lessons.json docs/data/lessons.json`，会把 `docs/data/` 也覆盖成旧格式。
- 线上搜索页的 evidence 统计（E3+/E4、trust_score）被静默回滚为全 E0，且两份 JSON 不再同构（317 vs 315）。

## Error

```
# 现象 1：evidence_level 字段消失
$ python3 -c "import json; d=json.load(open('data/lessons.json')); print(d[0].get('evidence_level','MISSING'))"
MISSING

# 现象 2：两份 JSON 不同构
$ diff <(python3 -c "import json; print(len(json.load(open('data/lessons.json'))))") \
       <(python3 -c "import json; print(len(json.load(open('docs/data/lessons.json')))") || echo "MISMATCH"
MISMATCH
```

## What was tried

先用 `misakanet-index.py` 重新生成 lessons.json（只改了消费方搜索页 + 一个生成器，没找到规范生成器）。

## Solution

**改数据文件前先 grep `.github/workflows` 找规范生成器：**

```bash
# 1. 找谁负责生成 lessons.json
grep -rn "lessons.json" .github/workflows/ scripts/

# 2. 确认当前线上格式
python3 -c "import json; d=json.load(open('data/lessons.json')); print(d[0].keys())"
```

**修复方案（把 evidence 字段加进规范生成器）：**

1. 在 `scripts/update_lessons_json.py` 写入 `evidence_level`（frontmatter 优先 + 内容推断）、`evidence_source`、`trust_score` 三个新字段。
2. 同时保留 `preview/triggers/verified` 字段，供 `mcp_preflight.py` / `lesson_reuse_agent.py` 消费。
3. 让 `data/` 与 `docs/data/` 两份 JSON 重新生成同构。
4. 让 `build-feed.yml` 不再覆盖 `docs/data/lessons.json`（或至少用新格式覆盖）。

**为什么必须用 `update_lessons_json.py`：**
- `update_lessons_json.py` 走 frontmatter 解析 + 字段映射，兼容 E0–E4 证据等级。
- `misakanet-index.py` 是早期索引脚本，不写 evidence 字段，会被下次 `update-lessons.yml` 跑回旧格式。

## Verification

```bash
# 两份 JSON 必须同构 + 同长 + 含 evidence_level
python3 -c "import json; d=json.load(open('data/lessons.json')); print(len(d), d[0].get('evidence_level'))"
python3 -c "import json; d=json.load(open('docs/data/lessons.json')); print(len(d), d[0].get('evidence_level'))"

# 相关测试
python3 -m pytest tests/test_add_provenance.py tests/test_intake_classify.py tests/test_clean_pipeline.py -x

# 线上统计（应有非零 E3+/E4）
curl -sS https://misakanet.org/api/lessons | python3 -c "import json,sys,collections; print(collections.Counter(l.get('evidence_level','') for l in json.load(sys.stdin)))"
```

**Expected Output:** `317 E0` (或类似数字，核心是有 E3/E4 项)，两份 JSON 行数一致。

## Related经验

- 任何改 `data/lessons.json` 的 PR 都会被 `update-lessons.yml` 在下次调度时回滚，除非同步改 `scripts/update_lessons_json.py`。
- `docs/data/lessons.json` 是 `data/lessons.json` 的镜像，只读副本，由 `build-feed.yml` 每 3 小时同步。
