---{"title": "Shell Debugging — set -x 与常见Pitfalls", "domain": "development", "tags": ["shell", "bash", "debug", "script"]}---

## Background

Shell 脚本报错但不显示Problem行，或Variable展开后不是预期Value。

## 根因

Shell Default只输出执行结果，不输出执行过程。Variable为空、特殊字符展开、IFS 分割等Problem只有看到「实际执行了什么Command」才能发现。

## Fix

```bash
#!/usr/bin/env bash
# Shell Debugging — set -x 与常见Pitfalls
set -x   # 打印执行的Command（+ 前缀）
set -e   # 任何Command失败时退出
set -u   # Use未定义Variable时报错
set -o pipefail  # 管道中任一Command失败也算失败

# 推荐组合：脚本开头加这一行
set -euxo pipefail

# Example - 没加 set -x 看不出Problem：
FILES=$(ls *.txt | head -5)
for f in $FILES; do  # 如果File名有空格，会被分割！
    echo "处理: $f"
done

# set -x 后会看到实际展开：
# ++ ls 'file 1.txt' 'file 2.txt'
# + FILES='file 1.txt
# file 2.txt'
```
## Verification

1. Follow the solution steps in order
2. Run any relevant commands or tests to confirm the fix
3. Verify the symptom no longer occurs
4. Check related logs or outputs for expected behavior


## 陷阱

| 场景 | Problem | Fix |
|------|------|------|
| File名含空格 | `for f in $FILES` 按空格分割 | `for f in "$FILES"` 或 `find -print0` |
| Variable未定义 | 变成空字符串 | `set -u` 捕获 |
| ls 结果赋Value | 带换行符 | 用 `mapfile` 或 `find` |
| 管道静默失败 | 前一个Command失败但 `|` 忽略 | `set -o pipefail` |
