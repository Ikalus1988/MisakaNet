---
{"title": "Shell 脚本调试 — set -x 与常见陷阱", "domain": "development", "source": "unknown", "status": "draft", "tags": ["shell", "bash", "debug", "script"], "created": "2026-06-12 18:46:23 UTC", "updated": "2026-06-12 18:46:23 UTC"}
---


## 背景

Shell 脚本报错但不显示问题行，或变量展开后不是预期值。

## 根因

Shell 默认只输出执行结果，不输出执行过程。变量为空、特殊字符展开、IFS 分割等问题只有看到「实际执行了什么命令」才能发现。

## 修复

```bash
#!/usr/bin/env bash
# 调试模式：在执行前打印每一条命令
set -x   # 打印执行的命令（+ 前缀）
set -e   # 任何命令失败时退出
set -u   # 使用未定义变量时报错
set -o pipefail  # 管道中任一命令失败也算失败

# 推荐组合：脚本开头加这一行
set -euxo pipefail

# 示例 - 没加 set -x 看不出问题：
FILES=$(ls *.txt | head -5)
for f in $FILES; do  # 如果文件名有空格，会被分割！
    echo "处理: $f"
done

# set -x 后会看到实际展开：
# ++ ls 'file 1.txt' 'file 2.txt'
# + FILES='file 1.txt
# file 2.txt'
```

## 陷阱

| 场景 | 问题 | 修复 |
|------|------|------|
| 文件名含空格 | `for f in $FILES` 按空格分割 | `for f in "$FILES"` 或 `find -print0` |
| 变量未定义 | 变成空字符串 | `set -u` 捕获 |
| ls 结果赋值 | 带换行符 | 用 `mapfile` 或 `find` |
| 管道静默失败 | 前一个命令失败但 `|` 忽略 | `set -o pipefail` |
