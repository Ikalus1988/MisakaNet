# 外部仓库接入：misaka-intake-bot（CI 失败 → 课程建议 / 自动 intake）

> 适用对象：想让自己的 CI 失败**自动获得修复建议**、并把**新颖失败自动上报**给
> MisakaNet（形成 lesson 语料）的仓库/开发者。零账号：intake 走匿名 MCP 通道。

> ### 🎯 长期试点计划（#1550）——持续征集外部接入报告
>
> 接入本 action（见下）后，在**你自己的真实仓库**跑一段时间，交付一份 **≥20 样本**
> 反馈报告，即可加入长期试点：
> [github.com/Ikalus1988/MisakaNet/issues/1550](https://github.com/Ikalus1988/MisakaNet/issues/1550)
>
> - 报告提交：PR 至 `docs/external-pilots/<你的仓库>-<日期>.md`（含样本 NDJSON）
> - 回报：zero-bounty（merge credit + leaderboard）；CI 失败自动获课程建议；上报的
>   新颖失败转正后你被记为来源（#1528 回执机制）
> - 进度：**Pilot 1/20**（roof4u，2026-09-08，25 样本）——长期开放，欢迎持续接入
> - 样例报告：[roof4u-2026-09-08](https://github.com/Ikalus1988/MisakaNet/blob/main/docs/external-pilots/roof4u-2026-09-08.md)


## 1. 它做什么

你的 CI 失败时，本 action 会：

| decision | 行为 |
|---|---|
| **hit** | 在 PR/issue 评论"相关 MisakaNet 课程"（suggest-only，附相似度与链接，供人工核对） |
| **intake** | 错误新颖且达标 → 自动经 `misakanet.org/mcp` 上报；worker 侧去重后**自动在 MisakaNet 仓开 `[Intake]` issue**（或 `[Question]`），成为他人可认领的任务 |
| **ignore** | 噪音/重复/缺证据 → 静默（不打扰），仅本地计数 |

价值闭环：你的仓库 CI 失败 → MisakaNet 建议帮你省排查时间；你上报的新颖失败 →
MisakaNet 语料变厚 → 全网络命中率提升。**复用越多 → intake/issue 越多 → 任务越多 →
lesson 越多 → 命中越好 → 越值得复用。**

## 2. 一行接入（推荐：workflow_run 模式）

新建 `.github/workflows/misaka-intake.yml`：

```yaml
name: MisakaNet Intake Bot

on:
  workflow_run:
    # 建议写你自己的 CI workflow 名（如 ["CI"]），不要用 "*"：
    # "*" 会在**任意** workflow 结束时都触发本 workflow，绝大多数运行在 if 处就被跳过
    # （本仓因此白跑了 21,126 次）。名字写窄一点，跨仓一样工作。
    workflows: ["CI"]
    types: [completed]

permissions:
  # `actions: read` 不是可选项：自动抽取报错时，action 读的是失败 job 的日志
  # （REST `.../actions/jobs/{id}/logs`）。而 workflow 里一旦写了 `permissions:`，
  # **没列出的 scope 一律被置为 `none`** → 日志读不到 → warning 被吞 → 变成
  # "No error input provided, skipping"：**绿着、什么都不发**。给不出这个权限时，
  # 改用 `error:` / `log-file:` 显式传错误文本。
  actions: read
  pull-requests: write
  issues: write                # 评论走 issues.createComment（PR 也是 issue）

jobs:
  intake:
    if: ${{ github.event.workflow_run.conclusion == 'failure' }}
    runs-on: ubuntu-latest
    steps:
      # 无需 checkout MisakaNet：action 自带 scripts/，`@v1` 拿到的就是那一版脚本
      - uses: Ikalus1988/MisakaNet@v1
        id: intake
        with:
          mode: suggest-and-intake      # 或 suggest-only（只建议不上报）
          source: ${{ github.repository }}   # 上报来源标识 = 你的仓库
          comment-on-pr: 'true'
```

> **为什么是 `@v1` 而不是 `@main`**：`@v1` 是打好的 tag，你拿到的是冻结的一份
> （action 与它跑的 `intake_bot.py` 同版本）；`@main` 每天在变，跨仓出问题时无法复现。
> 想尝鲜可以临时用 `@main`。
>
> 本 action 同时上架 GitHub Marketplace（`MisakaNet Intake Bot`），在 Marketplace 里点
> "Use latest version" 得到的就是同一行引用。

> 无 PR 的失败（如 main 分支定时任务）不会评论（无关联 PR），但 intake 上报照常。

## 3. 手动触发 / 指定错误文本

```yaml
on:
  workflow_dispatch:
    inputs:
      error:
        description: 'Error text'
        required: false
        default: 'curl: (35) SSL connect error proxy'
      mode:
        type: choice
        options: [suggest-only, suggest-and-intake]
        default: suggest-and-intake

permissions:
  # 这条路径把错误文本放在 `error:` 里，理论上不需要 `actions: read`；仍然给上，
  # 因为输入一旦为空，action 就会回落到读日志 —— 少给这一个 scope，回落的那次
  # 会变成"绿着但什么都没发"。评论要 issues: write（issues.createComment），
  # 列出失败 PR 要 pull-requests: read。
  actions: read
  pull-requests: write
  issues: write

jobs:
  intake:
    runs-on: ubuntu-latest
    steps:
      - uses: Ikalus1988/MisakaNet@v1
        with:
          mode: ${{ inputs.mode }}
          error: ${{ inputs.error }}
          source: ${{ github.repository }}
```

## 4. 收集样本报告（供赏金验收 / 自我评估）

每次运行 action 输出 `steps.intake.outputs.sample`（NDJSON 一行：repo/workflow/
decision/fingerprint/lesson_id/sim/receipt），并写入该步的 Job Summary。
累积 ≥N 条后汇成报告：

```yaml
      # 示例：把每次 sample 追加到本地文件（多 run 需 upload-artifact 归集）
      - name: Append sample
        shell: bash
        run: |
          echo '${{ steps.intake.outputs.sample }}' >> misaka-samples.ndjson
      - uses: actions/upload-artifact@v4
        with:
          name: misaka-samples
          path: misaka-samples.ndjson
```

## 5. 输入参数

| input | 默认 | 说明 |
|---|---|---|
| `mode` | `suggest-only` | `suggest-and-intake` 才真实上报 |
| `error` / `log-file` | 自动抽取 | 错误文本或 CI 日志路径（留空则从失败的 workflow_run 日志抽取） |
| `source` | `github-action` | 上报来源标识，建议用 `${{ github.repository }}` |
| `source-ref` | `main` | **仅兜底**：本地找不到 `intake_bot.py` 时从该 ref 拉取（`@v1` 自带脚本，通常用不到） |
| `sim` | `0.45` | 命中相似度阈值（stack-aware；无栈泛化错误需 ≥0.55） |
| `what-tried` | 空 | 尝试过的修复（提升 intake 转正率） |
| `comment-on-pr` | `true` | 是否在关联 PR 评论结果 |
| `pr-number` | 空 | 指定要评论的 PR（默认用失败运行关联的 PR；手动 dispatch 时靠它测试评论路径） |

## 6. 输出

| output | 内容 |
|---|---|
| `decision` | `hit` / `intake` / `ignore`（脚本自身失败是 `error`，且该 step 会**红**——不是"没什么可说的"） |
| `fingerprint` | 错误指纹（去重用） |
| `lesson-url` | 命中课程的链接 |
| `sample` | 一行 NDJSON（repo/workflow/decision/fingerprint/lesson_id/sim/receipt），同时写进 Job Summary |

## 7. 隐私与安全

- intake 只上报**技术错误签名**（≤280 字符）+ source 标识；本地已有 redaction
  （token/路径/邮箱/IP），worker 侧二次脱敏。
- **读取不限次数**（2026-09-18 起）：`search` / `get_lesson` 匿名即可用，只保留同一地址的
  反爬突发保护；注册只解锁写入类工具（`write_lesson` / `preflight`）。
- 上报内容进 MisakaNet 公开 issue 前会经去重/质量闸；仍介意可一直用 `suggest-only`。

## 7. 反馈问题

- 建议不准 / 误配：附错误原文到 [intake](https://github.com/Ikalus1988/MisakaNet/issues/new?template=lesson-feedback.yml)
  （提"课程建议质量"），我们会调阈值/词表。
- 想参与长期试点（≥20 样本反馈报告，zero-bounty）：见
  [#1550](https://github.com/Ikalus1988/MisakaNet/issues/1550)（长期开放，进度
  Pilot 1/20）；任何接入/报告问题可直接在该 issue 提问。
