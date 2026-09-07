# failure_harvest 全流程 Smoke 验证

> 目标：验证"失败事件 → 指纹簇 → lesson 骨架草稿"全流程可复现地跑通，
> 且草稿满足升格前置（lesson_gate 结构门可通过）。
> 适用：`scripts/failure_harvest.py`（P0，#1545 合入后）。

## 触发方式

### 方式 A：内置 demo（3 族合成事件，快速自检）

```bash
python3 scripts/failure_harvest.py --demo
```

预期（断言见 `tests/test_failure_harvest.py`）：

```
events:10 | cleaned_noise:2 | clusters:4 | drafts:3 | skipped:1
  drafts: K:ReadTimeoutError(3) / G:generic|git(2) / K:ReferenceError(2)
  skipped: G:generic|rust — low signal (occ=1 < 2)
```

验证点：
- pip 3 措辞变体（ReadTimeoutError / OSError ReadTimeoutError / 模块全路径）→ **1 簇**（防过窄）
- git credential "401" 与 "fatal:" 两措辞 → **1 簇**（弱信号不拆族）
- cloudflare KV 两措辞 → **1 簇**
- 纯 URL / 短文本噪音 → 跳过（cleaned_noise=2）
- 单事件 rust → 跳过（occ 门槛）

### 方式 B：真实形态事件文件（端到端，推荐）

构造 `events.json`（真实失败事件，同族可多变体、可带 source/what_tried）：

```json
[
  {"error": "/home/hp/.local/bin/gh auth git-credential get: ... gh: not found",
   "source": "agent-a", "what_tried": "checked gh install path"},
  {"error": "fatal: could not read Username for 'https://github.com': credential helper ...",
   "source": "agent-b", "what_tried": "reinstalled gh"}
]
```

```bash
python3 scripts/failure_harvest.py --events events.json --out lessons/drafts
# 或管道
cat events.json | python3 scripts/failure_harvest.py --json
```

产物落 `lessons/drafts/<safe-cid>.md`（如 `G-generic-git.md`），
frontmatter 含 `source: failure-harvest`、`harvest_ref`、`failure_patterns`、
`evidence_level: E0` —— 与 fatal-guard 草稿同生命周期。

### 方式 C：升格前置验证（草稿 → contrib 门槛）

草稿在 `lessons/drafts/` 隔离区不受 lesson_lint/lesson_gate 硬卡；
升格前人工补全 Root Cause / Solution / Verification 后移入 `lessons/contrib/`，
届时由 `lesson-gate.yml` 硬门校验。本地预检：

```bash
python3 scripts/failure_harvest.py --demo          # 生成草稿
python3 scripts/lesson_gate.py lessons/drafts/G-generic-git.md   # 结构预检
```

实测：harvest 草稿 frontmatter（title/domain/tags/status/evidence_level）
+ content ≥100 字符已满足 lesson_gate 结构要求（demo 草稿直接通过）。

## 单测护栏

```bash
python3 -m pytest tests/test_failure_harvest.py -q   # 10 用例
python3 -m pytest tests/test_failure_harvest.py tests/test_intake_bot_50.py -q  # 40 全过
```

锁定防回归点：specific kind 按类聚类 / generic 按栈聚类 / URL 剥除 / R 栈剔除 /
401+fatal 同簇 / occ 门槛 / 文件名跨平台安全。

## 已知边界

- 草稿 = 骨架（E0，无 Root Cause/验证）——升格需维护者审 + 补全（草稿生命周期）
- 跨异常类型的同根因（如 TypeError vs ReferenceError 同因）不合并——确定性规则
  不臆测语义，留给 #1527 failure_patterns 签名索引
- 真实事件源接入（ci-lesson-search 失败事件 → harvest）尚未自动化，属后续工作
