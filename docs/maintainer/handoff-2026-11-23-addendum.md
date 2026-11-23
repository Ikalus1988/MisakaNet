# Handoff — 2026-11-23（vol 45 补遗：发版 + 三个悬账）

> 承接 `handoff-2026-11-23.md`（vol 45）。这一卷三件事：**把 3.20.0 发出去**、把 vol 45 §3 那三笔
> 悬账拆开、以及发版过程中露出的一条"每次发版都留一条红 run"的缺陷。

---

## 1 判断

### 1.1 发版链条：第二个 publish 运行必须活得过 npm 自己的处理时间

一个 release 会有**两个** publish 运行（`release` 事件 + 一次 dispatch，`misakanet-publish.yml`
的注释写明这是故意的，用来兜住丢事件）。第二个运行撞到 E409 后要读 npm 确认版本是否真的 live，
而它只读 6 次 × 15s = **90 秒**。

实测 2026-11-23 的 3.20.0：05:06:55 `npm publish` 被接受、npm 回"being processed and may take a
few minutes"；registry 读侧约 **05:11 才看到 3.20.0（~245 秒）**。于是第二个运行在 90 秒时判
"NOT live" 并失败 —— 而那次发版其实完全正常。

**判据**：一个探测窗口的长度要来自**对面声明的处理时间**（npm 自己说"几分钟"），不是上一次观测到
的 gap（11-17 是 98 秒，于是被写成 90 秒"覆盖"）。差一点点覆盖，等于没覆盖。

这条修完（`NPM_STANDDOWN_POLL_ATTEMPTS` 6 → 20）之后，真 staged 的版本仍然会失败，只是晚 4 分钟
且给的是同一条"去 npmjs.com 批准"的提示。

### 1.2 公共面的计数单位是"谁写的"，不是"谁复制的"

gate 的"裸提及重复三次"这条路，读的是**整份渲染后的文件**；而 `title`/`summary_plain`/`trigger`
是 `render()` 从正文首句**复制**出来的。于是一次写作变成三次出现，句中的一个连字符英文短语就被
当成命令名。

实测：29 条被拦的候选里 **18 条只卡在这一条路**（`checked-in`、`task-list`、`exhaust`、`arrival`、
`vacancy`、`single-job`、`scientific-notation`……）；把计数对象改成正文后 **13 条立刻可转**，
而带真证据（code span / shell fence / prompt）的 17 条**一条没松**——包括 #5525 的四个私有键
（`requires_openai_auth` 等）和 #4903 的 `token_tool`。

**判据**：任何"N 次出现"的判据，先问这 N 次是**同一个人分别写的**，还是**流水线复制的**。

### 1.3 `needs-ac` 不是一支队列，是五个群体

46 条打开着的（2026-11-23 实测）：12 条是 intake 提交（判据本来就在代码里）、4 条 owner 问题
（只有裁决能关）、4 条赏金、6 条周期报告（报告存在 ≠ 完成）、20 条 bug/任务（合并提交引用
**且**它点名的可观测量变了）。

**判据**：先按"**谁能关**"分组，再谈 done。"被合并提交引用"是证据不是证明 —— #4640 被 #4684
引用，而它自己那段线程说 D2 of 4 落地了。

---

## 2 数字（2026-11-23 第二段收工）

| 项 | 值 | 判据 |
|---|---|---|
| 语料 | **1143**（vol 45 的 1130 → +13） | `data/lessons.json` |
| 公共面被拦 | **17**（原 29） | `convert_intake_batch.py` |
| `needs-ac` | 46，已按五群体分组 | `docs/maintainer/needs-ac-ledger-2026-11-23.md` |
| 发版 3.20.0 | tag + GitHub Release + **npm** + **PyPI** + **GHCR** 全部落地 | 见 §3 的渠道表 |

发版五条渠道的实测（3.20.0，2026-11-23）：

| 渠道 | 结果 | 读法 |
|---|---|---|
| git tag / GitHub Release | `v3.20.0`，release-please 自动打 | `gh release view v3.20.0` |
| npm `misakanet` | **3.20.0**（accept 后约 245 秒才在读侧可见） | `curl registry.npmjs.org/misakanet`，别信 run 的绿色 |
| PyPI `misakanet` | **3.20.0**（`release-pypi.yml` 的 workflow_dispatch） | `curl pypi.org/pypi/misakanet/json` |
| GHCR 容器 | success | `Publish Container to GHCR` |
| 插件市场 / OpenClaw 侧 | 走 `publish-*` 各自通道，不在本卷范围 | —— |

---

## 3 悬着的账

- **只有 owner 能点**（`docs/maintainer/needs-ac-ledger-2026-11-23.md` 里逐条写了理由）：
  #5245（被 #5421 引用，但那条是"看见截断"的 CI 侧修复）、#4640（D1–D4 只剩三项）、#5117；
  以及 46 条里属于"owner 问题"的那 4 条 —— 只有裁决能关。
- **等提交者**：133 条缺段落，其中 88 条只缺原因。**#3828** 已留评论：它要的是一句
  `## Verification`（weight 297 < 400，地板不降）。
- **等一次真跑**：`update-lessons.yml` 下一次运行要发 13+13 条回执（vol 45 的 13 条 + 本卷 13 条）
  并落地再生 PR。
- **等 CI**：#5612（npm 轮询窗口）合并后，下一次发版才不会再留一条红 run。
- **公共面剩下的 17 条**：其中 4 条卡在私有键上（#5525 一族），那需要**改写**（`public_analogue:`），
  不是加 allowlist —— 这是唯一还没有机械解法的一格。

---

## 4 下一轮入口

```bash
# 发版后核对"到底发出去了没有"——读 registry，不读 run 的颜色
curl -s https://registry.npmjs.org/misakanet | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['dist-tags'])"
curl -s https://pypi.org/pypi/misakanet/json | python3 -c "import json,sys;print(json.load(sys.stdin)['info']['version'])"

# 队列五格 + 公共面剩余
GITHUB_TOKEN= PYTHONUTF8=1 PYTHONIOENCODING=utf-8 python scripts/convert_intake_batch.py

# needs-ac 分组（标题形状即可分，不需要读正文）
gh issue list --repo Ikalus1988/MisakaNet --state open --label needs-ac --limit 80 \
  --json number,title --jq '.[] | "\(.number) \(.title)"'
```

---

## 5 坑（本卷实际踩到的）

1. **`git checkout live-main` 会把上一个分支的提交带过来**：本卷把 vol 45 的提交落在了
   `live-main` 上、而分支还停在旧 head，`gh pr create` 报 *"No commits between main and …"*。
   判据：提交后先 `git branch --show-current`，再 push。
2. **Python 里调 `gh` 要剔除 `GITHUB_TOKEN`**：宿主注入的那个是失效的，`subprocess` 不剔除就
   401（`json.loads` 直接炸在空输入上）。`env = {k:v for k,v in os.environ.items() if k != "GITHUB_TOKEN"}`。
3. **release 产物的版本号不要手改**：`.release-please-manifest.json`、`package.json`、
   `.codex-plugin/plugin.json`、`pyproject.toml` 全由发版 PR 带；手改会与 manifest 漂移。
4. **"发版 PR 合并成功"不等于"发出去了"**：`release` 事件的 run 会在 npm 仍在处理时就返回绿色
   （"+ misakanet@3.20.0" 只是 accept）。核对必须读 registry（§4 第一行）。
