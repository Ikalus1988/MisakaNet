---
{"title": "the user sent a text document rag知识库完整说明文档 md", "domain": "general", "source": "bootstrap", "status": "draft", "tags": [], "created": "2026-04-01", "updated": "2026-04-01", "confidence": 0.5}
---


---
tags:
- bootstrap
status: draft
source: bootstrap
domain: general
created: '2026-04-01'
confidence: 0.7
---



## 背景
[assistant] <think>
Great, Hermes CLI is working. The user confirmed it. Let me also check the current watchdog status to see if the WSL session has been stable since the `guiApplications=false` change.
</think>

[assistant] <think>
The WSL session has been stable for 17 minutes. Before `guiApplications=false`, the session would crash within 14-53 seconds. Now it's been 17 minutes without issues. This confirms that the `g

## 用户描述
[The user sent a text document: 'RAG知识库完整说明文档.md'. Its content has been included below. The file is also saved at: ~/.hermes/cache/documents/doc_ce0caa2cff68_RAG知识库完整说明文档.md]

[Content of RAG知识库完整说明文档.md]:
# RAG 智能问答 — 技术文档知识库 & 企业微信接入 完整说明文档

> 项目全生命周期复盘 | 2026-04  
> 颗粒度：每一个具体细节、问题处理过程、决策依据

---

## 目录

1. [项目概述与最终成果](#一项目概述与最终成果)
2. [环境搭建全过程](#二环境搭建全过程)
3. [文档分类系统 (doc_classifier.py)](#三文档分类系统)
4. [RAG 向量库构建 (rag_builder.py)](#四rag-向量库构建)
5. [智能问答 Web UI (rag_web.py)](#五智能问答-web-

## 助理回复
已读完。这套方案的架构设计相当扎实，几个核心决策值得记下来：

**关键技术决策亮点：**
- **NTFS + Linux 分区分离**：向量库放 Linux ext4（ChromaDB/SQLite 依赖文件锁），文本缓存放 NTFS（JSON 原子读写），分工清晰
- **双层 PDF 回退**：`pymupdf4llm` → `pymupdf` 纯文本兜底，应对扫描版/损坏文件
- **中文分块标点优化**：`separators` 加了 `。` 和 `；`，避免汉子中间硬切
- **三通道容灾**（云端 × 2 → 本地 Ollama → 纯检索），降级链路完整
- **企业微信异步主动推送**：回调 5s 超时用后台线程绕过

**待发 CLI 方案**，收到后从以下几个维度对比：

| 维度 | 这套方案 | CLI 方案 |
|------|---------|---------|
| 向量模型 / 维度 | BAAI/bge-base-zh-v1.5 (768d) | ? |
| 分块策略 | 800字符/100重叠，中文标点 | ? |
| 检索算法 | 纯向量相似度 | ? |
| LLM 容灾 | InternalModel→Qwen→Ollama→纯检索 | ? |
| 接入方式 | Gradio Web + 企业微信 | ? |
| 部署复杂度 | 多服务多端口 | ? |
| 增量更新 | 待实现 | ? |
| 踩坑记录 | 12条详细复盘 | ? |

发来吧。
