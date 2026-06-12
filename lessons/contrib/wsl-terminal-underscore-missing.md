---
{"title": "WSL Windows 终端复制粘贴吞下划线问题", "domain": "devops", "source": "unknown", "status": "draft", "tags": ["wsl", "terminal", "windows", "encoding"], "created": "2026-06-12 18:46:23 UTC", "updated": "2026-06-12 18:46:23 UTC"}
---


## 背景

从 Windows 复制文本粘贴到 WSL 终端时，下划线 `_` 字符消失。配置文件、命令中的下划线名全部错误。

## 根因

Windows Terminal 的「使用 Ctrl+Shift+C/V 作为复制粘贴」和「将文本格式设置为 HTML」同时启用时，某些版本的 Windows Terminal 在 VIM/Python REPL 中粘贴时过滤了下划线。

## 修复

```bash
# 方案 1：在 Windows Terminal 设置中关闭「将文本格式设置为 HTML」
# 设置 → 交互 → 将文本格式设置为 HTML → 关闭

# 方案 2：右键粘贴代替 Ctrl+Shift+V（不经过过滤）

# 方案 3：通过文件中转
# Windows:
echo "your_text_with_underscores" > \\\\wsl$\\<distro>\\home\\hp\\temp.txt

# WSL:
cat ~/temp.txt
```

## 验证

在 WSL 终端中输入：
```bash
echo "test_text_with_underscores"
# 应显示完整下划线
```
