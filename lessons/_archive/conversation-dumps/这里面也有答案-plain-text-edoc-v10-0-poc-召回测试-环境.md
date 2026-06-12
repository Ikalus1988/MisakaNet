---
{"title": "这里面也有答案？ ```PLAIN_TEXT # Edoc V10.0 POC 召回测试 ## 环境", "domain": "rag", "source": "bootstrap", "status": "draft", "tags": [], "created": "2026-04-01", "updated": "2026-04-01", "confidence": 0.7}
---


## 背景
[assistant] <think>
Good news: new document created and content written successfully. The error is just in the wiki update (non-critical JSON parse error). The new document is `https://open.feishu.cn/document/RkB
[user] 你发出改好的脚本，我替换
[assistant] <think>
The user wants me to send the updated exam script so they can replace the one in the wiki.
</think>

```python
#!/usr/bin/env python3
"""
Edoc V10.0 POC 召回考试脚本
用法:
  python3 ~/.hermes/scripts/

## 用户描述
这里面也有答案？
```PLAIN_TEXT
# Edoc V10.0 POC 召回测试
## 环境依赖
- 向量库：/mnt/d/Eric/知识库/chroma_db（collection: edoc_v10，34,549 chunks）
- 模型：BAAI/bge-small-en-v1.5（384维）
- 预存向量：~/.hermes/scripts/q_embeddings.npz
## Q1-Q10 测试集
| 题号 | 测试点 | Query | v1 Top-1 |
|------|--------|-------|----------|
| Q1 | 急停报警 SRVO-001 | SRVO-001 Operator panel E-stop alarm | B-83304EN-2_02_01 |
| Q2 | 刚性参数 SRVO-050 | SRVO-050 Rigid parameter insufficient | B-83284EN-1_07_01 |
| Q3 | 通信故障 CD38A | CD38A Ethernet communication failur

## 助理回复
<think>
The user is showing me a wiki document that also contains the v1 Top-1 answers. This is the wiki document that was set up as the exam reference. The "v1 Top-1" column IS the expected answer - so yes, this wiki page contains the answers too.

The user needs to remove the "v1 Top-1" column from this wiki page as well. I should help them fix this.
</think>

是的，「v1 Top-1」列就是答案。Bot 看到这个表就等于看到答案。

需要把这一列删掉，只保留题目。你把链接发我，我来改 wiki 内容。
