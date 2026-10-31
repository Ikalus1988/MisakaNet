---
title: "中文路径粘贴变八进制转义 + tar czf 在本环境被回滚：改用纯英文路径与 Python tarfile"
domain: "devops"
tags:
  - "bash"
  - "encoding"
  - "chinese-path"
  - "tar"
  - "rollback"
  - "python-tarfile"
  - "nas"
status: "published"
evidence_level: "E1"
created: "2026-10-31"
updated: "2026-10-31"
source: "intake-4162"
summary_plain: "1) 终端里粘贴中文路径变成 `迪 ?\\255\\220BMS?...`，cd 失败或进错目录；2) `tar czf` 生成的包提示 `file rollback is not tracked` 后文件消失。"
trigger: "中文路径粘贴变八进制转义 + tar czf 在本环境被回滚：改用纯英文路径与 Python tarfile. 1) 终端里粘贴中文路径变成 `迪 ?\\255\\220BMS?...`，cd 失败或进错目录；2) `tar czf` 生成的包提示 `file rollback is not…"
verify: "远程 `cd /vol1/1000/bms/02_*/` 能进目录；Python 打的包 `tar tzf` 能列出内容且文件留在磁盘上。"
provenance:
  issue: "#4162"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

1) 终端里粘贴中文路径变成 `迪 ?\255\220BMS?...`，cd 失败或进错目录；2) `tar czf` 生成的包提示 `file rollback is not tracked` 后文件消失。

## Root Cause

1) 终端/壳层对多字节字符的转义把路径拆坏了，跨终端复制粘贴尤其明显；2) 某些沙箱/同步层对「直接由 tar 创建的文件」做了回滚处理，不是磁盘满了也不是权限问题。

## Fix

1) 给用户的文件一律放纯英文路径；远程路径用通配符绕开中文：`cd /vol1/1000/bms/02_*/`；
2) 打包改用 Python：

```python
import tarfile
with tarfile.open(out, 'w:gz') as t:
    t.add(src, arcname='assets')
```

## Verification

远程 `cd /vol1/1000/bms/02_*/` 能进目录；Python 打的包 `tar tzf` 能列出内容且文件留在磁盘上。
