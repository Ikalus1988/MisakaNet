---
domain: "archive"
title: "Self Grow Wiki Code Review"
verification: "metadata-normalized"
source: "skill-pipeline"
status: "draft"
created: "2026-05-09"
---

## 背景

（此 lesson 从 skill `self-grow-wiki-code-review` 自动提取，待补全）

## 根因

（待补充）

## 修复


# self-grow-wiki Code Review — 2026-04-28

## P0 — 必须修复

### 1. wxauto_bot.py — API Key 半明文
```python
# 当前
api_key=os.environ.get("DEEPSEEK_API_KEY", "sk-071...35ea")
# 改为
api_key=os.environ.get("DEEPSEEK_API_KEY", "")
```
删掉 fallback key，只从环境变量读。

### 2. rag_core.py — pickle.loads 无损坏保护
`_pickle.loads(BM25_INDEX_PATH.read_bytes())` 在文件损坏（磁盘满写入中断）时崩溃。
改为 try/except + 删除损坏缓存并重建。

## P1 — 架构问题

### 3. LLM 调用逻辑 5 处重复
每个文件自己创建 OpenAI client + message 构造 + error handling。建议抽象到 `_call_llm()`。

### 4. stream_options 设置方式缺陷
```python
try:
    kwargs["stream_options"] = {"include_usage": True}
except Exception:
    pass  # 永远不会触发
```
应改为根据通道特性（mioffice.cn 不支持）条件启用。

### 5. API Key 三处重复硬编码
rag_core.py, kb_selfcheck.py, rag_admin.py 各自定义了 MIOFFICE_API_KEY 和 API_BASE。
改为统一到 config 模块或环境变量。

### 6. rag_web.py 和 rag_admin.py 问答逻辑重复
process_query 同名同参数完全相同的两份。应导入共享。

## P2 — 代码质量

### 7. ~27处 except Exception: pass（含静默）
建议至少加 log.warning()，部分不合理 catch 直接删掉。

### 8. Token 粗估的系统性偏差
```python
tok_completion = len(answer) // 2  # 中文1字≈2token，英文偏差大
```

### 9. 硬编码路径散落 4 处
/rag_chromadb, rag_query_log.db, kb_conflict_report.md, kb_learning.json
建议集中到 PATHS dict。

### 10. SQLite 读操作无锁
写操作有 `_log_lock`，但 get_query_logs 等读操作没有。

### 11. .gitignore 已覆盖 .pyc 和 pycache/，没问题。

### 12. wxauto_bot.py 702 行单文件，需拆分。

## P3 — 设计建议

### 13. CLAUDE.md 提到 wechat_bot.py（wcferry）但仓库还有 wxauto_bot.py，冗余未说明。

### 14. 三通道缺 DeepSeek（flash→deepseek→pro→qwen）。

### 15. start_rag.sh 无进程监控/watchdog。

### 16. 降级消息含 Markdown 格式，微信渲染乱码。


## 修复状态 (Phase 2 完成 — 2026-04-29)

### 已完成 (13/16)
- P0-1: wxauto_bot.py key 改环境变量 ✓ (Phase 1)
- P0-2: BM25 缓存损坏保护 ✓ (Phase 1)
- P1-4: stream_options 条件启用 ✓ (Phase 1)
- P1-5: kb_selfcheck.py 导入 rag_core ✓ (Phase 1)
- P2-7: 13 处裸 except:pass → 8 处加 `logger.warning()`, 5 处保留 ✓
- P2-8: `len(answer)//2` → `estimate_tokens()` (中文×2 + 英文÷4) ✓
- P2-9: 硬编码路径 → `PATHS` dict, 4 文件导入 ✓
- P2-10: SQLite 读操作加 `_log_lock` (4 functions) ✓
- P2-11: 无需修复 ✓
- P3-13: CLAUDE.md wcferry vs wxauto 双方案说明 ✓
- P3-14: 四通道: +DeepSeek (deepseek-chat, env key) ✓
- P3-15: start_rag.sh watchdog 守护循环 ✓
- P3-16: 降级消息去 Markdown (###/**/--- → 【】纯文本) ✓

### 跳过 (1)
- P2-12: wxauto_bot.py 拆分 — 评估后跳过 (702行/18函数, 结构清晰)

### 未开始 (2)
- P1-3: LLM 调用抽象 (需较大重构, 低优先级)
- P1-6: rag_web/rag_admin process_query 重复 (需评估影响面)

## 修复过程教训

### 添加新导出时的 import 链
给 rag_core.py 加 `PATHS` dict 和 `estimate_tokens()` 后, 需同步更新所有消费方:
- rag_admin.py, rag_api.py, rag_builder.py, kb_selfcheck.py 的 `from rag_core import (...)` 元组
- 忘记更新会导致运行时 NameError
- 如有 inline import (`from rag_core import X` inside function), 需移到顶部

### with _log_lock 缩进陷阱
把函数体包裹进 `with _log_lock:` 时, 整个 body 需统一缩进。逐行 patch 容易产生部分代码留在 with 外的 bug。推荐: 一次性 patch 整个函数体（约 20-50 行）。

### except:pass 分类处理
并非所有 `except: pass` 都需要改。保留场景:
- doc_classifier.py:219 — fallback 到 alternate 实现
- rag_builder.py:348 — 删除可能不存在的 collection
- rag_core.py:567 — 已有上层 error logging, 内层仅 cleanup

### DeepSeek 通道注意
- 需要 `import os` (rag_core.py 原先未导入)
- mioffice.cn 网关不支持 deepseek-

## 验证

（待补充）
