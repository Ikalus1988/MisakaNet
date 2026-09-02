# Lesson Trust Semantics

> MisakaNet 的信任模型和证据等级

---

## 一句话定位

**MisakaNet is a Git-backed failure-memory layer for AI coding agents.**

不是通用记忆系统，不是 Agent runtime，不是向量数据库。
是专注、轻量、可审计的失败恢复知识层。

---

## 反 RAG 立场

**MisakaNet is NOT a RAG system.**

| RAG 系统 | MisakaNet |
|----------|-----------|
| 向量嵌入 + 语义搜索 | BM25 关键词搜索 |
| 需要嵌入模型 | 零依赖 |
| 云服务 | 本地运行 |
| 黑盒检索 | 可审计的搜索结果 |

**为什么选择 BM25 而不是 RAG？**

1. **零依赖：** 无需安装嵌入模型（通常 2GB+）
2. **可审计：** 搜索结果完全可预测
3. **本地运行：** 无需云服务，无需网络
4. **快速：** 毫秒级响应
5. **足够好：** 对于 failure recovery，关键词搜索已经足够

---

## 信任级别

MisakaNet uses three trust levels for lessons. These terms are used consistently across README, site, and generated data.

## Definitions

| Term | Meaning | Quality gate |
|------|---------|-------------|
| **indexed** | In the search index. May be draft, published, or contrib. | quality_scorer ≥ 0 |
| **published** | Approved and visible. Passes quality gate. | quality_scorer ≥ 75 |
| **verified** | Fact-checked against original source material. Rare. | manual review + source link |

## Usage

- **README / public site**: Use "indexed" when counting total lessons.
  - ✅ "249 indexed failure-recovery lessons"
  - ❌ "249 verified failure lessons" (unless all 249 have been fact-checked)

- **Lesson frontmatter**: `status` field uses `draft`, `published`, or `deprecated`.
  - `published` means it passed the quality gate, not that it was manually verified.

- **Contrib lessons**: Start as `draft`, become `published` after quality_scorer ≥ 75.

- **Core lessons**: Are `published` by default (maintainer-curated).

## Why this matters

Claiming "verified" when lessons are only "indexed" erodes trust when a lesson turns out to be wrong. Use "indexed" for scale claims, "verified" only for fact-checked content.

---

## Evidence levels E0–E4 (Issue #786)

`status` answers *"is this published?"*. `evidence_level` answers the harder question: **how reliable is this lesson?** Without it, a contributor's self-reported guess and a CI-verified fix are indistinguishable in search results.

| Level | Meaning | How it is achieved | Weight |
|-------|---------|--------------------|--------|
| **E0** | Contributor self-reported | Default on intake | 0.00 |
| **E1** | Maintainer reviewed | A maintainer accepted the intake | 0.25 |
| **E2** | Local smoke reproduced | Maintainer or CI reproduced the fix | 0.50 |
| **E3** | Sandbox / CI verified recovery | Automated verification in CI | 0.75 |
| **E4** | Reused by another contributor / agent | Usage report from a different user | 1.00 |

### Rules

- **Default is E0.** A missing, empty, malformed, or unknown `evidence_level` reads as E0 everywhere — evidence is never assumed. `scripts/queue_lesson.py` writes `"evidence_level": "E0"` on new lessons.
- **One step at a time.** Promotion is E0 → E1 → E2 → E3 → E4; skipping levels means the intermediate evidence was never produced.
- **Evidence is not writing quality.** A beautifully written but unreproduced lesson is still E0.

### Promotion rules

| From | To | What has to happen |
|------|----|--------------------|
| E0 | E1 | A maintainer reviews the lesson and accepts it (**review**) |
| E1 | E2 | Someone reproduces the failure and the fix locally (**reproduce**) |
| E2 | E3 | CI or a sandbox run verifies the recovery automatically (**CI verify**) |
| E3 | E4 | A different contributor or agent reports reusing it successfully (**external reuse**) |

To promote a lesson, edit `evidence_level` in its frontmatter in the same PR that carries the evidence (review comment, reproduction log, CI run link, or the usage report).

### Evidence References (`evidence_refs`) (Issue #1439)

Lessons can optionally specify `evidence_refs` in their frontmatter to declare verifiable evidence sources at contribution time:

```yaml
---
title: "Fix ECONNRESET in Redis connection pool under load"
domain: "devops"
tags: ["redis", "connection-pool", "econnreset"]
status: "published"
evidence_level: "E3"
evidence_refs:
  - "ci:https://github.com/org/repo/actions/runs/12345678"
  - "repro:https://gist.github.com/user/abcdef123456"
  - "issue:#1439"
  - "commit:a1b2c3d4e5f6"
---
```

Supported formats:
- `repro:https://...` — Link to reproduction logs / environment steps.
- `ci:https://...` — Link to CI run or test action proving the fix.
- `issue:#<num>` — Issue reference where the problem/fix is tracked.
- `commit:<sha>` — Git commit SHA introducing the fix or reproduction test.
- `https://...` — Direct URL to external public evidence/documentation.

### me_events: live reuse signals (tool-level semantics)

`misakanet_me_events` aggregates a lesson's **live reuse evidence** — helpful votes (KV), regression-benchmark citations, and cross-node confirmations. It uses the E-level vocabulary as *signal strength*, not as the frontmatter promotion chain:

- **Single helpful vote** is labeled `E3` — it is a reuse signal, **not** CI verification; it does not claim the lesson passed a sandbox run.
- **E4 in the tool** means ≥2 independent reuse signals, or the strongest single signal reaching E4 level (e.g. 2+ helpful votes from different users).
- This is a query over live signals. The authoritative `evidence_level` for a lesson lives in its frontmatter and follows the one-step-at-a-time promotion rules above; me_events does not edit it.

### How evidence affects scoring

`scripts/score_lessons.py` keeps the existing quality `score` unchanged — the CI gate (`--threshold`) still measures writing quality — and adds a **trust score** on top:

```
trust_score = quality_score × (0.7 + 0.3 × evidence_weight)
```

So an E0 lesson keeps 70% of its quality score and an E4 lesson keeps all of it. The scorer also prints the corpus distribution (`E0=344 E1=0 …`), which is the honest current picture: everything starts self-reported until maintainers begin promoting.

### Where it shows up

- **Search results** — a purple `E0`–`E4` badge on every card, with the meaning on hover (`docs/search/index.html`).
- **Lesson pages** — `Evidence E2 — Local smoke reproduced` in the page metadata (`scripts/build_lesson_pages.py`).
- **Index data** — `evidence_level` is emitted per lesson by `scripts/misakanet-index.py` into `lessons.json`.
- **Schema** — `schemas/lesson.json` constrains the field to the E0–E4 enum.

The canonical implementation is `misakanet/evidence.py`; use `normalize_evidence_level()` rather than reading the raw field, so unknown values keep degrading to E0.
