---
title: "bash 3.2：$VAR 后面紧跟中文/全角符号，变量名会被吞进去（unbound variable）"
domain: "devops"
tags:
  - "bash"
  - "bash3"
  - "macos"
  - "variable-expansion"
  - "unbraced"
  - "cjk"
  - "unbound-variable"
status: "published"
evidence_level: "E1"
created: "2026-10-31"
updated: "2026-10-31"
source: "intake-4176"
summary_plain: "```bash DISP=BaiduProbe echo \"非 ASCII：$DISP —— 会拒签"
trigger: "bash 3.2：$VAR 后面紧跟中文/全角符号，变量名会被吞进去（unbound variable）. ```bash DISP=BaiduProbe echo \"非 ASCII：$DISP —— 会拒签"
verify: "扫全仓 `.sh` 文件无输出；`bash -u` 下跑带中文后缀的 echo 不报 unbound variable；`bash --version` 确认为 3.2.x。"
provenance:
  issue: "#4176"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

```bash
DISP=BaiduProbe
echo "非 ASCII：$DISP —— 会拒签"

## Root Cause

macOS 自带的 bash 是 **3.2**，变量名解析把紧跟其后的多字节字符也当成标识符的一部分。`$DISP ——` 里的 `—` 被算进了变量名，于是找 `DISP—` 这个变量，`set -u` 下直接 unbound variable。

## Fix

变量后面接中文/全角符号时**一律加花括号**：

```bash
echo "非 ASCII：${DISP}，SideStore 会拒签"
echo "显示名=${DISP}（纯 ASCII）"
```

`${CRYPT:-0}（必须是 0）` 这种带默认值的本来就有花括号，没问题——**危险的是裸 `$VAR`**。

2026-10-28 同一天又踩两次（`bootstrap.sh` 第 103 行 `$ASSET）`、`pack-ipa.sh` 第 119 行 `$SECRETS，`）。教训：**别只修报错的那一行**，改完用脚本扫全文件（BSD grep 没有 `-P`，用 python）：

```python
import re, sys
for f in sys.argv[1:]:
    s = open(f, encoding='utf-8').read()
    for m in re.finditer(r'\$[A-Za-z_][A-Za-z0-9_]*', s):
        n = s[m.end():m.end() + 1]
        if n and ord(n) > 127:
            print(f, s[:m.start()].count(chr(10)) + 1, m.group())
```

## Verification

扫全仓 `.sh` 文件无输出；`bash -u` 下跑带中文后缀的 echo 不报 unbound variable；`bash --version` 确认为 3.2.x。
