---{"title": "WSL Windows 终端复制粘贴吞下划线Issue", "domain": "devops", "tags": ["wsl", "terminal", "windows", "encoding"]}---

## Background

从 Windows 复制文本粘贴到 WSL 终端时，下划线 `_` 字符消失。Configuration file、Command中的下划线名全部Error。

## 根因

Windows Terminal 的「Use Ctrl+Shift+C/V 作为复制粘贴」和「将文本格式Settings为 HTML」同时启用时，某些Version的 Windows Terminal 在 VIM/Python REPL 中粘贴时过滤了下划线。

## Fix

```bash
# WSL Windows 终端复制粘贴吞下划线Issue
# Settings → 交互 → 将文本格式Settings为 HTML → 关闭

# 方案 2：右键粘贴代替 Ctrl+Shift+V（不经过过滤）

# 方案 3：ViaFile中转
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
