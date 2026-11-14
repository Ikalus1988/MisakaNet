# Handoff — 2026-11-14 第 37 卷（承接 `handoff-2026-11-14-part2.md` 第 36 卷）

> 这一卷是「仓库清扫」：把审计出的过期面按第一性原理逐项判生死，交给 11 个 PR。
> 真正值得带走的不是删了什么，而是**四次差点删错、四次被门禁或复核拦下**的判据。

## 1. 这一轮定下来的判据

1. **「没有引用」要按调用方式查，不能按文件名查。** 四种漏法都在本轮出现过：
   目录 glob（`tests/intake_receipt_cases/*.json` 由 `CASES_DIR.glob("*.json")` 加载）、
   脚手架（`agents/` 是给第三方 agent 抄的模板）、文档里的格式范本（`tasks/reuse/` 被
   `docs/benchmark-challenge.md:47` 当提交格式）、行号引用（`docs/blog` 用
   `release/v2.16.0-release-notes.md:13` 当证据）。
   **另一半是同一种病的另一种形状：`head -N` 截断输出。** 我扫 `misaka-protocol.json` 的消费者时
   `git grep … | head -8` 把结果截断，只看到 pr-shape-guard/API.md/CHANGELOG/archive，判成"无主"——
   而它有三个活消费者（MCP 资源 + worker 构建期 import）。**引用扫描不要 `head`。**
2. **保留一个文件的门槛 = 说得出消费者是谁。** `archive/README.md` 现在按这条写；说不出来就该走
   git 历史，而不是留在工作树里。
3. **「发布面」必须打线上验证。** 仓库里有 `smithery.yaml` / `vscode-extension/package.json`
   不代表列表还在：Smithery 服务页与 VS Code 市场都返回 **404**。反过来，看着像退役契约的
   `misaka-protocol.json` 有三个活消费者。**文件存在性与服务存在性是两件事。**
4. **删一个 workflow 会同时动摇三类计数。** `docs/CI.md` 的 `## 数据/索引（N）`、`ARCHITECTURE.md`
   的**三处**（正文 / mermaid 图 / 结尾段）、以及库存门禁的 replay fixture。本轮第一次只改了两处，
   `test_workflow_inventory.py` 直接报 `states [92] workflow(s); the directory holds 91`。
5. **坏掉的功能留下的是「承诺」，不是数据。** `badcase/` 与 `confidence-judgment/` 从 2026-08-27
   起没有任何新数据落盘（CI 只有 `issues: write`，没有 `contents: write`、没有 commit），却每天在
   issue 里评论「📁 Archived to: `badcase/<n>`」。删掉的是这句话——不是待归档的证据，那句话本身
   就是唯一的产物。

6. **一份「显式豁免清单」会把「看着像死文件」变成「已作决定」。** `.github/actions/classify-failure/` 没有任何 workflow 调用，它的消费者 `ci-self-heal.yml` 早在 #1984 就当孤儿删了——我据此删了它并**撤回**：`tests/test_workflow_inventory.py` 的 `UNWIRED_ACTIONS` 里写着「kept as a tested library; no workflow calls it yet」，而且门禁断言这条理由非空。**删之前先搜它是否已在某张豁免表里；在表里就说明有人想过，要删得先推翻那条理由。**

## 2. 数字（截至 #4863 合并）

| 项 | 值 |
|---|---|
| 合并 PR | 11（#4830–#4867，其中 #4867 合并中） |
| 净变化 | 149 files changed，+248 / **−9044** |
| 离开仓库的跟踪文件 | **128** |
| 本地释放 | ~1.0 GB（gcloud SDK 448 MB + `__pycache__` 48 MB + `mcp-publisher.exe` 20 MB + 构建残留） |
| workflow 数 | 92 → **91**，`ARCHITECTURE.md` 三处与 `docs/CI.md` 节标题同步 |
| 新增门禁 | `tests/test_config_example_is_honest.py`、`embed_workers_ai` 的 4 条 token 测试 |

## 3. 悬着的账

| 谁 | 项 | 下一步 |
|---|---|---|
| 仓库 | **#4867** bench 假结果 + pr-genius 孤儿链接 | CI 中，armed；合并即收口 |
| 仓库 | `docs/reviews/`（14 个）+ `docs/roadmap/90-day-strategy-2026-07.md` 判 ARCHIVE 但未执行 | 牵动 `tests/test_doc_line_citations.py` 的 `ARCHIVE_PREFIXES`（`docs/reviews/` 是豁免前缀，搬走就不再豁免）——单独一轮，先读门禁再动 |
| 仓库 | `docs/onboarding/agent-intake.md` 与 `docs/agents/retrieval-and-contribution.md` 内容重复 | 是**合并**不是删除（前者 2026-10-15 才写），需要一次编辑 |
| 仓库 | `docs/mcp-protocol.md`、`docs/agent-benchmark.md` 无入链 | 是**链接缺口**不是过期：补链接或合并，见 §1.1 |
| 本地 | **4 个 worktree 里有真东西**（2026-11-14 逐个体检）：`/tmp/wt-crash` 改 `scripts/compare_site_pixels.py` + 新文件 `tests/test_pixel_scoped_gate.py`；`/tmp/wt-main` 改 `check_page_scripts.py` 与它的测试 + 新文件 `docs/_partials/site-helpers.js`；`/tmp/wt-guard` 改 design-convergence 与两份 handoff（并删了 part3）；`/home/eric_jia/wt/les` 是 398 文件 / ±92300 行的整体改写。其余 `/tmp` worktree 无跟踪改动 | 这四个需要 owner 认领或丢弃；**删之前先 `git -C <wt> diff > /tmp/<wt>.patch`**（都没提交）。另：`feat/pr-shape-guard-internal-artifact` **未并入 main**，是那些提交唯一的引用 |
| owner | 工作区里两个未跟踪文件：`lessons/contrib/rag-chunk-coarse-cover-page-pollution.md`（完整课程草稿）、`salvage-worksheet-2026-11-04.md`（44 条 intake 的工作单） | 课程草稿走 `lesson_gate` 提 PR；工作单已被每日 `intake-salvage-digest.yml` 取代，可删 |

## 4. 下一轮入口

```bash
# 1) 收口本轮
gh pr view 4867 --json state,mergeStateStatus

# 2) 复核清扫没有回退（删掉的东西不该长回来）
ls .github/workflows/*.yml | wc -l                              # 期望 91
git ls-files | grep -cE '^(badcase|confidence-judgment)/'        # 期望 0
grep -c 'Guides & articles (58)' docs/llms-full.txt              # 期望 1

# 3) 继续未做的那批（先读豁免规则，别先搬家）
grep -n 'ARCHIVE_PREFIXES' tests/test_doc_line_citations.py
```

## 5. 坑（本轮新踩）

- **`git add -A` 会把用户未跟踪的文件卷进提交**：本轮踩了一次（课程草稿 + 工作单被一起提交），
  已 `reset --soft` 回滚重提。提交前先看 `git status --short` 的 `??` 行。
- **`gh api -f environment_ids[]=<int>` 发的是字符串**：部署审批会回 422
  `For 'items', "…" is not an integer`，要用 `--input -` 发原始 JSON。
- **WSL 沙箱里 wrangler 写不了 `~/.config`**：`XDG_CONFIG_HOME` 指到仓内 gitignored 目录，
  复制一份 `default.toml` 即可；用完删掉那份 OAuth 副本。
- **删文件之前先搜 `path:line` 形态的引用**：博客按行号引用 release notes、`data/query-aliases.json`
  引用 README 的表格行。门禁（`test_query_aliases`、`test_doc_line_citations`）抓得到，但会晚一步，
  而且修起来比"删之前看一眼"贵。
- **本机 worker 全量测试固定 5 条红**：`UNDICI-EHPA` 代理警告污染了"stderr 必须为空"的断言，
  加一个残留 `update-check.json`。四个都在 `workers/agent-autostart-hook.test.mjs`，与改动无关。
- **批量回填结构化字段之前，先量「源内容是不是判据」。** 想把 359 篇缺 `verify:` 的课程里的 `## Verification` 段搬进字段：334 篇确有这样一段，但格式规整（单命令+单行输出）的只有 **14 篇**，且一半是 `echo 'Verification passed'` 这类占位——照搬会把占位符升级成结构化字段，比空着更糟。**源内容存在 ≠ 源内容是判据。**
- **本机 git 协议会整段断**（`gnutls_handshake failed`，连 api.github.com 也 SSL_ERROR_SYSCALL）。
  断的时候 `gh` 与 `git push` 一起失败；恢复后一次推三支正常——**是本地网络，不是 GitHub**。
