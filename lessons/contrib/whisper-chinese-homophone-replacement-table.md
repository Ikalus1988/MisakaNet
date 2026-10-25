---
title: "Whisper picks the wrong Chinese homophone every time: fix it with a per-model replacement table, not a bigger model"
domain: "audio"
tags:
  - "whisper"
  - "asr"
  - "transcription"
  - "chinese"
  - "homophone"
  - "post-processing"
  - "replacement-table"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "whisper 转写中文专业内容时同音字会稳定选错，词表和更大的模型都修不好；只能在转写后按模型专属映射表做确定性替换。"
trigger: "whisper 中文同音字 错字 精讲变金奖 / initial_prompt 无效 / turbo 升 large 仍错 / 转写稿术语错误"
verify: "映射表替换后 grep 已知错误形式（金奖|公众师|公认师|梅老师|美老师|本日助安|本职助安|柱子安全|终极注册|串奖）返回 No matches found，同时正确形式命中。"
source: "intake-3267"
provenance:
  issue: "#3267"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# Whisper picks the wrong Chinese homophone every time: fix it with a per-model replacement table, not a bigger model

## Problem

whisper 转写中文专业内容时，同音字会**系统性**选错字，且 `initial_prompt`（领域词表）与换用更大模型（turbo→large）都修不好。实例：

| 正确 | 转写结果 |
|---|---|
| 精讲 | 金奖 |
| 串讲 | 串奖 |
| 工程师 | 公众师（turbo）/ 公认师（large） |
| 死记硬背 | 死尽背 |
| 艾宾浩斯 | 艾比英浩斯 |
| 命题人 | 密提人 |
| 承前启后 | 成前起后 |
| 米老师（人名） | 美老师（turbo）/ 梅老师（large） |

没有报错，转写正常返回。错误在语义层：术语被替换成同音 / 近音的常用字，读起来一样但意思完全错。

## Root Cause

不是模型规模问题，是**同音字上的先验偏置**。实测：同一段 6.6 分钟中文讲座音频做三方对照：

| 配置 | 错误词数 | 正确词数 |
|---|---|---|
| (a) turbo，无词表 | 21 | 1 |
| (b) turbo + `initial_prompt` 注入 111 个领域术语 | 13 | 2 |
| (c) large + 同一词表 | 13 | 4 |

(b)(c) 确有改善，但形态都是「错误形式消失、正确形式不出现」——只是换成了第三种错法。决定性证据：`讲→奖` 这个错在三个配置里完全一致（8 / 7 / 7 次），`large` 并未纠正它。

声学模型不为「专业术语的正确写法」负责：它在发音相同的一组字里按语言模型先验挑一个，规模变大只改变挑错的分布，不改变「必须挑对」这件事。

## Solution

转写后做**确定性替换**，不要指望声学模型：

1. 写一个映射表 JSON，每条 `{from, to, note}`；
2. 替换按「**先长后短**」排序——否则「金奖」会先于「金奖班」命中，破坏上下文；
3. 报告每条规则的实际命中次数（0 命中的规则要复核，可能是 `from` 写错了）；
4. **映射表必须针对你实际使用的模型建立**：同一个词 turbo 错成「公众师」、large 错成「公认师」，只按一个模型的错例建表会大面积静默漏改；
5. 流程上加一步「替换后用 grep 验证错误形式零残留」——漏改是静默的，不验就等于没改。

```json
[
  {"from": "金奖班", "to": "精讲班", "note": "longest-first"},
  {"from": "金奖", "to": "精讲"},
  {"from": "公众师", "to": "工程师", "note": "turbo"},
  {"from": "公认师", "to": "工程师", "note": "large"}
]
```

报料者未给出 whisper 的具体调用命令、模型文件与映射表全文，需复现确认。

## Verification

对 large 转写稿应用 21 条映射规则，替换 19 处；随后搜索全部已知错误形式：

```
grep -nE "金奖|公众师|公认师|梅老师|美老师|本日助安|本职助安|柱子安全|终极注册|串奖" transcript.md
# No matches found
```

同时正确形式（精讲|工程师|米老师|中级注册安全|本智助安|串讲）命中 16 行。

注意验证步骤本身会抓出映射表缺陷：首轮只按 turbo 错例建表时，这次 grep 验出 5 处漏改（裸「金奖」4 处，large 特有的「公认师」「本日助安」各 1 处）。所以要先跑一遍 grep 再宣告完成，而不是替换完就交付。
