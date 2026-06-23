---
domain: "archive"
title: "Knowledge Base Quality Audit"
verification: "metadata-normalized"
source: "skill-pipeline"
status: "draft"
created: "2026-05-09"
---

## 背景

（此 lesson 从 skill `knowledge-base-quality-audit` 自动提取，待补全）

## 根因

（待补充）

## 修复


# 知识库质量审计流水线 + 飞轮闭环

## 背景

230K+ chunks 的 RAG 向量库存在三类质量缺陷：
- **OCR 污染**: pymupdf4llm 插入 `==> picture omitted <==` 标记
- **版本冗余**: 同一内容的多个版本（CM/03 vs CM/05）被分别导入
- **来源混乱**: chunk 的 source 标注与实际不一致

## 执行环境

所有脚本必须在 mkdocs-env 虚拟环境中运行：
```bash
source ~/mkdocs-env/bin/activate
python3 daily_audit.py
```
直接 `python3` 会报 `ModuleNotFoundError: No module named 'openai'`。
cron job 的 prompt 中也要包含激活 venv 的步骤。

## 质量流水线执行顺序

### P0a: 源文件完整性
```bash
cd ~ && source ~/mkdocs-env/bin/activate
CUDA_VISIBLE_DEVICES="" python3 p0_source_map.py
```
检查 DB 中所有 filename 是否能在文件系统中找到对应 PDF。
输出 `/tmp/source_mapping.json`。

### P0b: 污染清洗
```bash
cd ~ && source ~/mkdocs-env/bin/activate
CUDA_VISIBLE_DEVICES="" python3 p0_cleanup_simple.py
```
确定性替换（无需 LLM）：
- `==> picture [NxN] omitted <==` → 删除整行
- `grep: binary file matches` → 删除
- 零宽字符 strip
- 纯数字/符号噪音行 → 删除

### P1a: 版本去重 (MinHash)
```bash
cd ~ && source ~/mkdocs-env/bin/activate
CUDA_VISIBLE_DEVICES="" python3 p1_dedup.py
```
每个 chunk 生成 MinHash 签名（64-bit, 5-char shingle）。
Jaccard 相似度 > 0.85 → 视为重复。
跨文件重复组中保留版本号最大的 chunk。
注意：会修改 ChromaDB（删除重复），运行前确保 RAG API 已停止。

### P1b: 来源校正
```bash
cd ~ && source ~/mkdocs-env/bin/activate
CUDA_VISIBLE_DEVICES="" python3 p1_reassign_fast.py
```
仅扫描含 B-xxxxx 编号但 filename 不匹配的 chunk，修正 source 字段。

### P2a: 质量分
```bash
cd ~ && source ~/mkdocs-env/bin/activate
CUDA_VISIBLE_DEVICES="" python3 p2a_quality_score.py
```
给每 chunk 添加 metadata: `quality_score`(0-1), `quality_label`(优/良/中/差)。
评分规则：base=1.0，含污染标记 -0.3，噪音行 -0.2，过短 -0.1。

### P2b: 增量质检门禁
```bash
python3 p2b_ingest_gate.py /path/to/new.pdf
```
新 PDF 入库前检查：
- picture omitted 污染
- 二进制残留
- 图片为主（文本过少）
- 与现有文档重复
返回 0=通过，非0=失败。

## 飞轮闭环（检索质量自迭代）

这不是单向的"越考越准"，而是**诊断 → 修复 → 验证**的完整飞轮。

```
                    ┌─────────────────────────┐
                    │  每天 9:00 巡检          │
                    │  随机考 7 道检索测试题    │
                    │  (L1单实体/L2跨文档/L3语义)│
                    └────────┬────────────────┘
                             │
                      ┌──────┴────────┐
                      │  全部通过 ✅   │  有失败 ❌
                      └──────┬────────┘
                             │
                    ┌────────┴──────────────────┐
                    │  自动诊断根因              │
                    │                            │
                    │  ├ "关键词未命中" → 加同义词│ ← 低风险，自动执行
                    │  │  (写入 synonyms.json)    │
                    │  │                          │
                    │  ├ "品牌污染"     → 补过滤词│ ← 建议，需确认
                    │  │                          │
                    │  ├ "分数太低"     → 查文档/ │
                    │  │  切分/权重     → 给建议  │ ← 高风险，给建议
                    │  │                          │
                    │  └ 写入 badcase_pending     │
                    └────────┬──────────────────┘
                             │
               ┌─────────────┴─────────────┐
               │                           │
    ┌──────────┴──────────┐      ┌─────────┴──────────┐
    │  日常巡检失败       │     

## 验证

（待补充）
