---
title: "A navigation layout change leaves other UI automation scripts on the old selector"
domain: "testing"
tags:
  - "ui-testing"
  - "selectors"
  - "contract-test"
  - "playwright"
  - "release-gate"
  - "frontend"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "改导航布局只更新了一个 UI 脚本的选择器，其余脚本还在找旧类名，发版门禁红在一个无关脚本上。"
trigger: "locator.click: waiting for locator('.ant-menu-item')"
verify: "把 App 改回旧控件或在任一脚本里留旧类名，新契约单测立刻红并点名文件与期望值；真机发版门禁 13 层全绿。"
source: "intake-3584"
provenance:
  issue: "#3584"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

## Problem

改前端导航/布局——把左侧 `Menu` 换成顶部 `Tabs`——时，只改了**一个** UI 自动化脚本的选择器，其余几个还在找旧的 CSS 类名（如 `.ant-menu-item`）。

结果发版门禁当场红在**一个与本次改动无关的脚本**上（`playwright-ui-smoke`）：

```
locator.click: waiting for locator('.ant-menu-item')
```

超时。而你改的那个脚本是绿的——这一点最误导人：它读起来像"改动已经收干净了，红的是别人的问题"。

同一个项目里，这已经是当天第二次"改一处、没横扫同族入口"：上午刚因为只修了一个页面的文件上传回调，漏掉另外两个页面。

## Root Cause

**App 的 UI 契约和测试的选择器，是两处独立书写的字符串，没有任何机器校验它们一致。**

- 旧的契约测试只查"命令名 / 参数名 / 结果字段"这类**后端**契约；
- "导航控件到底是什么、自动化该用哪个类名"这种**前端布局**契约，从来没有测试覆盖；
- 于是布局一改，测试里的选择器就成了**悬空引用**：它不会在你改的那一处报错，而是等跑到某个用到导航的脚本时才炸，且炸的位置和你改的地方看起来毫无关系。

补上这一层要付的代价，比"下次记得全仓改一遍"低得多——因为"记得"不是机制，下午就会忘第二次（报料者在同一天已经忘了一次）。

## Solution

不要只做"全仓 grep + 逐个替换"——那下次还会漏，而且漏的方式一模一样。补一条**双向**契约测试：

1. 从 App 源码推断功能入口**实际渲染**的是哪个控件（`Tabs` 还是 `Menu`）；
2. 遍历所有会点导航的 UI 自动化脚本，断言它们用的 CSS 选择器**与 App 的推断结果一致**；
3. 任一侧不匹配就红，并在失败信息里点名**是哪个脚本**、**期望什么**。

形态示意（报料者给出了断言方向，未给出实现代码，路径与类名为占位）：

```python
import re
from pathlib import Path

app_src = Path("<app-source>/<nav-component>").read_text(encoding="utf-8")
rendered = "tabs" if "<Tabs" in app_src else "menu"
expected = {"tabs": ".ant-tabs-tab", "menu": ".ant-menu-item"}[rendered]

for spec in Path("tests/ui").glob("*.spec.ts"):
    used = set(re.findall(r"\.ant-(?:menu-item|tabs-tab)\b", spec.read_text(encoding="utf-8")))
    stale = used - {expected}
    assert not stale, f"{spec}: 旧选择器 {sorted(stale)}，但 App 现在渲染 {rendered}（期望 {expected}）"
```

关键在于第 1 步是**从 App 源码推断**，不是从另一个常量读——两边都从同一个"事实源"长出来，才不会出现"两份各自维护的字符串"。

配套（同一次事故里的另一半教训）：把"显示成功但没产物"这类判据也写进脚本——**断言产物真的落地**（磁盘上有文件 / 数量对得上），不要只断言弹了成功提示。

## Verification

- **契约测试本身可证伪**：把 App 改回 `Menu`，或在**任一**脚本里故意留旧类名 → 单测立刻红，错误信息点名文件与期望值。两边任一改动都会红在单元测试里，而不是等发版门禁。
- **真机发版门禁**：13 层全绿（含 UI 冒烟 / 单台 QA / 批量分组 / 产物实测）——报料者给出的通过判据。
- **产物判据**：导出后**磁盘文件数 == 声称的条数**，不是只看成功 toast。

## Notes

- 这类失败的共同形态是"**同一契约被独立书写两次**"：App 一份、测试一份，中间没有机器校验。凡是这种结构，修一次就会漏下一次，正确的修法是加一条交叉校验，而不是把 checklist 记得更牢。
- 失败为"超时"而非"找不到元素"时尤其要警惕：超时是"选择器一直等不到"，说明这个选择器在当前 DOM 里根本不存在，比 `strict mode violation` 之类的错更接近"契约变了"。
