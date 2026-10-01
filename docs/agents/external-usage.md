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
| **ignore** | 噪音/重复/缺证据 → 不上报；默认只在关联 PR 贴一条 `🚫 MisakaNet: Skipped`（判读见 §8） |

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
| `decision` | `hit` / `intake` / `ignore`（脚本自身失败是 `error`，且该 step 会**红**——不是"没什么可说的"；判读方法见 §8） |
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

## 8. 怎么判断 bot 是否真的在工作

跑了一段时间却**一条评论、一条 intake 都没有**时，先别急着下"这个错误没人踩过"的结论。
action 有两种完全不同的"安静"：

- **bot 坏了**（`decision=error`）——链路/参数/网络有问题，本次失败**根本没被检索、也没被上报**；
- **没有失败可报**（`decision=ignore`）——噪音/重复/缺证据，**不上报**（但仍可能在关联 PR 上留一条
  `🚫 MisakaNet: Skipped` 说明原因，见 §8.3）。

历史教训：外部试点仓库 `zsxh1990/upgraded-docs-framework` 连续 **7/7** 次运行都是
`{"decision":"error","reason":"script failed"}`，**0 条 intake**，报告因此一直无法结案
（[#1825](https://github.com/Ikalus1988/MisakaNet/issues/1825) 记录了根因与规模：
**21,732 次运行、0 条评论**）。接入方当时拿不到任何线索去区分这两种安静。

### 8.1 一条命令自检（接入前 / 排障时）

在 MisakaNet 仓内（或任何有 `scripts/intake_bot.py` 的地方）跑：

```bash
python3 scripts/intake_bot.py --json --source probe --error "ModuleNotFoundError: No module named 'requests'"
```

期望 `decision` ∈ {`hit`, `intake`, `ignore`}——**这三者都算"bot 在工作"**：
`hit` = 命中已有课程、`intake` = 该报料（不带 `--auto-intake` 时是 dry-run）、
`ignore` = 噪音/重复/缺证据。**得到 `decision=error` 就是故障**，不是"没有失败可报"。

实测输出（2026-09-25，`main` @ `66dace0`）：

```console
$ python3 scripts/intake_bot.py --json --source probe --error "ModuleNotFoundError: No module named 'requests'"
{"decision": "hit", "fingerprint": "08b7f8e407058a27", "suggest_only": true, "lesson": {"id": "fehler-python-modul-nicht-gefunden", "title": "ModuleNotFoundError in Python trotz pip install", "url": "https://misakanet.org/lessons/fehler-python-modul-nicht-gefunden/", "sim": 0.5}}
$ echo $?
0
```

三种 decision 都实测过（同一台机器、同一份脚本）：

```console
# ignore：无失败语义的输入
$ python3 scripts/intake_bot.py --json --source probe --error "https://example.com/some/long/path/segment"
{"decision": "ignore", "fingerprint": "18c2205186763857", "reason": "纯噪音（URL/JSON/路径/符号串），无失败语义"}

# intake：断网/不想联网时加 --offline，跳过远端预查（仍然会给出该不该报料的判断）
$ python3 scripts/intake_bot.py --json --source probe --offline --error "ModuleNotFoundError: No module named 'requests'"
{"decision": "intake", "fingerprint": "08b7f8e407058a27", "dry_run": true, "payload": {...}}
```

> `--error` 的值**必须整体加引号**：含空格/换行的错误文本一旦被 shell 拆成多个 argv，
> 脚本会以 exit 2 结束、stdout 为空——这正是下面 §8.2 那个坑。连 `--error` 一起丢掉引号，
> 你会亲手复现它：
> `python3 scripts/intake_bot.py --json --source probe --error ModuleNotFoundError: No module named 'requests'`
> → `intake_bot.py: error: unrecognized arguments: No module named requests`、**exit 2**。

### 8.2 `script failed` 是什么（历史签名）

如果你看到的是这个对象，说明你的 action 版本还带着修复前的兜底分支：

```json
{"decision":"error","reason":"script failed"}
```

原因（[#1825](https://github.com/Ikalus1988/MisakaNet/issues/1825)，已修）：

1. action 里 `--error` 携带的是失败 job 的**多行日志摘录**，而脚本调用写成
   `python3 $SCRIPT $ARGS`（变量**未加引号**）；
2. 多行文本被 word-split 成多个 argv → `argparse` 直接 **exit 2**；
3. `2>/dev/null` 把真正的报错**吞掉**，`|| echo '...'` 兜成一个泛化的
   `{"decision":"error","reason":"script failed"}`；
4. 调用方遇到未知 decision 走 `return`（不发评论）→ 于是**步骤是绿的、什么都不发**。

修复已进 `main`，**`v1` tag 也包含修复**（`v1` 的
[`action.yml`](https://github.com/Ikalus1988/MisakaNet/blob/v1/action.yml) 用 bash 数组
`ARGS=(...)` + `"${ARGS[@]}"` 逐值传参，并保留 stderr：脚本非 0 退出会打 `::error::`、把 exit code
与 stderr 尾部写进 `reason`，**步骤会红**）。所以：

- pin 的如果是 `@v1`，你不会再看到 `reason: "script failed"`；看到就说明**没拿到修复**——
  确认引用的是 `Ikalus1988/MisakaNet@v1`（或更新），而不是旧的 commit SHA / 旧 tag；
- 修好之后 `decision=error` 会带 `reason: "intake bot exited <code>"` 与 `stderr` 尾部，
  可以直接拿去报障。

### 8.3 "绿着、什么都不发"的三步判别法

1. **看该 step 的 `decision` 输出**（Job Summary、`steps.intake.outputs.decision`，或日志里的
   `RESULT: {...}`）：`error`/`skip` = bot 侧的问题，`hit`/`intake`/`ignore` = bot 工作了。
2. **看 `reason`**：`script failed` → 修复前的静默失败（§8.2，升到 `@v1`）；
   `intake bot exited N` → 脚本真的报错（看它附的 stderr 尾部）。
3. **绿 + 没有任何评论时，逐条排除**：

| 现象 | 含义 | 怎么办 |
|---|---|---|
| 步骤**红** + `decision=error` | bot / 参数 / 网络坏了（修复后的正常失败形态） | 读 `reason` 里的 exit code 与 stderr 尾部；先跑 §8.1 自检 |
| 步骤**绿** + `decision=error`（`reason: "script failed"`） | **修复前的静默失败**：绿着、什么都没发 | 升到 `@v1` 重跑；这就是 [#1825](https://github.com/Ikalus1988/MisakaNet/issues/1825) |
| 步骤绿 + `decision=skip` | 压根没拿到错误文本——典型是 workflow 写了 `permissions:` 却漏了 `actions: read`，读不到失败 job 的日志 | 补 `actions: read`，或用 `error:` / `log-file:` 显式传入（见 §2/§3） |
| 步骤绿 + `decision=ignore` | 正常：噪音 / 重复签名 / 缺证据，**不会 intake** | 无需处理；默认会在关联 PR 贴一条 `🚫 MisakaNet: Skipped`（带 `reason`），`comment-on-pr: false` 或无关联 PR 时才完全安静；想提高转正率可加 `what-tried:` |
| 步骤绿 + `decision=hit`/`intake` + 无评论 | 该 run **没有关联 PR**（如 main 上的定时任务），评论无处可贴；intake 上报本身照常 | 正常；要测评论路径用 `pr-number:` 手动指名 |

> 反过来说：**只要你看到过任何一条 bot 评论**（含 `🚫 Skipped`），就说明"读日志 → 跑脚本 → 贴评论"
> 这条链路是通的，问题只可能在 decision 本身；**一条都没有**时才优先怀疑 `error`/`skip`
> 与"没有关联 PR"这两类原因。

> 注意：**"没有失败可报"只会以 `ignore` 出现**，永远不会以 `error` 出现。
> 任何 `error` 都值得报障——把 `reason`（含 exit code / stderr 尾部）连同你的 workflow 片段
> 贴到 [#1550](https://github.com/Ikalus1988/MisakaNet/issues/1550) 或新开 issue 即可。
