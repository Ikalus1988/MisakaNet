# Code scanning 处置记录 — 2026-09-30（19 条 HARDCODED_SECRET + 2 条 RISKY_APPROVAL + 1 条真缺陷）

> 触发：09-30 一天里 open 告警从 4 条涨到 **22 条**。本文件把每一条归到根因，附**可复算的命令**，
> 并写清哪些**不能**在仓库侧修。
>
> 复算前提：一个能读 code scanning 的 GitHub token（本仓 `scripts/gh_push_via_api.py` 的取 token 顺序：
> `$GITHUB_TOKEN` / `$GH_TOKEN`，再退到 `~/.git-credentials`）。

## 0. 结论

| 类别 | 条数（告警 / 文件） | 根因 | 能否仓库侧修 |
|---|---|---|---|
| HARDCODED_SECRET — 测试夹具/占位符 | 8 / 8 | 脱敏测试用的假凭据字面量 | 能（见 §3.1） |
| HARDCODED_SECRET — `sk-` 词内碰撞 | 9 / 7 | **上游规则缺词边界**，普通英文词被当成 OpenAI key | **不能**（§3.2） |
| HARDCODED_SECRET — 历史文档里的公开标签 | 1 / 1 | `token:` 后跟一个公开标签串 | 能（改标点） |
| HARDCODED_SECRET — 课程投影里的占位 key | 1 / 1 | `data/lessons.json` 展开了一篇课程示例 | 不能（§3.3） |
| RISKY_APPROVAL_DEFAULT | 2 / 2 | 交接文档**引用**了沙箱模式名 | 能（拆词/改写） |
| py/bad-tag-filter（CodeQL） | 1 / 1 | TDZ 门禁的 `</script>` 不匹配 `</script >` | **能，且已修**（§4） |

条数比文件数多 2，是因为 GitHub 对同一 `(文件, 行)` 留了两条：**#288 ≡ #308**、**#289 ≡ #310**
（两次扫描各自开了一条，没人 dismiss，旧的就没关）。所以是 **22 条告警 / 19 个文件**。

**一句话**：19 条 HARDCODED_SECRET + 2 条 RISKY_APPROVAL 全部是误报，其中 9 条（7 个文件）是上游扫描器的
正则缺陷；唯一一条真缺陷是 CodeQL 的 `py/bad-tag-filter`，已在本轮修好并加了行为门禁。

## 1. 怎么把它们一次列出来

```bash
python3 - <<'PY'
import sys, json, urllib.request
sys.path.insert(0, "scripts")
from gh_push_via_api import resolve_token
tok = resolve_token()
req = urllib.request.Request(
    "https://api.github.com/repos/Ikalus1988/MisakaNet/code-scanning/alerts?state=open&per_page=100",
    headers={"Authorization": f"Bearer {tok}", "User-Agent": "mn", "Accept": "application/vnd.github+json"})
for a in json.load(urllib.request.urlopen(req)):
    i = a["most_recent_instance"]
    print(f'#{a["number"]:4d} {a["rule"]["id"]:24s} {i["location"]["path"]}:{i["location"]["start_line"]} '
          f'tool={a["tool"]["name"]}@{a["tool"].get("version")}')
PY
```

`most_recent_instance.message.text` 是根因的入口：CodeQL 那条写的是
*"This regular expression does not match script end tags like `</script >`."*——照它修就行了。

## 2. 扫描器是什么（以及为什么本仓的本地模型会漂）

`.github/workflows/guarded-repository.yml` 调 `hashgraph-online/hol-guard` 的可复用工作流（pin 在 v3.6.1），
它把 `codex_plugin_scanner` 装进 runner 扫**整个 checkout**，再把结果当 SARIF 上到 code scanning，
工具名 `plugin-scanner`（告警上显示版本 **2.2.0**）。

⚠️ **本地那份 `tests/test_scanner_secret_patterns.py` 复制的是 PyPI 上的 2.0.12，不是跑在 CI 上的 2.2.0。**
2.2.0 多出这些模式（抄自 hol-guard `src/codex_plugin_scanner/checks/security_secret_patterns.py`）：

```
github_pat_[A-Za-z0-9_]{20,}   xoxe-…   xoxr-…   xapp-…
sk-(?:proj-|ant-)?[A-Za-z0-9_-]{20,}      # ← 实际部署的版本没有词边界
```

**这就是「本地门禁全绿、GitHub 上 22 条红」的原因**：本地那份规则比线上的旧，而且只覆盖
workflows / workers / 插件清单 / `tests/`，线上那份扫全树。

## 3. 19 条 HARDCODED_SECRET（17 个文件）逐类

### 3.1 测试夹具与占位符（8 条，可修）

| 文件 | 命中的东西 |
|---|---|
| `tests/test_redaction_sync.py`、`tests/test_misaka_capture.py`、`tests/test_intake_redaction.py`、`tests/test_tombstone_redaction.py`、`tests/test_intake_spam_guard.py` | 喂给脱敏器的假 `ghp_…` / `AKIA…` / 私钥头 |
| `tests/fixtures/intake_spam_guard_corpus.json` | 同上，语料里的一条 |
| `packages/fatal-guard/tests/crash-scenarios.js`、`packages/fatal-guard/tests/redact-compliance.js` | 同上（JS 侧） |

这些文件的**主题就是脱敏**，夹具是重点不是事故。仓库侧的正规修法不是删夹具，而是**拼出字面量**
（`tests/test_scanner_secret_patterns.py` 自己的 `SAMPLES` 就是这么写的）：把
`"ghp_" + "ABC…"` 拆成两段，脱敏器拿到的字符串一模一样，扫描器 grep 到的原文不再命中。
改完要把这些文件从 `EXEMPT_FILES` 去掉——`test_every_exemption_is_still_earned` 会逼你这么做
（不再命中却还挂在豁免表里 = 一个开了口的洞）。

### 3.2 `sk-` 词内碰撞（9 条告警 / 7 个文件，**只能上游修**）

命中的不是 key，是**普通英文词里的 `sk-`**：`di`+`sk-full-…`、`ta`+`sk-claim-…`、`ri`+`sk-concurrency-…`。
上游 2.2.0 的正则 `sk-(?:proj-|ant-)?[A-Za-z0-9_-]{20,}` 没有 `(?<![A-Za-z0-9])`，于是任何
「……sk-后面还跟 20 个以上词字符」的 slug / prose 都算 OpenAI key。

**逐条对齐的证据**（告警报的行号 = 该文件里第一个 `sk-…{20,}` 的位置）：

```bash
python3 - <<'PY'   # 复算：把 7 条告警的文件跑一遍「无词边界」版 sk- 正则
import glob, re
pat = re.compile(r"sk-(?:proj-|ant-)?[A-Za-z0-9_-]{20,}")
files = (glob.glob("docs/lessons/disk-*/index.html")
         + glob.glob("docs/lessons/idempotent-task-*/index.html")
         + ["docs/sitemap.xml", "docs/.generated-pages.json",
            "docs/field-reports/2026-09-18-issue-1819-agent-ab-measurement.md"])
for f in files:
    text = open(f, encoding="utf-8", errors="ignore").read()
    m = pat.search(text)
    print(f, "->", text.count("\n", 0, m.start()) + 1, repr(m.group(0)) if m else None)
PY
```

（路径用 glob 写，是为了让**这份记录本身**不包含那个 `sk-` 连续串——否则本文会变成同规则的第 8 条告警。
上面 7 个文件的命中行号与告警一一对应：8 / 6 / 8 / 6 / 456 / 120 / 270。）

hol-guard 的源码里**已经有**词边界 `(?<![A-Za-z0-9])`（v3.6.1 的
`src/codex_plugin_scanner/checks/security_secret_patterns.py`）。**部署的那份没有**——这是推断，
依据是上面对齐的行号（有词边界时这 7 个文件一个都不命中）加上告警上写的 tool version `2.2.0`：那个
2.2.0 的 wheel 不在 PyPI 上（PyPI 上最新是 2.0.12，也就是本地那份门禁复制的版本），所以没法把它装下来
直接复现。结论仍然是「上游已修、尚未发布」：等 hol-guard 发了带这个词边界的版本、并 bump
`guarded-repository.yml` 的 pin，这 7 条会自己消失——届时**本地那份门禁也该换成新版本的模式表**，
把两个模型之间的漂移一起修掉。

这 7 条**不能**在仓库侧修：其中 4 个是 `lessons/*.md` 生成的公开页面（slug 就是 URL），
`sitemap.xml` / `.generated-pages.json` 是生成物，`docs/field-reports/…` 是历史记录。
为了让别的仓库不再踩，值得给 hol-guard 提一个 issue（现象 + 上面这段复算）。

### 3.3 课程投影里的占位 key（1 条，不能修）

`data/lessons.json:897` 是 `aider-api-key-leak` 那篇的 preview，里面有课程作者写的
`sk-ant-api03-` + 一串 `X` 占位符。源文件 `lessons/contrib/aider-api-key-leak.md` **没有**被告警——
因为它在 `docs/`/`lessons/` 这类「示例面」路径下被扫描器的 illustrative-context 规则放过了；
投影到 `data/lessons.json` 之后路径提示没了，同一段文字就命中。改课程正文才能消掉这条告警，
而那是拿内容去迁就别人的正则，不值。

### 3.4 历史文档里的公开标签（1 条，可修）

`docs/release/v2.16.0-release-notes.md:21` 命中的是 `token:` 后跟 **public read-only access** 这个
公开标签串——它是发布说明里的文案，不是凭据。把冒号改成破折号即可不再命中（同一段文字，同样的意思）。

## 4. CodeQL `py/bad-tag-filter`（1 条，真缺陷，已修）

`tests/test_site_script_ordering.py` 的 `INLINE_SCRIPT` 原本是 `…</script>`，**匹配不到 `</script >`**。
这不是 lint：`docs/**/*.html` 里只要出现一次带空格的闭合标签，正则就会一路吃到**下一个** `</script>`，
TDZ 规则分析的是两个脚本拼起来的假文件，正是它要抓的那类漏报。

修法：闭合标签写成 `</script[^>]*>`（同时覆盖 `</script >`、`</script\t\n bar>`、
`</script foo="bar">`）。注意**只加 `\s*` 不够**——CodeQL 的三条 `msg` 是并列的，`\s*` 只消掉
"`</script >`" 那条，会剩 "`</script foo=\"bar\">`" 那条继续报。已在本地按 CodeQL 查询
（`github/codeql` → `shared/regex/…/BadTagFilterQuery.qll`）的分支逐条验证三种写法。

门禁：`test_the_extractor_closes_on_a_tag_with_whitespace_or_attributes` 把严格版正则的行为
（两个脚本读成一个）与修好后的行为都钉住了。

## 5. RISKY_APPROVAL_DEFAULT（2 条，误报）

规则是 `RISKY_APPROVAL_PATTERNS` 三选一：DSH 的沙箱模式名 `danger-full-` + `access`；`approval_policy`
字段配带引号的 `never`；`approvalMode` 字段配带引号的 `bypass`（三处的完整字面量本文都不写，
理由见下）。命中的两处都是交接文档在**讨论**这条规则本身
（`handoff-2026-09-11.md` 里甚至已经记着「一词，误报」）。这条检查没有行号，GitHub 就记在 `:1`。

处置：把那个词拆开写（例如在中间插 Markdown 强调）即可不再命中——**本文也照此处理**，
否则这份记录自己就会变成同规则的第 3 条告警。

## 6. 待 owner 决定

1. **#3.2 / #3.3 的 10 条**：上游修好之前只能 dismiss（`won't fix` / `false positive`），
   或者等 hol-guard 发新版本后 bump `guarded-repository.yml` 的 pin 再看它们自己消失。
   （#288/#289 是其中两条的重复，一起关掉。）
2. **#3.4 / §5 的 3 条**：改文档措辞就能消，但要动发布说明和历史交接记录，属于编辑决定。
3. **#3.1 的 8 条**：仓库侧可以清，做法在 §3.1；本轮**没有**动它们，因为这需要把 5 个脱敏测试的夹具
   改成运行时拼接，风险与收益要 owner 先点头（改夹具容易，改坏脱敏断言不容易被发现）。
