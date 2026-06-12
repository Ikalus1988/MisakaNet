---
{"title": "the user sent a text document fanuc知识库方案 v5 md", "domain": "general", "source": "bootstrap", "status": "draft", "tags": [], "created": "2026-04-01", "updated": "2026-04-01", "confidence": 0.5}
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
The WSL session has been stable for 17 minutes. Before `guiApplications=false`, the session would crash within 14-53 seconds. Now it's been 17 minutes without issues. This confirms that the `g
[user] [The user sent a text document: 'RAG知识库完整说明文档.md'. Its content has been included below. The file is also saved at: ~/.hermes/cache/documents/doc_ce0caa2cff68_RAG知识库完整说明文档.md]

[Content of
[assistant] 已读完。这套方案的架构设计相当扎实，几个核心决策值得记下来：

**关键技术决策亮点：**
- **NTFS + Linux 分区分离**：向量库放 Linux ext4（ChromaDB/SQLite 依赖文件锁），文本缓存放 NTFS（JSON 原子读写），分工清晰
- **双层 PDF 回退**：`pymupdf4llm` → `pymupdf` 纯文本兜底，应对扫描版/损坏文件
- **中

## 用户描述
[The user sent a text document: 'FANUC知识库方案_v5.md'. Its content has been included below. The file is also saved at: ~/.hermes/cache/documents/doc_a6ed11aeee1c_FANUC知识库方案_v5.md]

[Content of FANUC知识库方案_v5.md]:
# FANUC 工业机器人知识库方案 v5

**更新**：2026-04-14
**状态**：POC 验证完成（检索召回率 60%）| 规模：3.4万 chunks / 143 PDF / 362 MB
**下一步**：5 模型 LLM 对比评测（llm-eval 脚本已就绪）

---

## 一、背景与目标

### 背景

工业机器人维护场景中，工程师需要从大量 FANUC 原厂手册（报警代码、参数配置、标定步骤、安全规范等）中快速定位答案。传统方式依赖人工翻阅 PDF 或记忆，效率低且容易出错。

### 目标

- 将约 20,000 页

## 助理回复
两份方案都读完了。以下是完整对比分析：

---

## 方案对比总览

| 维度 | 方案 A（Claude uptus / 企业微信版） | 方案 B（Hermes CLI / 飞书版） |
|------|---|---|
| **定位** | 通用工业文档（多格式多分类） | FANUC 垂直领域（PDF 为主） |
| **PoC 阶段** | 生产可用 | 评测验证中（60% Top-1） |
| **向量模型** | bge-base-zh-v1.5 · 768d · CPU | bge-small-en-v1.5 · 384d · RTX 4060 GPU |
| **分块策略** | 800 字符 / 100 重叠 / 中文标点分隔 | 512 tokens / 50 重叠 / 段落切分 |
| **检索算法** | 纯向量 cosine 相似度 | 双路召回（向量 + BM25 keyword boost） |
| **融合方式** | — | Simplified RRF（向量优先，BM25 兜底） |
| **表格处理** | 整页表格 → `\|` 分隔独立 chunk | 整页表格 → 8000 char 独立 chunk |
| **LLM** | InternalModel-Flash → Qwen-Plus → Ollama qwen2.5:3b（3 通道容灾） | MiniMax M2.5 API（单通道） |
| **接口** | Gradio Web UI + 企业微信 `/查` | 飞书 `/查` 命令 + CLI 脚本 |
| **文档规模** | 442 份（PDF/Word/PPT/Excel） | 143 份 PDF |
| **向量条数** | 22,181 | 34,100 |
| **建库耗时** | 20~30 分钟（CPU） | ~
