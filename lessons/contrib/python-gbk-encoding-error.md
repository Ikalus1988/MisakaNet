---{"title": "Python GBK Encoding Error — Windows/WSL 跨平台", "domain": "devops", "tags": ["python", "encoding", "gbk", "windows", "wsl"]}---

## Background

在 WSL 中Run Python 脚本，读取或写入File时报：
```
UnicodeDecodeError: 'gbk' codec can't decode byte ...
```
或 Cron 日志中出现乱码。

## 根因

Windows Default编码是 GBK，WSL 是 UTF-8。当 Python 在 WSL 中读取来自 Windows 的File或输出日志到挂载盘时，Default编码检测失效。

## Fix

```python
# Python GBK Encoding Error — Windows/WSL 跨平台
with open("file.txt", "r", encoding="utf-8") as f:
    content = f.read()

# 2. 写入File时指定编码
with open("file.txt", "w", encoding="utf-8") as f:
    f.write(content)

# 3. SettingsEnvironment variable（推荐永久）
# 在 ~/.bashrc 中Add：
export PYTHONIOENCODING=utf-8
export LANG=C.UTF-8

# 4. 对系统日志
sudo locale-gen zh_CN.UTF-8
```

## 验证

```bash
python3 -c "import sys; print(sys.getdefaultencoding())"
# 应输出 utf-8
```
