# Handoff — 2026-10-22（第 16 卷，承接 handoff-2026-10-22-part2.md §138）

> 上一卷：`docs/maintainer/handoff-2026-10-22-part2.md`（§132–§138）　·　下一卷：`docs/maintainer/handoff-2026-10-23.md`（§1–§4）
> 本卷记三件事：**release-please 扫不动提交历史**（账本里没有这个包 → 没有基线 → 扇 1237 个 commit）、
> **`--verify` 把两件事判成了一件**（端点/可用性与安装完整性，各自独立判），以及
> **文件被"列出来了"和发版真的会动它是两件事**（`extra-files` 按包自身 path 解析，两条路径都被解析到不存在的文件）。
>
> 本卷从 `handoff-2026-10-22-part2.md` 拆出：上一卷写到这里已经 1028 行，超过
> `docs/maintainer/handoff-rules.md` 定下的 800 行上限。**拆分是规则要求的，不是可选项**——
> `tests/test_handoff_size_limit.py` 对超过上限的新文件会直接变红。
>
> 本卷正文里出现的"上一卷 §N"一律指 `docs/maintainer/handoff-2026-10-22-part2.md` 的 §N。

---

## 139. 工具让路的那一半：release-please 扫不动提交历史（2026-10-22）

### 现场

`handoff-2026-10-22-part2.md` §138 收尾时留了一笔："真正的 0.6.0 要等它合入后 release-please 重建发版 PR，
而那个 PR 必须自己变绿才能合。"

**它没有变绿，而且变不了绿。** 发版 PR #3451 上 18 条腿全红（9 unit + 9 e2e），
说的是同一件事：

```
FAIL version-matches-expectation — --version printed 0.5.6 but the installed package.json says 0.6.0
```

而 #3738（让版本字面量跟着发版走的那个修复）**已经在 main 里了**。
它进不去发版 PR 的分支——**因为没有任何东西去更新那个分支**。

### 真正的原因：不是"重跑一下就好"

`Release Please` 工作流在 main 上每次都失败：

```
release-please failed: Request failed due to following response errors:
 - Something went wrong while executing your query on 2026-10-22T14:27:06Z.
```

两次运行（attempt 1 / attempt 2，手动重跑的那次也是同一个位置）停在同一处：
**第 29 页左右、290 个提交**。

### 根因：账本里没有这个包

`packages/misakanet-setup` 是 #3691 才加进 manifest 的包，**从来没有被 release-please 发过版**，
所以发版账本 `.release-please-manifest.json` 里**没有它的条目**。

release-please 靠这个条目回答"这个包的历史从哪开始"（`src/manifest.ts`）：

```ts
const expectedVersion = this.releasedVersions[path];
if (!expectedVersion) {
  this.logger.warn(`No version for path ${path}`);
  continue;
}
```

没有条目 → 没有基线 → `needsBootstrap` → 提交扫描**不会提前 break**，
只能从仓库开头一路走回来：HEAD → `misakanet-setup-v0.5.6` = **1237 个提交**。

**而这条路径上唯一能收住扫描的，是 `bootstrap-sha`。**

### 这不是配额耗尽，但**也不完全是我当时写的那个原因**

两处实测：

- 失败时刻查 `gh api rate_limit`：`graphql remaining 4974 / 5000` —— 点数配额**几乎没动**；
- 手工用 release-please 原样的 GraphQL 查询重放（**新请求，不是重试**）：**第 9 页**就以同样的报错失败，
  紧接着的下一次请求立刻失败。

**当时我把这写成了"GitHub 对一串重查询的次级限制"。这个归因是错的**，
而且是 2026-10-22 晚些时候 GitHub 官方状态页给出的答案：

| 时间 | GitHub 事件 |
|---|---|
| 14:18–15:18 | "Incident with Actions Results"（Actions 结果处理延迟） |
| 15:28–（仍在 investigating） | "Errors loading Issues, Pull Requests, and search results"，Actions / Issues / PR 全部 `degraded_performance` |

而 release-please 的失败时间点是 **14:26、14:56、15:28、15:30、16:02、16:09** ——
**落在事故窗口里**，并且**有一次成功（15:34–15:37）也发生在同一个事故窗口内**。

这解释了之前对不上的所有细节：报错位置随节奏漂移（第 9 页 / 第 29 页 / 第 1 页）、
配额没动、**新请求也会失败**——这不是限流（限流会退避、会随时间恢复），
这是 **API 侧在降级**，而 GitHub 在这种状态下的 GraphQL 报错就是这一句没有细节的
"Something went wrong while executing your query"。

**但根因那一半仍然成立**：账本里没有条目 → 没有基线 → 扫描要从仓库开头走 **1237 个提交**
（50 次 GraphQL 往返）。这意味着**发版在最不该依赖 API 状态的时刻，最依赖 API 状态**。
`bootstrap-sha` 把它收到 143 个提交（15 次往返），这是**独立成立的改进**。

**不能说的话**：不能说"这个修复让发版能跑通了"。
唯一跑通的那次（15:34）发生在事故窗口内，**它证明不了修复有效**，只证明那次运气好。
修复的理由是"少走 87% 的路"，不是"它修好了这个故障"。

### 修法：一个顶层键

`release-please-config.json` 的顶层加：

```json
"bootstrap-sha": "4e3d15af7a68f35e0485e6cff26f9c0936a87b97"
```

`4e3d15af` 是 `c8c53aa0`（"docs(dsh): what the plugin actually gives" #3398）的父提交，
也就是 **0.6.0 备注里最旧的那条 setup 改动**之前。

| | 之前 | 之后 |
|---|---|---|
| 扫描的提交数 | 1237 | **143**（约 15 页，在墙以内） |
| 0.6.0 的 setup 备注 | 六条 | **还是那六条**（不是一份被截短的列表） |

> action 的输入里**没有** `bootstrap-sha`，但**配置文件有**（顶层键，
> `schemas/config.json` 认，`additionalProperties: false` 所以只能写这个键名）。
> 这一点值得记住：**release-please 的"配置文件"比它的"action 输入"多几个旋钮**。

### 两条必须一起记下来的边界

1. **这个 bootstrap 会过期。**
   0.6.0 合入后 release-please 自己会把 setup 路径写进账本，基线改由 tag 回填，
   `bootstrap-sha` 自动失效——**但要在 0.6.0 发版之后把它删掉**。
   一个活过用途的 bootstrap 会**静默截断**将来的 changelog，而不是响亮地失败。
2. **0.6.0 的 setup 备注仍然少了一些东西，而且这一节没有修好它。**
   真正未发布的 setup 改动有 **19 个**
   （`git log misakanet-setup-v0.5.6..HEAD -- packages/misakanet-setup integrations/agent-autostart`），
   而备注只列了 6 条——其余的在 `commit-search-depth` 默认的 500 提交之外
   （`#3404`、`#3398` 之后还有 `#2245`、`#2197`、`#2144` 等）。
   `bootstrap-sha` 把扫描收到 143，**没有补上这个缺口**，只是没有让它更糟。
   诚实的说法是：**0.6.0 会带上这些改动，但备注里不列。**

### 元教训

> `handoff-2026-10-22-part2.md` §138 说"一道门禁能抓住'人忘了'，不等于它能抓住'工具忘了'"。
> 这一节是它的下半句：**一道门禁抓得住漂移，也不等于发版流程走得到终点。**
>
> #3738 让"字面量跟着发版走"这件事**对**了——但如果发版流程本身跑不完，
> 这条正确性就没有任何机会生效。
> **先证明流程能跑完，再证明流程跑出来的东西是对的。**

### 第二条元教训（这一节最贵的部分）

> **我在事故期间把"API 在降级"诊断成了"我在被限流"，并且把这个错误诊断写进了 handoff。**
>
> 两个证据当时就在手上：一个是我自己的探针（新请求也会失败——限流不会这样），
> 一个是配额读数（4974/5000，点数几乎没动——限流会动）。
> 我把它们解释成了"次级限制"，因为那个解释能解释"位置漂移"，
> 而"API 在降级"我当时没想到去查。
>
> **一个能解释现象的解释，不等于正确的解释。** 区别在于：
> 正确的解释会**预测**下一次观察。限流预测"等一会儿会恢复"；
> 降级也预测"等一会儿会恢复"——所以光靠等待分辨不出来。
> 分辨靠的是**去查那个能直接回答问题的外部事实**（GitHub 的状态页），
> 而不是靠手里已有的两个弱证据。
>
> 教训很具体：**当你的诊断解释了一个现象、而另一个诊断也能解释同一个现象时，
> 去找那个能一次性判定对错的源**，别在两个都能自圆其说的解释里挑一个顺眼的写进文档。

## 140. `--verify` 把两件事判成了一件（#3696）

### 现场

OpenClaw 试用者的机器：workspace 是 root 拥有的、只读。`--verify` 给出的是

```
OpenClaw：规则块没装（/root/.openclaw/workspace/AGENTS.md）→ 重跑安装命令
```

**这条建议恰恰是唯一无效的那一条**：文件写不进去，重跑写进去的量和上一次一样。
于是他去查网络、查权限、查网关——而真正的堵点安装器上一轮已经说过了。

### 两个问题，不是一个

- **建议和成因对不上**："没装"（不在）和"装不了"（写不进）是两个事实、两套修法，
  而校验器只问了"文件在不在"，**从来没问过"能不能写"**。
  它现在用安装器写之前用的那个问法（`canCreateHere`），写不进的文件说"装不了"并给出**能work的**修法。
- **用一个问题的事实回答另一个问题**：输出只有一个 NOT READY，
  而这台机器有两个互不相干的事实：**端点答不答应**（能不能用 MisakaNet）、
  **我们偏好的文件写没写**（安装完整性）。端点完全正常、workspace 只读的机器是**能用的**，
  而旧判定说它 NOT READY。

所以输出改成两段，各自一条判定，一段不成立不判死另一段：

```
── 端点/可用性 ──
  ✓ 端点可达：https://misakanet.org/mcp（MCP 握手成功，8 个工具）

── 安装完整性 ──
  ! OpenClaw：规则块装不了（…）→ 只读或权限不足，重跑也写不进去 → 改权限（或换到可写的目录）后再重跑

可用性：就绪 —— 端点可达，检索与读取可用
安装完整性：不完整 —— 2 项需要手动处理（上面每条 ! 都给了成因和做法）
```

报告里长出对应的两个字段（`endpoint-usable` / `install-complete`），
**收集报告的机器不必去解析散文**就能分清"我们的文件写不进去"和"端点不应答"。

### 没有变的：退出码契约

`verify: NOT READY` 仍然表示"两半里有一半有问题"，`--strict` 仍然不放过它。
变的是：**输出说了是哪一半，以及该做什么。**

### 第三件事：token 那一行说的是哪个 token

它读的是**本安装器自己的状态目录**，所以通过别的通道（mcporter、网关）拿到 token 的机器会显示"无 token"，
而那句 `skip` 又让人读成"什么都没装"。现在这一行说清了两件事：
**它只看得到自己的状态目录**，以及**读路径完全不受影响**。

### 三条测试，断言的是措辞和建议，不是"有输出"

- 只读的 `AGENTS.md` 是"装不了"、不是"没装"、且不带"重跑安装命令"；
- 两段不互相污染，且安装失败时端点判定仍然是"就绪"；
- token 那一行说清自己的范围。

## 141. 文件被"列出来了"，和发版真的会动它，是两件事（2026-10-22）

### 现场

`bootstrap-sha` 合入之后，**Release Please 有一次跑通了**（attempt 3，2026-10-22T15:37Z）——
提交扫描 143 个提交，发版 PR 被重建。
（这一次发生在 GitHub 事故窗口内，**它不能证明 bootstrap-sha 修好了什么**，见 §139 的更正。）

然后去看字面量：

```
$ gh api .../contents/packages/misakanet-setup/bin/misakanet-setup.mjs?ref=<发版 PR 的 head>
160:const VERSION = '0.5.6'  // x-release-please-version
```

**标记在，值没动。** 而同一个分支上 `packages/misakanet-setup/package.json` 已经是 `0.6.0` ✓。

> **这一节的证据不受当晚那次 GitHub 事故影响**：它不是从"CI 红了"推出来的，
> 而是直接读**发版分支上的文件内容**（`package.json` 已 0.6.0、字面量仍 0.5.6）
> 加上**上游源码里 `addPath` 的实现**——两条都不依赖 GitHub 那晚是否在降级。
> （§139 的失败归因受影响，这一节的**发现**不受影响：文件内容不会撒谎。）

### 两个事实拼在一起才是真相

- `package.json`（**包自己的** manifest）由 node strategy 更新 → 动了 ✓；
- 两个 `.mjs` 字面量在 `extra-files` 里 → 没动 ✗。

差别不在"更新器会不会处理 .mjs"，而在**路径**。

### release-please 怎么解析 extra-files

`BaseStrategy.addPath`（`src/strategies/base.ts`）：

```ts
protected addPath(file: string) {
  if (!this.path || this.path === ROOT_PROJECT_PATH || file.startsWith('/')) {
    file = file.replace(/^\/+/, '');
  } else {
    file = `${this.path.replace(/\/+$/, '')}/${file}`;
  }
```

**带 path 的包，extra-files 是相对那个 path 解析的**；只有以 `/` 开头的路径才是"相对仓库根"。

setup 包的 path 是 `packages/misakanet-setup`，所以配置里这两条

```
packages/misakanet-setup/bin/misakanet-setup.mjs
workers/misakanet-setup.test.mjs
```

解析成

```
packages/misakanet-setup/packages/misakanet-setup/bin/misakanet-setup.mjs   ← 不存在
packages/misakanet-setup/workers/misakanet-setup.test.mjs                   ← 不存在
```

而更新器**对不存在的文件一声不吭**（`createIfMissing: false`）——**没有报错，没有警告，
只是没动**。

### 为什么上一卷 §138 的门禁没抓住

上一卷 §138 的门禁做了两件事：转写 release-please 的**标记规则**（`x-release-please-version`），
断言每个版本字面量都**列在** extra-files 里。两件都成立，而且都正确。

**缺的是第三条规则：路径怎么解析。**

"文件被列出来了"和"发版真的会动它"之间隔着一次路径解析——而这一次解析把两处列表
都指向了不存在的文件。根包的条目没事（根包的 path 就是根，按写的解析），
所以门禁看到的一切都自洽。

### 修法：一条路径规则 + 一条门禁

配置改成以 `/` 开头（release-please 据此认为是"相对仓库根"）：

```json
"extra-files": [
  "/packages/misakanet-setup/bin/misakanet-setup.mjs",
  "/workers/misakanet-setup.test.mjs"
]
```

门禁补上转写上游 `addPath` 的那一条，并断言**解析之后**确实存在文件——对**每一个包**，
不只是这一个：

```python
def _release_please_add_path(package_path: str, file: str) -> str:
    """release-please's `BaseStrategy.addPath` (src/strategies/base.ts), transcribed."""
    if not package_path or package_path == "." or file.startswith("/"):
        return file.lstrip("/")
    return f"{package_path.rstrip('/')}/{file}"
```

它对**旧配置**如实变红：

```
AssertionError: the extra-files entry 'packages/misakanet-setup/bin/misakanet-setup.mjs' of
the package 'packages/misakanet-setup' resolves to
'packages/misakanet-setup/packages/misakanet-setup/bin/misakanet-setup.mjs', and that file does
not exist — release-please skips a missing file silently, so the release would not move whatever
version it carries
```

### 元教训（这一节最值钱的一句）

> **上一卷 §138 写的是"门禁的门禁"——转写并执行发版工具的规则，才能证明发版真的会动它。**
> **而这条规则本身有三条：标记规则、列表规则、路径规则。**
> 我转写了第一条、断言了第二条，**漏了第三条**，于是门禁在一份"看起来完全正确"的配置上通过了。
>
> 这不是"门禁写错了"，是**"我把规则数少了"**。
> 一条规则有三条子规则的时候，"转写了规则"这句话本身就得再被检查一遍。
>
> 更一般的一句：**当一个门禁的对象是"别人的工具的行为"时，
> 门禁的强度等于你转写的规则条数 ÷ 实际生效的规则条数。**
> 这个比值没有人算过，所以必须**逐条**数——
> 而逐数的唯一办法是去读上游源码，而不是读自己上一次的 handoff。

## 142. 一行配置被静默删掉：整文件重写是"删除别人的键"的最短路径（2026-10-22）

### 现场

#3741 把 `bootstrap-sha` 加进了 `release-please-config.json`。两次提交之后，它不在 main 上了。

不是被谁 revert 的——**#3744 的那一次提交自己删掉了它**。那个提交要改的是同一个文件的另一处
（给 setup 包的 `extra-files` 加 `/` 前缀），但它的 diff 长这样：

```diff
@@ -1,7 +1,6 @@
   "signoff": "misakanet-bot <bot@misakanet.dev>",
-  "bootstrap-sha": "4e3d15af7a68f35e0485e6cff26f9c0936a87b97",
   "packages": {
```

**那个分支的父提交就是 #3741**（`66b053ac`），所以这不是合并冲突、不是 rebase 丢的、也不是
"忘了"——是那次编辑**把整个文件重写了一遍**，而重写用的那份内容来自一个更早的基线。
于是上一轮刚合进去的键，跟着旧基线一起被写回。

### 怎么发现的：不是靠门禁，是靠日志里一行字

两次 release-please 跑挂掉的方式，和 #3741 之前一模一样：

```
⚠ Expected 2 releases, only found 1
⚠ Missing 1 paths: packages/misakanet-setup
⚠ No version for path packages/misakanet-setup
```

`No version for path` 这一行才是证据：它说的是"账本里没有这个包的条目"，
所以扫描没有起点。而账本里**本来就不该有**那个条目——那个包从未被 release-please 发过版。
真正的问题不是账本，是**地板没了**：没有 `bootstrap-sha`，扫描就没有下限，
只能从仓库开头走（1237 个 commit），走不完。

**这件事没有门禁能报**，因为当时没有任何一条门禁知道"地板应该存在"。
所以补的不是一条"检查这个键在不在"的断言，而是**把上游判定抄下来**：

```python
expected_releases = len(config["packages"])       # upstream: Object.keys(strategiesByPath).length
releases_found = len(ledger)                      # upstream: this.releasedVersions
needs_bootstrap = releases_found < expected_releases
```

`needs_bootstrap` 为真时，配置**必须**带 `bootstrap-sha`；账本对每个包都有条目之后，
配置**必须不再**带它——过期地板会静默截断未来的 changelog，而不是响亮地失败。
两个方向都抄，因为这两个方向都是**会安静地错**的。

### 元教训

> **改一份共享配置文件时，"我改了哪几行"和"这个文件现在是什么样"是两件事。**
>
> 整文件重写会把**你没有打算改的键**一起带回旧基线——那些键是**别人**（上一轮的你、或者某个 PR）
> 在同一份文件上刚加的，而它们的正确性对你正在做的那件事完全不可见。
>
> 定点编辑（只改目标行）不会犯这个错，代价是"要先把文件读一遍"。
> 这笔账很划算：**多读一遍文件，比多跑一次发版流水线便宜**。

第二条，来自 §141 的教训：

> **门禁要覆盖"别人会怎么改这个文件"，而不只是"这个文件现在对不对"。**
>
> §141 的门禁问的是"配置现在对吗"，它对"配置从别人手里交回来之后还对吗"一无所知。
> 这次丢键不是配置错了，是**配置对了但中间少了一步**——
> 而那一步没有任何东西在看。

**给下一轮的一句操作提醒**：
改 `release-please-config.json`、`release-please-manifest.json`、任何 workflow YAML 这类
**多方共享的文件**时，用定点编辑；合完之后看一眼 `git show <sha> -- <file>` 的 diff 行数——
**一行只该有一行的 diff**。
