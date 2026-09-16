# Setup 健康度卡口 —— 把 `--report` 接进 CI

> 状态：**已实现**（`packages/misakanet-setup` ≥ 0.5.4）
> 实现：`packages/misakanet-setup/bin/misakanet-setup.mjs`（`--report --strict` / 别名 `--ci`）
> 测试：`workers/misakanet-setup.test.mjs`（`--report --strict` 四项 + 既有的"不泄露 token"项）
> 来源：#1767 的 A3 → **#1782**（本文就是该 issue 的"可直接复制的 workflow"那一条）

## 为什么需要它

`--report` 早就输出一段脱敏 YAML（`schema: misakanet-setup-report/1`，含 `verify` / `permissions` /
`endpoint-tools` / `open-items`），但它**永远退出 0** —— 这是**刻意的**：那份 YAML 是要贴进 issue、
贴进 CI 日志给人看的，退出码非 0 会把"收集证据"变成"红掉的步骤"。

代价是 CI 用不了它：环境坏了和好了一样。

所以现在**两种契约并存**，而不是把老的改掉：

| 调用 | 行为 |
|---|---|
| `--report` | 打印报告，**只要报告印出来了就退 0**（保持原样，别去"修"它） |
| `--report --strict`（或 `--ci`） | 打印**同一份** YAML，然后用退出码表态 |

关键点：strict 模式**先打印完整 YAML，再按退出码表态**。CI 因此可以"把证据贴进 job summary
**并且**让这一步变红"，而不是二选一。

## 退出码

| 码 | 含义 | CI 该怎么处理 |
|---|---|---|
| `0` | **READY** —— 报告里 `verify: READY` 且 `open-items: 0` | 绿 |
| `1` | **NOT READY** —— `verify: NOT READY`，**包括 `open-items > 0`** | 红：**机器**不健康。YAML 的 `open-items-detail` 里每条都带修法，照着修 |
| `2` | **跑不起来** —— 报告**根本没生成**（stdout 里没有 YAML，stderr 一行原因） | 红：**工具**坏了（或它读不懂这份配置），**不要去修机器** |

这与本仓既有的约定一致（`scripts/check_workflow_scripts.py` 的
`0 = no findings, 1 = findings, 2 = cannot run`）。1 和 2 分开的意义就是这一句话：
**"环境不健康"要修环境，"检查器跑不起来"要修检查器** —— 混成一个码，CI 只会告诉你"红了"。

## 两个字段**永远**不参与判定

报告最后两行是**人手填**的空白字段：

```
# Fill these two in (see the bounty for how):
tools-visible: {}          # e.g. {codex: 7} — from `codex mcp list` / `codewhale mcp tools`
live-call-evidence: ""     # one line your agent printed when it called misakanet_search
```

它们是给报料人在**报告生成之后**手填的（悬赏要的就是这两行）。工具**从不回读**它们，退出码也
**完全不看**它们 —— 一条测试（`--report --strict exits 0 on a READY machine, and the human fields
never gate it`）就把这件事钉住：一台 READY 的机器，在这两个字段**都还是空白模板**时，strict 必须退 0。

理由很直接：**一个依赖"报料人记得填"的卡口，不是卡口。** 今后任何"顺手校验一下这两个字段"的
改动都是错的，哪怕看起来更严格。

## 复制即用的 job

把下面这段整块贴进你的 workflow（或本仓的 `.github/workflows/`）。它**只读**：`--report` 不写任何
文件、不改任何配置。

```yaml
name: Setup health

# 回答一个问题：这台机器的 MisakaNet 接线还健康吗？
# 注意这不是"跑一遍安装器"—— 装是装，健康是健康。
on:
  pull_request:
  workflow_dispatch:

permissions:
  contents: read

jobs:
  setup-health:
    # 想判一台**真**机器（有自己的 agent 目录），就把这行换成 self-hosted runner。
    # GitHub-hosted runner 上通常没有 agent 目录，于是这一步会走下面的 skipped 分支 —— 这是预期行为。
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1  # v7

      - uses: actions/setup-node@820762786026740c76f36085b0efc47a31fe5020  # v7
        with:
          node-version: '22'

      # ① 先确认这台 runner 上有"可判"的对象。
      #    没有 agent 目录时，--report 只能描述一台"什么都没装"的机器 —— 那是**判不了**，
      #    不是**不健康**。GitHub 的 job 不能动态 skip，所以这里退 0，并在 summary 里写明 skipped。
      - name: Is there an agent directory to judge?
        id: agent
        run: |
          if [ -e "$HOME/.claude" ] || [ -e "$HOME/.claude.json" ] \
            || [ -e "$HOME/.codex" ] || [ -e "$HOME/.hermes" ] \
            || [ -e "$HOME/.openclaw" ] || [ -e "$HOME/.codewhale" ]; then
            echo "present=true" >> "$GITHUB_OUTPUT"
          else
            echo "present=false" >> "$GITHUB_OUTPUT"
            {
              echo '## MisakaNet setup health — ⏭️ skipped'
              echo ''
              echo '这台 runner 上没有 agent 目录（`~/.claude`、`~/.codex`、`~/.hermes`、`~/.openclaw` 都没有），'
              echo '所以 `--report` 只能描述一台"什么都没装"的机器：那是**判不了**，不是**不健康**。'
              echo 'GitHub 的 job 不能动态 skip，于是这里退 0 并把 skipped 记在 summary 里。'
              echo '想让它真的判：换成 self-hosted runner，或看下文「让 runner 真的能判」。'
            } >> "$GITHUB_STEP_SUMMARY"
          fi

      # ② 跑卡口。`set +e` 是必须的：`run:` 默认是 `bash -e`，不关掉的话
      #    第一步非 0 退出就会在拿到退出码之前把这一步掐掉 —— 退出码正是这里唯一要的东西。
      - name: Run the report in strict mode
        id: report
        if: steps.agent.outputs.present == 'true'
        run: |
          set +e
          npx -y @misaka-net/misakanet-setup --report --strict \
            > setup-health.yaml 2> setup-health.err
          CODE=$?
          set -e
          echo "code=$CODE" >> "$GITHUB_OUTPUT"
          {
            echo "## MisakaNet setup health — exit ${CODE}"
            echo ''
            echo '```yaml'
            cat setup-health.yaml
            echo "exit=${CODE}"
            echo '```'
            if [ -s setup-health.err ]; then
              echo ''
              echo '**stderr**'
              echo '```'
              cat setup-health.err
              echo '```'
            fi
          } >> "$GITHUB_STEP_SUMMARY"

      # ③ 退出码就是判定。1 与 2 都让这一步红，但要说清是"修机器"还是"修工具"。
      - name: Gate on the exit code
        if: steps.agent.outputs.present == 'true'
        run: |
          case "${{ steps.report.outputs.code }}" in
            0) echo "✅ READY" ;;
            1) echo "::error::NOT READY —— 环境不健康；见 job summary，里面每条 open item 都带修法"; exit 1 ;;
            2) echo "::error::报告没生成（退出码 2）—— 是工具跑不起来，不是机器不健康；见 summary 里的 stderr"; exit 1 ;;
            *) echo "::error::未知退出码：${{ steps.report.outputs.code }}"; exit 1 ;;
          esac
```

### 为什么"没有 agent 目录 → skipped"而不是 failure

`verify` 的判定标准是"**这台机器上的 agent 接线能不能用**"：端点可达、MCP 已注册、钩子会触发、
只读工具已放行。一台干净 runner 上，标准答案就是 `NOT READY`（`open-items` 里会是
"端点不可达 / 钩子缺失"，如果连端点都出不去）。把它当成红，等于**每次 PR 都因为它自己制造的红而
失声** —— 那样一周之内所有人都会开始无视这个检查。所以：

- 没有可判对象 → 记 `skipped`（job 不能动态 skip，用 summary + 退 0 表达），**不红**；
- 有可判对象 → 健康度由退出码说话，`1`/`2` 都红，且原因分开。

### 让 runner 真的能判（可选）

如果你要的不是"某台真机器健不健康"，而是"**安装器今天还能不能产出一个健康的家目录**"
（一个真正的冒烟测试），就让 runner 先长出一个 agent 目录再判：

```yaml
      - name: Make the runner look like a machine with an agent
        run: |
          mkdir -p "$HOME/.claude"
          printf '{}\n' > "$HOME/.claude.json"
          # 只读安装：不注册匿名节点（不需要网络到 misakanet.org 就能写配置）
          npx -y @misaka-net/misakanet-setup --no-register
```

这一段之后上面的 job 就会真的跑出 `0`/`1`/`2`。注意两点：它需要 runner 能访问
`misakanet.org`（`verify` 要握手一次 `tools/list`，离线会诚实地报 `NOT READY`）；它断言的是
**安装器**的能力，不是某个用户的机器。这种 job 在本仓自己的 GitHub-hosted runner 上也是**有意义**的
—— 它变成"安装器 + 检测逻辑"的端到端回归。

## 本地复现三种退出码

```bash
TMPHOME=$(mktemp -d)
export MISAKANET_ENDPOINT=http://127.0.0.1:9/mcp    # 死端口 = 确定性的 NOT READY

# 默认：永远 0（报告照样打印，verify: NOT READY）
node packages/misakanet-setup/bin/misakanet-setup.mjs --home "$TMPHOME" --report; echo "exit=$?"
# → exit=0

# 卡口：NOT READY → 1（YAML 仍然完整打印在 stdout）
node packages/misakanet-setup/bin/misakanet-setup.mjs --home "$TMPHOME" --report --strict; echo "exit=$?"
# → exit=1   （stderr: --strict：NOT READY（…）→ 退出码 1）

# 跑不起来 → 2：报告生成中途抛错，stdout 为空，stderr 一行原因
mkdir -p "$TMPHOME/.claude" "$TMPHOME/.codex"
printf '{"mcpServers":{}}\n' > "$TMPHOME/.claude.json"
printf '{}\n' > "$TMPHOME/.claude/settings.json"
node packages/misakanet-setup/bin/misakanet-setup.mjs --home "$TMPHOME" --no-register >/dev/null
printf '{"hooks":{"Stop":[{"hooks":5}]}}\n' > "$TMPHOME/.claude/settings.json"   # 工具读不懂的形态
node packages/misakanet-setup/bin/misakanet-setup.mjs --home "$TMPHOME" --report --strict; echo "exit=$?"
# → exit=2
```

（`mktemp -d` 的临时家目录是为了永远不动你自己的配置，与本仓测试的
`workers/misakanet-setup.test.mjs` 用 `makeHome()` 做的事一样。）

## 三个坑

1. **别用管道拿退出码**：`npx … --report --strict | tee out.yaml` 的退出码是 `tee` 的，不是卡口的。
   要么 `> out.yaml`，要么显式取 `${PIPESTATUS[0]}`。这个坑在本仓有专门记录
   （`docs/maintainer/handoff-2026-09-15.md`）。
2. **别把 `--report` 默认模式的退出码改成跟判定走**：现有用户把它当"证据收集器"用（贴 issue、
   贴 CI 日志），改了就是破坏性变更。要卡口就显式 `--strict` / `--ci`。
3. **别把 `2` 并入 `1`**：`2` 意味着"没判"，把它说成 NOT READY 会让维护者去修一台没问题的机器。

## 相关

- 安装器与全部 flag：`packages/misakanet-setup/README.md`（"Exit codes" 一节）
- 报告字段与人手填字段：`--report` 的输出本身（`schema: misakanet-setup-report/1`）
- 测试：`workers/misakanet-setup.test.mjs` → `node --test workers/misakanet-setup.test.mjs`
- issue：#1782（本文对应）、#1767 A3（来源）
