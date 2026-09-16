---
domain: "general"
title: "<English Title>"
status: "draft"
verification: "metadata-normalized"
{"title": "<English Title: 4-120 chars>", "domain": "<domain>", "tags": ["tag1", "tag2", "tag3"], "status": "published", "confidence": "0.9", "created": "<YYYY-MM-DD>", "updated": "<YYYY-MM-DD>", "source": "<your-source>", "verified_date": "", "domain_expert": ""}
---

# <English Title>

## Problem

<!-- What went wrong? What was the symptom? Be specific. -->

## Root Cause

<!-- Why did it happen? Include technical detail. -->

## Solution

<!-- How to fix it. Include commands, config, or code. -->

### Step 1

### Step 2

### Step 3

## Verification

<!-- How to confirm the fix works. -->

## Notes

<!-- Caveats, edge cases, related lessons. -->

---

### Template Rules

| Rule | Standard | Reason |
|------|----------|--------|
| **Filename** | `kebab-case-english.md` | No Chinese, no project prefixes |
| **Frontmatter** | JSON inside `---` | Must parse with `json.loads()` |
| **Required fields** | `title`, `domain`, `status` | Schema enforcement |
| **Tags** | 1-10 tags, 2+ chars each | BM25 retrieval |
| **Section order** | Problem → Root Cause → Solution → Verification | Consistency |
| **Structured fields** | `summary_plain`, `trigger`, `verify` — required for **new** lessons (#1783) | Answerable in plain language + retrievable by fragment |
| **Code blocks** | Language-specified fenced blocks | Syntax highlighting |
| **Paths** | `<placeholder>` not `/home/user/...` | Portability |

---

### Structured Fields (optional for the corpus, required for new lessons)

Three **optional** frontmatter fields (#1783). They never replace
`Problem` / `Root Cause` / `Solution` / `Verification` — the body is still the lesson,
these are what make it *findable* and *usable* by a non-technical reader.

```yaml
summary_plain: "公司网络里装不上 Python 包，是因为下载源要先换成公司内部的镜像。"
trigger: "pip install timeout behind proxy"
verify: "pip install -v httpie 退出码为 0"
```

| Field | What it is | Limit |
|-------|------------|-------|
| `summary_plain` | One plain-language sentence for a non-technical reader — what happened, in words a non-engineer can repeat to a colleague | ≤ 120 chars |
| `trigger` | The short, matchable condition that should make an agent **search** — an error fragment or keyword phrase, not a question | ≤ 160 chars, one line |
| `verify` | A checkable pass/fail criterion — something a reader can run or observe, and that fails when the fix is absent | ≤ 200 chars |

**`summary_plain`** — one sentence a model can repeat to the user verbatim:

```yaml
# ✅ good: names the symptom and the cause in plain words
summary_plain: "公司网络里装不上 Python 包，是因为下载源要先换成公司内部的镜像。"

# ❌ bad: a restatement of the title, in jargon, that tells the reader nothing
summary_plain: "pip 的 index-url 配置异常导致的解析超时问题。"
```

**`trigger`** — the corpus is indexed by error text and keywords, so a whole-sentence
Chinese question retrieves **nothing**; a distinctive fragment retrieves the lesson:

```yaml
# ✅ good: the words that actually appear in the error, short enough to match
trigger: "pip install timeout behind proxy"

# ❌ bad: a natural-language question — nothing in the index matches it
trigger: "我的构建为什么一直失败，应该怎么解决？"
```

**`verify`** — checkable, i.e. a reader can tell pass from fail without asking you:

```yaml
# ✅ good: a command with an observable result
verify: "pip install -v httpie 退出码为 0"

# ❌ bad: not a criterion at all — nothing to run, nothing to observe, and it
# cannot fail, so it verifies nothing
verify: "注意编码问题"
```

Full definitions, why `trigger` matters for retrieval, and the optional corpus
backfill: `docs/maintainer/lesson-fields.md`.
