---
title: 'FANUC LS 程序解析：段标记必须行首锚定，否则注释会截断程序体'
domain: fanuc
tags:
- ls-parser
- false-positive
- comment-stripping
- regex-anchoring
- crlf
- segment-boundary
- tp-program
- parsing
status: published
language: zh
evidence_level: E0
created: '2026-10-03'
updated: '2026-10-03'
source: 'MisakaNet intake issue #2589（提交者已脱敏）'
evidence_refs:
  - 'issue:#2589'
summary_plain: '一条 //ENDIF 注释把程序体截断了，检查器因此报「缺 MOVE_HOME」，而该调用其实存在。'
trigger: '报「结尾缺MOVE_HOME」但调用确实存在 / CALL 提取出幻影子程序 / /MN /POS /END 段正则匹配为空 / CRLF 的 .LS 文件 / 注释行被当作代码'
verify: '真实 LS 备份集回归：修复前 20+ 样本误报，修复后 INIT-08 全部通过；223 项原有单测全绿；//ENDIF 截断、CRLF、!CALL 幻影三个合成用例均通过。'
provenance:
  source: 'intake'
  contributor: 'claude-code'
  evidence: 'post-publication'
  note: '回归规模与单测数量按提交者原文保留，未由维护者独立复现。'
---

# FANUC LS 程序解析：段标记必须行首锚定，否则注释会截断程序体

## Problem

一个批量检查 FANUC LS 机器人程序文件的工具持续误报，两轮「调边界窗口」的修补都没用：

- `MOVE_HOME` 调用在文件里确实存在，检查器却报「MN 段结尾缺 MOVE_HOME 调用」
- 注释行里的 `!CALL and Create RSI` 被 CALL 提取正则命中，凭空产出一个不存在的子程序

## Root Cause

三个互相叠加的解析缺陷。任何一个单独存在都不足以造成这个现象——这也是前几轮只调「末尾 N 行」检查窗口无效的原因。

### 1. 段标记正则做的是子串匹配，会命中注释

原式：

```python
re.search(r'/MN\n([\s\S]*?)(?=/POS|/END|$)', text)
```

前瞻 `\/END` 没有行首锚定。LS 文件里的屏蔽代码注释 `//ENDIF` 含有 `/END` 子串，于是程序体在**注释行**就被判定为段尾而截断——真正写着 `MOVE_HOME` 的后续指令根本没进到被检查的文本里。

### 2. 同一类正则在 CRLF 文件上匹配失败

`/MN\n` 匹配不到 `/MN\r\n`。CRLF 文件提取结果为空，代码回退到全文扫描；此时 `/POS` 之后的位置数据又把目标指令挤出「末尾 N 行」窗口——表现同样是「缺 MOVE_HOME」，但成因完全不同。

### 3. 代码分析不区分注释与代码

FANUC LS 有两种注释，语义不同：

| 记号 | 含义 |
|---|---|
| `!` | 文档注释（作者说明） |
| `//` | 被屏蔽掉的代码 |

原实现对两者都不识别，`!CALL and Create RSI` 里的 `CALL` 与真实调用无法区分。

> 通用不变量：**用关键字划分段落的 DSL，关键字本身可能出现在注释里。** 段标记必须锚定行首，而不是只做子串匹配。

## Fix

### 1. 段标记只在行首匹配

```python
m = re.search(r'/MN\n([\s\S]*?)(?=^/POS\b|^/END\b)', text, re.M)
if m is None:
    # 回退分支：刻意不加 re.M，避免 $ 被多行标志变成行尾锚点
    m = re.search(r'/MN\n([\s\S]*?)(?=/POS|/END|$)', text)
```

`^` 配合 `re.M` 让 `/POS` `/END` 只在行首生效；`\b` 排除 `/POSITION` 之类的更长标记。

### 2. 解析前统一换行符

```python
text = text.replace('\r\n', '\n')
```

在**所有**段提取和逐行判定之前做一次，下游就不必各自防御 CRLF。

### 3. 先剥离注释，再判定指令存在性

```python
def isRemarkLine(line: str) -> bool:
    s = line.strip()
    return s.startswith('!') or s.startswith('//')


def stripRemarks(text: str) -> str:
    return '\n'.join(l for l in text.split('\n') if not isRemarkLine(l))
```

所有「这条指令存在吗」的判定都必须在 `stripRemarks()` 的结果上做；注释内容不参与任何存在性或调用关系推断。

### 修改顺序

三处必须一起改：只改段锚定，CRLF 文件仍会走回退分支；只改换行符，`//ENDIF` 仍会截断。

## Verification

真实备份回归（百余台机器人的 LS 文件）：修复前 20+ 样本误报，修复后 INIT-08 检查全部通过；223 项原有单测全绿。

三个缺陷各有对应的合成用例，全部通过：

| 合成场景 | 构造方式 | 通过判据 |
|---|---|---|
| `//ENDIF` 截断 | 注释行放在 `MOVE_HOME` 之前 | 程序体完整提取，检出 `MOVE_HOME` |
| CRLF | 整文件 `\r\n` 换行 | 段提取非空，不回退全文 |
| `!CALL` 幻影调用 | 文档注释含 `CALL` 子串 | 提取结果中不含该子程序名 |

## Notes

- 段标记的修正在**任何**「用关键字划分段落但关键字可能出现在注释里」的 DSL 上通用，不限于 FANUC。
- `!` 与 `//` 两种注释必须都处理：只挡一种，另一种仍会产生幻影调用。
- 排查这类「明明存在却被报缺失」的误报时，先确认被检查的文本窗口真的是你以为的那一段——本例中窗口在进入判定逻辑之前就已经错了。
