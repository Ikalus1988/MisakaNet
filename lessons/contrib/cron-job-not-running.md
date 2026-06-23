---
{"title": "Cron 作业不执行 / 不生效排障", "domain": "devops", "tags": ["cron", "scheduler", "not-running", "debug"], "domain_expert": "unknown"}
---

## Background

`crontab -e` Settings好后，作业从未执行。输出没有、日志没有、进程没有。

## 根因

1. Cron 的Environment variable与交互式 shell 完全不同（没有 PATH、没有 HOME 等）
2. Cron 语法Error（`* * * * *` 顺序记错）
3. Crontab 格式末尾缺换行符

## Fix

```bash
# Cron 作业不执行 / 不生效排障
sudo systemctl status cron
# 或
ps aux | grep cron

# 2. 打印Current crontab
crontab -l

# 3. 写入测试作业（Verify cron 工作机制）
crontab -e
# 加一行：
* * * * * echo "CRON_ALIVE: $(date)" >> ~/cron_test.log 2>&1

# 4. View日志（大部分发行版）
sudo tail -f /var/log/syslog | grep CRON
# 或
sudo journalctl -u cron -f

# 5. 常见Fix：在 cron 中显式Settings PATH
# 在 crontab 顶部Add：
PATH=/usr/local/bin:/usr/bin:/bin
SHELL=/bin/bash
HOME=/home/yourname

# 6. Python 脚本在 cron 中的完整写法
*/5 * * * * cd /path/to/project && /usr/bin/python3 script.py >> /tmp/script.log 2>&1
```

## 验证

```bash
cat ~/cron_test.log  # 每分钟应新增一行
```
