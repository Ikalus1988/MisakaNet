---
{"title": "scripts/new_lesson.py 在 Windows/WSL 边界因非法文件名崩溃", "domain": "scripts", "source": "agent", "status": "published", "tags": ["python", "path", "slugify", "windows", "wsl"], "created": "2026-05-30 22:00:00 UTC", "updated": "2026-05-30 22:00:00 UTC"}
---

## 问题

`scripts/new_lesson.py` 的 `_slugify()` 在生成文件名时，若标题全为特殊字符（如 `!!!`）会产出空 slug，导致写入 `.md` 这种无文件名的路径，直接触发 `OSError`。此外，Windows 保留名（`CON`, `AUX`, `NUL`, `COM1`…）在 NTFS/WSL 边界上会导致写入失败或不可预期的路径解析。

## 根因

原实现仅用正则保留 `[a-z0-9\u4e00-\u9fff]`，虽能替换大部分非法字符，但：
1. 没有兜底空 slug 的场景；
2. 未处理 Windows 保留文件名；
3. 多个连字符未压缩，可能产生 `--` 这种对 URL 不友好的结果。

## 修复方案

在 `scripts/new_lesson.py` 中重写 `_slugify()`：

```python
def _slugify(title: str) -> str:
    """Sanitize a title into a safe, cross-platform filename stem."""
    _RESERVED = {
        "con", "prn", "aux", "nul",
        "com1", "com2", "com3", "com4", "com5",
        "com6", "com7", "com8", "com9",
        "lpt1", "lpt2", "lpt3", "lpt4", "lpt5",
        "lpt6", "lpt7", "lpt8", "lpt9",
    }

    slug = title.lower().strip()
    slug = re.sub(r"[^a-z0-9\u4e00-\u9fff-]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    slug = slug.strip("-")
    if not slug:
        slug = "untitled"
    if slug in _RESERVED:
        slug = f"{slug}_lesson"
    return slug[:60]
```

关键点：
- 任何非安全字符（含 `/ \ : * ? " < > |` 与 emoji）统一替换为 `-`；
- 压缩连续 `-` 为单个；
- 空 slug 时回退到 `untitled`；
- 命中 Windows 保留名时追加 `_lesson` 后缀；
- 仍保持 60 字符上限与 CJK 支持。

## 验证

```bash
# 1. 直接运行脚本验证生成行为
python3 -c "
from scripts.new_lesson import _slugify
assert _slugify('!!!') == 'untitled'
assert _slugify('CON') == 'con_lesson'
assert _slugify('test/slash') == 'test-slash'
print('All assertions passed.')
"

# 2. 使用知识检索确认 lesson 已入库
python3 search_knowledge.py "slugify windows path"
```

---

*自动生成于 2026-05-30 22:00:00 UTC | 来源: agent*
