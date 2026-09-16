# tmux 三 agent 链路验证 + 评估报告 — 2026-09-15（第二轮）

> 第一轮（`agent-chain-2026-09-15.md`）是逐个手动跑；这一轮**在 tmux 里并行跑**，三个窗口各一个 agent，
> 同一个问题，全部原始输出落盘。目的有两个：验证前一天那批修复在真实会话里**站得住**，以及看第一轮
> 之后新改的**入门示例**在真机上是否真的立刻有用。

## 1. 方法

```bash
Q='pip install timeout 是什么原因？'          # ← 就是 #1721 新换的入门示例
tmux new-session -d -s mn-chain -n claude   "$CLAUDE  -p '$Q' --output-format stream-json --verbose --permission-mode bypassPermissions > /tmp/chain2/claude.json"
tmux new-window  -t mn-chain -n hermes      "$HERMES  chat -q '$Q' -Q -v > /tmp/chain2/hermes.log"
tmux new-window  -t mn-chain -n openclaw    "$OPENCLAW agent --message '$Q' --session-key chain2-… --json > /tmp/chain2/openclaw.json"
```

三个窗口全部 **exit 0**；`tmux list-windows` / `capture-pane` 可随时 attach 复核。

## 2. 结果

| agent | 退出码 | 是否调用 `misakanet_search` | 是否取 lesson 正文 | 检索结果 | 回答 |
|---|---|---|---|---|---|
| **claude-haha** | 0 | ✅ ×2 | ✅ `get_lesson` ×3 | 命中 | 给出 5 类原因 + **复述经验**："我参考了别人的一条经验：装大包时把 `--default-timeout` 调到 120+，或直接切到清华/阿里镜像" |
| **hermes** | 0 | ✅ ×1（0.85s / 1836 字符）| — | ⚠️ **`no_match`**（见 §3）| 仍答对了（靠自身知识）|
| **openclaw** | 0 | ✅ ×1 | ✅ ×1 | 命中 | 给出镜像源/超时两类解法 |

**结论**：**3/3 全部真的在用 MisakaNet**（第一轮只有 2/3，OpenClaw 是修了 workspace 之后才通的），
其中两个 agent 走完了「检索 → 取正文 → 用经验作答」的完整链路，claude-haha 还按规则用大白话向用户
交代了经验来源。

## 3. ⚠️ 本轮新发现（已立案 #1725）

hermes 用**同一句话**检索却拿到 `no_match`，而另外两个 agent 命中了。差别只在它多传了一个 `domain`。
线上复现（同一个 query，只改 domain）：

| 调用 | 命中 |
|---|---|
| `{query: "pip install timeout", top: 3}` | **3** |
| `+ domain: "python"` | **0**（`no_match: true`）|
| `+ domain: "contrib"` | **3** |
| `+ domain: "devops"` | **0** |

**根因**：远端索引里的 `domain` 是**目录名**（`contrib`/`ops`/`core`…），不是 lesson 自己声明的
frontmatter `domain`（`python`/`devops`…）。而工具文档、`AGENTS.md`、lesson 模板都让人用 frontmatter 的值。
于是**照文档填 domain 的调用方会静默拿到"查不到"**（`no_match` 是合法返回，没有任何错误）。

这是本轮唯一一处"配置全对、行为错"的地方，也是最有价值的一条：它解释了为什么一个健康的 agent
会看起来"没在用经验库"。

**止血（本轮已做）**：`AGENTS.md` §3.2 写明过滤器的**实际词汇**并建议"不确定就省略 `domain`"。
**治本（#1725 候选）**：让索引生成器用 frontmatter domain —— 但会改变本地检索的 domain 加权，
`workers/search-floor-real-corpus.test.mjs` 等**标定测试需要重跑并显式更新记录**。

## 4. 入场示例的验证（#1721 的线上检验）

这一轮用的问题就是新换的 `pip install timeout`：claude-haha 与 openclaw **第一次检索就命中**，
claude 还取到正文并复述了经验。上一轮的示例（`docker exit code 137`）在同一条链路上只返回
"相关但不直接"的邻居课 —— **换示例这件事在真机上是可感知的差别**。

## 5. 过程记录：我自己的一次坏改动（被门禁拦住）

给 worker 的工具描述加 domain 口径说明时，我用 `'",'` 作锚点切字符串，**切坏了语法**：

```
node --check workers/register-proxy-sw.js → exit 1
node --test workers/*.test.mjs → pass 45 / fail 30
```

当场 `git checkout --` 回滚，恢复后 **245 passed / 0 fail**。教训与前几轮一致：**改字符串描述时用精确锚点，
并且改完立刻跑 `--check` + 全量测试**；这一批测试这次救下的是一条会被部署出去的 worker 语法错误。

## 6. 下一步（迭代清单）

1. **#1725 治本**：索引统一用 frontmatter domain + 重标定检索下限测试（先止血已做）。
2. **Codex 用户级钩子**仍未确证（安装器如实标注；不在本轮三 agent 之列）。
3. 回看第一轮的 `verify`：现在是握手探针（不耗配额）；可把"检索健康度"做成**独立**的一次带例子的
   自检（明确的用户动作），与 `--verify` 的"可达性"分开，避免两者职责混淆。
