# Handoff — 2026-11-22（vol 44，同一天第二卷）

> 承接 `handoff-2026-11-22.md`（vol 43）。这一卷只写**判断、实测数字、悬账与下一轮入口**（`handoff-rules.md` §5）。
>
> 主线：vol 43 把队列读对了（183 条、可转 0~7）。这一卷去问"那 0 里面还剩什么能动的"，
> 顺带发现一个**跑了三天、每次都失败、每次都绿**的自动化。

---

## 1. 判断

### 1.1 「可转 0」不是队列空了，是剩下三类人

175 条 open intake（`[Intake]` 且非 `decision`）的形状：

| 格 | 条数 | 谁卡住 |
|---|---|---|
| 缺 `Problem`/`Root Cause`/`Fix` | 142 | 提交者 |
| 公共面被拦（未登记的命令名） | 27 | owner 的计数决定（vol 43 §1.4） |
| 无标签 | 3 | 维护者给词就能转 |
| 已被课程引用 | 2 | —— 等回执关单 |
| 内容 weight < 400 | 1 | 提交者（不是语言问题，见 §3） |

**判据**：批次读数的价值在"每一格归谁"，不在总数。把 `convertible 0` 读成"没事可做"，
就会漏掉那 3 条**今天就能转**的——而它们被挡住的原因是可复现的缺陷，不是写作质量：
`tags_of` 的两条回退（正文里的工具名、标题里的词）都假设 Latin 标识符，中文散文同时踩空两条
→ 0 标签 → 整条被拒。这是同一族的第三次（前两次：`## Fix (if known)` 别名、"一个标签就够"）。

**给这三个的标签不是自动标注**：转换器早就留了 override 通道（`domain`/`title`/`tags`，
注释里写明"这是关于一条 issue 的人的决定"）。走它，不要改提交者的句子。

### 1.2 加课会把两个"总数"弄红，其中一个藏在测试里

显式的那个是语料条数与生成的页面；**藏着的那个**是 `docs/trust-semantics.md` 里那张 E0–E4
分布表——它是手抄的生成物，`tests/test_evidence_distribution.py` 会拿 `scripts/evidence_distribution.py
--check` 对着它跑。三篇 E1 课把 E1 从 630 推到 633，表不动就红。

**判据**：改完课程、跑全量测试之前，先跑 `scripts/evidence_distribution.py` 看那张表。

全量测试（1183 个用例）里**只有这一个**失败是本次改动造成的；另外 10 个在干净的 main 克隆上
同样红（代理环境变量、bash voice hook、`gh` 输出的引号转义、intake kind 判定）。
**判据**：本机这套测试不是全绿基线，改动前在 main 的干净克隆上跑同一批文件做基线比对，
否则会把自己的改动和环境的红混在一起。

### 1.3 一个自动化的自我报告若不能区分「平常的一天」和「它没工作」，它就不是报告

`update-lessons.yml` 的 "Emit intake receipts" 步骤，实测 100% 失败，而每次运行都是绿的：

| 运行 | 日期 | 输出 |
|---|---|---|
| 44599408593 | 11-19 | `⚠️ 259 intake receipt(s) undelivered` |
| 44865971717 | 11-21 | `⚠️ 290 intake receipt(s) undelivered` |
| 44972657740 | 11-22 01:42 | `⚠️ 302 intake receipt(s) undelivered` |
| 44981609437 | 11-22 03:39 | `##[warning] 303 receipt(s) could not be posted` |
| 44998816751 | 11-22 07:34 | `##[warning] 313 receipt(s) could not be posted` |

条数每次只涨"这批新课的条数"——**不是**积压，是从第一条起就没发出去过。而
`_post_issue_comment` 把 gh 的 stderr 丢掉了，所以 313 次一模一样的失败，一个字的原因也没有。

**判据**：区分形状，而不是加音量。全失败 ≠ 欠一条回执：前者是凭证坏了，后者是平常的一天。
旧代码两者都打 `::warning`，于是三天全绿。

**为什么不是让它变红**：这步跑在再生步骤之前，红了会冻住整条日更流水线——为一条欠账冻流水线，
比漏报更糟（这也是当初写 `::warning` 的原因）。正解是**级别 + 内容**：全失败 `::error` +
第一条 stderr，部分失败仍是 `::warning`，退出码都保持 0。

### 1.4 收据队列的口径是「日志行数」，不是 issue 状态

668 条课程引用了 issue，回执日志里只有 347 个唯一 key → 318 条"无回执"。这里**很多 issue 早已
被别的机制关掉**（intake 清扫、triage）。所以这个数不是"318 个还开着的 intake 在等"，
别拿它当 issue 队列读数。

---

## 2. 实测数字（2026-11-22 第二卷收工，判据同列）

| 项 | 值 | 判据 |
|---|---|---|
| 语料 | **1121**（+3） | `data/lessons.json` 条数 |
| open intake | 461 | `--label mcp-intake --state open` |
| 批次扫描 / 可转 | **175 / 0** | `convert_intake_batch.py`（页大小 1000） |
| 回执：引用 / 已记 / 无回执 | 668 / 347 / **318** | `emit_intake_receipt.py --check` |
| open issue | 594 | `gh issue list --state open --limit 2000` |
| open bounty | 80 | `--label bounty` |
| `needs-ac` | 47 | `--label needs-ac` |

---

## 3. 悬着的账（按「谁卡住了」分组）

- **只有 owner 能定**：
  - 公共面**计数**改不改（vol 43 §1.4，27 条卡在那）；
  - 47 条 `needs-ac` 的"done 长什么样"；
  - `#3828` 这种"段落齐全但太短"的收不收：231 字符的中文渲染后 weight 351 < 400。
    `content_weight()` 已经给 CJK 双倍，所以**不是**语言歧视——它真的只有一段。要收就得让
    提交者补一句验证，而不是改地板。
- **等一次真跑**：`update-lessons.yml` 每天 `00:00Z` 跑；下一轮第一次运行才证明收据失败是
  凭证还是别的——看注释里的第一条 stderr。318 条一次发出去可能撞二级限流，撞了就是
  `::warning` + 剩下的留到下次（未发的**不记账**，所以天然幂等）。
- **等提交者**：142 条缺段落（形态见 vol 43 §3）。
- **无我方未合 PR**。

---

## 4. 下一轮入口（可直接粘）

```bash
# 0) 对时
git fetch -q origin main && git log --oneline -3 origin/main

# 1) 队列五格（Windows 下必须带 UTF-8 三件套，否则假报 scanned 0，见 §5）
GITHUB_TOKEN= PYTHONUTF8=1 PYTHONIOENCODING=utf-8 python scripts/convert_intake_batch.py

# 2) 收据：引用 / 已记 / 无回执，以及第一条失败原因（--log 指向临时文件，别写仓库那份）
GITHUB_TOKEN= PYTHONUTF8=1 PYTHONIOENCODING=utf-8 python scripts/emit_intake_receipt.py --check 2>&1 | head -3

# 3) 那 3 条只差标签的，override 通道（改完走正常 PR，不是批量脚本）
#    .local/intake/overrides.json: {"<number>": {"domain": "...", "tags": [...], "title": "..."}}
GITHUB_TOKEN= PYTHONUTF8=1 PYTHONIOENCODING=utf-8 python scripts/intake_lesson_to_file.py \
  --issues-json .local/intake/issues.json --overrides .local/intake/overrides.json

# 4) 改过课程之后：先 git add，再在 WSL 里按顺序生成，最后在 ext4 clone 里自查
git add -A lessons/
wsl -e bash -lc 'cd /mnt/d/MD/misakanet/MisakaNet && for s in update_lessons_json build_lesson_pages \
sync_lesson_count export_okf rebuild_lessons_index export_public_vocabulary gen_ranking_snapshot; do \
python3 scripts/$s.py || break; done && python3 scripts/evidence_distribution.py'
```

---

## 5. 坑（本卷实际踩到的）

1. **Windows 控制台下这些脚本会假报「队列是空的」**：子进程输出解码走 GBK，`gh` 回来的中文
   一碰就 `UnicodeDecodeError`，脚本把 0 条当成结果打印。三件套：`PYTHONUTF8=1`
   `PYTHONIOENCODING=utf-8`，再加 `sys.stdout.reconfigure`。这一条比它听起来贵：它把"工具坏了"
   伪装成"没有工作"。
2. **`--depth 1` 的克隆不能更新同分支**（`rejected … shallow roots are not allowed to be updated`）：
   自查要么新克隆，要么就别用浅克隆。
3. **自查的正确顺序**：WSL 里跑七个生成器 → 在 **ext4** 的干净 clone 里 `git status --porcelain`
   必须为空 → `check_dist_diff.py main-side`。在 `/mnt/d` 上跑 `git status` 会有几千条 CRLF 假阳性
   （Windows 工作区 `core.autocrlf=true`，WSL 的 git 是 false）。
4. **`docs/trust-semantics.md` 不在生成器链里**：它是手抄的生成物，漏抄只由测试抓（§1.2）。
5. **`git commit -s`**：DCO 是必需检查，漏签要等 CI 红一次才知道。
