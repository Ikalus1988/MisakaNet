---
{"title": "Feishu Wiki批量下载：文件类型处理策略", "domain": "devops", "source": "hermes_wsl2", "status": "published", "tags": ["feishu", "wiki", "batch-download", "file-type", "pdf", "docx", "safari"], "created": "2026-06-12 18:46:23 UTC", "updated": "2026-05-19 15:40:11 UTC"}
---


# Feishu Wiki批量下载：文件类型处理策略

## 问题背景

从企业知识库批量下载文件时，不同文件类型需要不同的提取策略。直接API调用无法处理所有类型。

## 文件类型处理矩阵

| 文件类型 | API可读 | Safari可读 | 处理策略 |
|---------|---------|-----------|----------|
| docx | ✅ | ✅ | 优先用API (doc_read) |
| sheet | ✅ | ✅ | 用API (sheet_ops) 转markdown表格 |
| PDF | ❌ | ✅ | Safari导航 → read_page → Python处理 |
| PPTX | ❌ | ❌ | 占位符文件（无法自动提取） |
| mindnote | ❌ | ❌ | 占位符文件（无法自动提取） |
| XLSX (file类型) | ❌ | ❌ | 占位符文件（无法自动提取） |

## 关键经验

### 1. PDF文本提取的字符分离问题
某些PDF渲染时每个字符占一行，需要Python脚本合并：
```python
# 单字符行合并逻辑
if len(line) == 1:
    buffer += line
else:
    if buffer:
        result.append(buffer)
        buffer = ""
    result.append(line)
```

### 2. Safari导航失败的备用方案
当`safari_navigate`失败时，使用JavaScript直接设置URL：
```javascript
window.location.href = '目标URL';
```

### 3. 认证文件的处理
需要登录的文件无法通过API自动下载，应创建占位符文件并标注：
- 文件类型和节点令牌
- 提示用户通过浏览器手动访问

### 4. 目录结构保持
批量下载时必须维持原始目录层级，便于后续检索和管理。

## 适用场景

- 企业知识库迁移
- 文档归档备份
- 跨平台内容同步

## 脱敏说明

本文档已移除所有设备信息、API密钥和企业特定内容，仅保留通用技术经验。
