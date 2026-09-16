# 课程结构化字段：`summary_plain` / `trigger` / `verify`（#1783）

> 面向维护者。三个字段**都是可选的**，但**新增**课程必须写齐——门禁对新增严格、对存量劝告
> （#1506 的分档）。存量回填**不是必须**，也不允许阻塞任何 PR。
>
> 它们**永远不替代** `Problem` / `Root Cause` / `Solution` / `Verification`：
> 正文仍然是课程本体，这两个字段只是让课程**被搜到**（`trigger`）、让结论**能被外行读懂**
> （`summary_plain`）、让"修好了没有"**可判定**（`verify`）。不要为了填字段而把正文删短。

## 1. 字段定义

| 字段 | 是什么 | 限制 | 谁在用 |
|---|---|---|---|
| `summary_plain` | 给**不懂技术的人**看的一句话大白话：出了什么事、为什么 | ≤ 120 字符 | 模型命中后原样转述给用户 |
| `trigger` | 触发条件：**短、含可匹配片段**的错误文本/关键词（不是整句提问） | ≤ 160 字符，单行 | 检索索引（`misakanet_search`） |
| `verify` | 可判定的通过/失败判据（能跑、能看、修没修好结果不同） | ≤ 200 字符 | 读者自查、reviewer 判断"是否实测" |

写进 frontmatter（YAML 或老的 JSON 都行）：

```yaml
summary_plain: "公司网络里装不上 Python 包，是因为下载源要先换成公司内部的镜像。"
trigger: "pip install timeout behind proxy"
verify: "pip install -v httpie 退出码为 0"
```

正例/反例（`lessons/TEMPLATE.md` 里也有同一份）：

| 字段 | ✅ 正例 | ❌ 反例 | 反例为什么没用 |
|---|---|---|---|
| `summary_plain` | `公司网络里装不上 Python 包，是因为下载源要先换成公司内部的镜像。` | `pip 的 index-url 配置异常导致的解析超时问题。` | 只是把标题换个说法，术语照旧，外行读完仍然不知道发生了什么 |
| `trigger` | `pip install timeout behind proxy` | `我的构建为什么一直失败，应该怎么解决？` | 整句自然语言，索引里没有任何文档含这串词，命中 0 |
| `verify` | `pip install -v httpie 退出码为 0` | `注意编码问题` | **不可判定**：没有可执行/可观察的判据，也永远不会失败——它验证不了任何东西 |

## 2. 为什么 `trigger` 能提升检索

语料是**按错误原文和关键词**建索引的（D1/BM25 词项 + 标题/正文片段），不是自然语言问答库。
所以：

- 整句中文提问（"我的构建为什么一直失败"）→ 词项几乎全都不是索引里的高频判别词 → **命中 0**，
  然后走 `no_match` + intake 兜底。这是长期存在的已知问题；
- 错误原文里最独特的片段（`pip install timeout behind proxy`、`context window exceeded`）→
  判别词密度高 → 能精确落到那一篇课程。

`trigger` 就是把"该怎么问"**从用户身上挪到提交者身上**：提交者最清楚这篇课对应的是哪段错误文本，
把它写成短、可匹配、无歧义的字段，检索就有了一条稳定的入口。同类先例是
`data/regression_queries.json` 的 11 条回归查询夹具——那里的查询串就是同样的"短片段"形态。

`verify` 解决的是另一个方向的浪费：正文里的验证段常常是叙述（"确认一下没问题"），
reviewer 和读者都无法判断它是否算数；一条可判定的判据（命令 + 预期结果）让"是否实测"变成事实问题。

## 3. 读取侧：模型能拿到什么

| 调用 | 拿到的字段 |
|---|---|
| `misakanet_search(detail=compact)`（默认） | `summary_plain`（有则带上）——默认档就能原样转述 |
| `misakanet_search(detail=summary)` | 三个都有（有则带上） |
| `misakanet_search(detail=full)` | 三个都有（语料行带就带上） |
| `misakanet_get_lesson` | 三个都有（有则带上）——直接从返回正文的 frontmatter 解析，**不依赖任何数据管道** |

**等形性保证**：没有这三个字段的老课程，响应与改动前**逐字节相同**（不新增 null、不新增空串、
不重排键）。这条由 worker 测试守着（`workers/d1-lesson-service.test.mjs` 里的
"keeps the exact legacy shape" 用例，逐键、逐字节断言）。

规则块（`PROMPT_BLOCK` 与 `integrations/agent-autostart/prompt.md`）要求：命中后用
`summary_plain` 原样说给用户听；没有该字段时自己提炼一句大白话。

**已知缺口（本 issue 范围外，一行改动可补）**：`misakanet_search` 投影读的是语料行的字段，
D1 侧已从 `lessons.frontmatter`（schema 已有列、sync 已写入）解析；
GitHub/KV 兜底路径读的是 `data/lessons.json`，该文件目前还没有这三个键
（生成器 `scripts/update_lessons_json.py` 显式挑选字段）。所以**检索侧要完全生效**，
还需要把这三个字段加进索引生成器；`misakanet_get_lesson` 不受影响，今天就能用。

另外：`trigger` 目前**只出现在响应里**，还没有进入 BM25 的正文索引文本
（`lessonIndexText()` 的字段表）——它的定位是"查询侧片段"（同类先例是
`data/regression_queries.json` 那些查询串），命中后由模型直接复用它再查。
把 `trigger` 也并入索引文本是后续可选项，不属于本 issue。

## 4. 存量回填：可选，且**不得阻塞任何事**

回填**不是必须的**，没有 CI 任务要求存量课程补齐；只有**新增**课程会被硬门禁拦下。
回填 PR 只改 frontmatter、不重写正文，这样 review 成本最低，也避免顺手引入内容回归。

### 4.1 用门禁找出还缺字段的课程（只读）

`--existing` 就是"存量劝告"档：缺字段只出 `[warn]`，**永远不会让命令失败**，因此可以放心
在 CI 之外随便跑。

> 分档靠 git：门禁会问 git"这个路径在基线分支（`origin/main`）上已经有了吗"——CI 用
> `git diff --diff-filter=A` 回答的正是同一个问题。在没有 `.git` 的目录里（比如解压出来的源码包）
> 它会退化成"一律按新增处理"，此时请显式加 `--existing`。

```bash
# 只看本次改动过的课程（推荐的日常用法）
FILES=$(git diff --name-only origin/main -- 'lessons/**/*.md')
python3 scripts/lesson_gate.py --existing $FILES

# 只列出"还缺结构化字段"的文件名（喂给回填脚本或分批处理）
python3 scripts/lesson_gate.py --existing --json $FILES \
  | python3 -c "import json,sys; d=json.load(sys.stdin); \
      [print(f) for f, issues in d['files'].items() \
       if any('structured field' in i for i in issues)]"
```

### 4.2 补字段

按 `lessons/TEMPLATE.md` 的说明，给这些课程的 frontmatter 补上 `summary_plain` / `trigger` /
`verify`（一次一批，小 PR 更好审）。写完用同一条命令复查——警告消失即为补齐：

```bash
python3 scripts/lesson_gate.py --existing $FILES   # 期望：不再有 structured field 警告
```

### 4.3 三条纪律

1. **回填 PR 不阻塞其他 PR**：任何"等存量补齐再合并"的要求都不成立；
2. **回填只动 frontmatter**：正文、（尤其是 `Verification`）保持原样，除非你确实重新验证过；
3. **`trigger` 抄错误原文的片段，不要发明新词**：写不出来的就留空（存量课程允许缺），
  为了凑字段编一个没人会搜的 trigger 反而会污染索引。

## 5. 相关

- 模板与正反例：`lessons/TEMPLATE.md`
- 门禁实现与分档：`scripts/lesson_gate.py`（`structured_field_tier` / `validate_structured_fields`）
- 门禁测试：`tests/test_lesson_gate_fields.py`
- 检索投影与等形性测试：`workers/register-proxy-sw.js`、`workers/d1-lesson-service.test.mjs`
- issue：#1783（拆分自 #1767 的 B2/A4）
