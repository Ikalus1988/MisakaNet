---
title: Feishu Markdown Table Not Rendered
language: en
---

> **English Translation**
> Translated from Chinese original.

---{"title": "飞书 post Messaging中 Markdown 表格不渲染", "domain": "development", "source": "Misaka10019", "tags": ["feishu", "markdown", "table", "post", "lark"]}---

## 背景

在飞书 IM 消息中使用 `post` 类型的富文本消息发送 Markdown 表格，表格显示为空白或原始分隔线（`|------|`），而不是渲染后的表格。

## 根因

飞书 `post` 消息类型中 `<tag>md</tag>` 标签内的 Markdown 表格在客户端不解析。飞书 post 格式不支持原生 Markdown 表格渲染，无论是直接发送表格还是放在代码块里。

## 修复

在发送前，用 `<br>` 标签替换表格的分隔符 `|`，打断表格行连续性，使飞书客户端能够渲染：

```python
import re

def _optimize_markdown_style(content: str) -> str:
    """飞书 post 中表格渲染修复：用 <br> 替换 | 分隔"""
    lines = content.split('\n')
    result = []
    in_table = False
    
    for line in lines:
        is_table_line = bool(re.match(r'^\s*\|.*\|\s*$', line))
        if is_table_line:
            # 表格行：替换 | 为 <br> 分隔符
            line = re.sub(r'\|', '<br>', line)
            # 清理多余的 <br> 前后空格
            line = re.sub(r'\s*<br>\s*', ' | ', line).strip()
            line = f'<br>{line}<br>'
            in_table = True
        else:
            in_table = False
        result.append(line)
    
    return '\n'.join(result)
```

## 验证

修复后，表格在飞书客户端正常渲染为结构化形式，不再是空白或原始文本。

## 限制

- 此修复适用于飞书 post 消息，其他平台不适用
- 如果表格出现在消息开头（前无换行），`<br>` 注入逻辑需要额外处理边界情况
- 飞书官方暂无原生的 Markdown 表格支持，此为权宜之计
