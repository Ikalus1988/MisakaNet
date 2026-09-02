---
title: Cron 作业不执行 / 不生效排障
domain: contrib
tags:
- cron
- scheduler
- not-running
- debug
status: published
created: '2026-07-06'
language: zh
source: unknown
domain_expert: unknown
---

---
## Problem

`crontab -e` 设置好后，作业从未执行。输出没有、日志没有、进程没有。

## Root Cause

1. Cron 的环境变量与交互式 shell 完全不同（没有 PATH、没有 HOME 等）
2. Cron 语法错误（`* * * * *` 顺序记错）
3. Crontab 格式末尾缺换行符

## Solution

```bash
# Cron 作业不执行 / 不生效排障
sudo systemctl status cron
# 或
ps aux | grep cron

# 2. 打印当前 crontab
crontab -l

# 3. 写入测试作业（确认 cron 工作机制）
crontab -e
# 加一行：
* * * * * echo "CRON_ALIVE: $(date)" >> ~/cron_test.log 2>&1

# 4. 查看日志（大部分发行版）
sudo tail -f /var/log/syslog | grep CRON
# 或
sudo journalctl -u cron -f

# 5. 常见修复：在 cron 中显式设置 PATH
# 在 crontab 顶部添加：
PATH=/usr/local/bin:/usr/bin:/bin
SHELL=/bin/bash
HOME=/home/yourname

# 6. Python 脚本在 cron 中的完整写法
*/5 * * * * cd /path/to/project && /usr/bin/python3 script.py >> /tmp/script.log 2>&1
```

## Verification

```bash
cat ~/cron_test.log  # 每分钟应新增一行
```

**Expected Output:**
```
CRON_ALIVE: Mon Aug 27 10:00:01 UTC 2026
CRON_ALIVE: Mon Aug 27 10:01:01 UTC 2026
```

预期输出（每分钟追加一行，时间戳递增）：

```
CRON_ALIVE: Sun Jul  6 10:00:01 CST 2026
CRON_ALIVE: Sun Jul  6 10:01:01 CST 2026
CRON_ALIVE: Sun Jul  6 10:02:01 CST 2026
CRON_ALIVE: Sun Jul  6 10:03:01 CST 2026
```

若文件持续增长，说明 cron 服务运行正常；若文件为空或不存在，请检查 cron 服务状态及 crontab 语法。