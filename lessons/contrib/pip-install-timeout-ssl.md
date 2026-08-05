---
{
  "domain": "contrib",
  "title": "pip install Network Timeout / SSL ErrorFix",
  "verification": "metadata-normalized",
  "created": "2026-07-06",
  "source": "unknown"
}
---
---{"title": "pip install Network Timeout / SSL ErrorFix", "domain": "devops", "tags": ["pip", "network", "SSL", "timeout", "proxy"]}---

## 背景

`pip install` 失败，报 `timeout`、`SSL: CERTIFICATE_VERIFY_FAILED`、或 `Connection broken` 错误。

## 根因

PyPI 默认源在国外，网络不稳定或被墙。pip 默认超时 15 秒，大包下载不够。

## 修复

```bash
# pip install Network Timeout / SSL ErrorFix
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 2. 加长超时（临时）
pip install --default-timeout=120 <包名>

# 3. 关闭 SSL 验证（紧急，不推荐生产）
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org <包名>

# 4. 从缓存重建（如果网断了但缓存有部分）
pip install --no-cache-dir <包名>
```

## 验证

```bash
pip install requests -v  # 应正常完成
```
