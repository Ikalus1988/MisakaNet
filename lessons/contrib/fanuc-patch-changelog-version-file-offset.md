---
title: "FANUC patch import: CHANGELOG version-to-file mapping derived from email bodies drifts by one patch"
domain: "fanuc"
tags:
  - "patch-import"
  - "changelog"
  - "version-mapping"
  - "xlsx"
  - "hex-dump"
  - "data-provenance"
  - "fanuc"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "补丁版本号和文件对不上，是因为版本号从邮件正文推导；以 xlsx 补丁号列为准，再用文件内版本串核对。"
trigger: "CHANGELOG 版本号 文件映射 偏移 补丁 v2.0.8-11 实际对应 v2.0.8-12 邮件正文 推导 xlsx 0x20"
verify: "对每个补丁文件跑 xxd -s 0x20 -l 32，读出的版本串与 xlsx 补丁号列逐条相等；不等的那条以 xlsx 修正 CHANGELOG。"
source: "intake-2015"
provenance:
  issue: "#2015"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# FANUC patch import: CHANGELOG version-to-file mapping derived from email bodies drifts by one patch

## Problem

批量把补丁数据导入到一个 Git 仓库时，CHANGELOG 里的「版本号 → 文件」映射整体偏了一位：例如 `v2.0.8-11` 名下的文件，实际是 `v2.0.8-12` 对应的那个。

导入过程本身没有报错——提交、文件都能写进仓库，是事后核对时才发现版本号和文件内容对不上。这类错位不会自己暴露：CHANGELOG 只是文本，不携带任何能自证"这个文件就是这一版"的信息，所以错位一旦发生，往往要等有人按版本号去取文件时才被发现。

报料者未给出偏移是从哪一条开始的，也未给出偏移了多少条。

## Root Cause

同一批补丁有三个来源并存：xlsx 表格、邮件（OWA）、飞书文档。三者的信息结构不一样，可靠性也不一样：

- **xlsx** 有明确的序号列和补丁号列，一行就是一条补丁，版本号和文件在同一行里，是唯一的**结构化**来源；
- **邮件正文**是散文。版本号要么在标题里，要么散在正文里，而回复链还会带进引用块和历史签名——"这个版本"、"上一版"、"见下"这类指代不携带绝对版本号，很容易把上一封邮件的版本号套到这一封的附件上；
- **飞书文档**是人工整理的说明，同样不是可机器校验的键值对。

版本号一旦从非结构化来源推导，一次错位就会沿着导入顺序传下去：后面的版本号整体对应到相邻补丁的文件上。邮件的线程结构还让这个错误看起来"有据可依"——引用块里确实出现过一个版本号，只是那是上一封的。

## Solution

1. **把结构化来源定为唯一权威**：版本号与文件的对应关系只从 xlsx 的补丁号列生成，邮件和飞书文档只用来补充说明，不用来生成键。这一步就把"从哪取版本号"从判断题变成了固定规则。

2. **用文件内部的版本串做第二判据**。FANUC 的 `.pc` 补丁文件在 offset `0x20` 处写有版本编码，可以直接从文件里读出来，不依赖任何外部文档：

   ```bash
   xxd -s 0x20 -l 32 <patch-file>.pc
   ```

3. **交叉验证，差异一律以 xlsx 为准**：把 CHANGELOG 与 xlsx、飞书文档、邮件逐条比对；每一条差异都记下来（哪一条、哪个来源、改成了什么），否则下一次导入会重犯同一处错误。

把第 2 步写成导入脚本里的断言，错位会在写 CHANGELOG 之前就停下：

```python
raw = path.read_bytes()
field = raw[0x20:0x40]                        # 版本字段，偏移由报料者在 .pc 上确定
assert expected_version in decode_version(field), (path.name, expected_version, field.hex())
```

`expected_version` 来自 xlsx 的那一行；`decode_version` 是这段代码里唯一没定下来的部分——版本字段的编码方式报料者未给出，见 Notes。

## Verification

- 对每个补丁文件跑 `xxd -s 0x20 -l 32`，把文件内的版本串与 xlsx 补丁号列逐条比较，必须条条相等。
- 飞书文档与 CHANGELOG 逐补丁比对，差异项全部以 xlsx 修正之后，CHANGELOG 里不再有"版本号与文件内版本串不一致"的行。

判据（可脱离上面两条命令使用）：任取 CHANGELOG 的一行，其版本号必须能在对应文件自身的版本字段里读出来；读不出或对不上，就是映射错位。这个判据不看文件名、不看邮件标题，所以它不会跟着推导链条一起错。

## Notes

- 报料者未给出：补丁总数、偏移从哪一条开始、`.pc` 版本字段的编码方式（ASCII 字符串 / 压缩 BCD / 其它）、以及 xlsx 的具体列名 —— 需复现确认。上面 `decode_version` 就是留给这一步的空位，不要凭猜测定死它。
- offset `0x20` 是报料者在这一批 `.pc` 文件上确定的；换机型或换补丁类型时先自己扫一遍确认偏移，不要假定它不变。
- 这一课的可泛化部分与 FANUC 无关：多个数据源并存时，键值只从有列名的结构化来源取；非结构化来源最多用来交叉验证，不能用来生成键。
- domain 选 `fanuc`：检索时输入的会是厂牌名和补丁文件类型（`.pc`），而不是上位学科名。
