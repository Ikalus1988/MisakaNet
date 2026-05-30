---
{"title": "OpenAI 兼容 API 的通用调用格式", "domain": "development", "tags": ["api", "openai", "llm", "inference", "chat"]}
---

## 背景

部署了 LLM 服务（vLLM/Ollama/本地推理）后，不知道怎么用 API 调用。各框架接口不一。

## 根因

大部分 LLM 服务实现了 OpenAI 兼容的 API 格式，但端点和参数细节有差异。

## 修复

```python
import requests
import json

url = "http://localhost:11434/v1/chat/completions"  # Ollama 示例
headers = {"Content-Type": "application/json"}

payload = {
    "model": "qwen2.5:7b",
    "messages": [
        {"role": "system", "content": "你是专业助手"},
        {"role": "user", "content": "你好"}
    ],
    "temperature": 0.7,
    "max_tokens": 1024,
    "stream": False
}

resp = requests.post(url, headers=headers, json=payload)
data = resp.json()
print(data["choices"][0]["message"]["content"])
```

## 常见服务端点

| 服务 | 端点 | 默认端口 |
|------|------|---------|
| OpenAI | `https://api.openai.com/v1` | — |
| Ollama | `http://localhost:11434/v1` | 11434 |
| vLLM | `http://localhost:8000/v1` | 8000 |
| 任何 OpenAI 兼容服务 | `http://host:port/v1` | 自定义 |

## 验证

```bash
# 检查可用模型
curl -s http://localhost:11434/v1/models | python3 -m json.tool
```
