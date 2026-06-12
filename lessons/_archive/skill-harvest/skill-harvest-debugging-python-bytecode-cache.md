---
{"title": "Debugging Python Bytecode Cache", "domain": "general", "source": "skill-pipeline", "status": "draft", "tags": [], "created": "2026-05-09", "updated": "2026-05-09"}
---


## 背景

（此 lesson 从 skill `debugging-python-bytecode-cache` 自动提取，待补全）

## 根因

（待补充）

## 修复


# Python Bytecode Cache Debugging

## Symptom
Python 代码修改后行为不变——函数返回错误值、返回 None、或表现和旧版本一样。stderr 无语法错误，反复运行结果相同。

## Root Cause Checklist

1. **`.pyc` 缓存文件** — Python import 使用编译后的 `.pyc` 字节码，不一定读取 `.py` 源文件。如果 `__pycache__/*.pyc` 比 `.py` 新，Python 优先用缓存。这在以下情况发生：
   - 文件被修改时 Python 进程正在运行（Python 启动时就预加载了模块）
   - 通过 subprocess 调用脚本（gateway 调用 venv python）时，venv 有独立的 `__pycache__`

2. **模块级 vs 嵌套函数缩进** — 批量去缩进代码块时，逐行验证缩进是否正确。用 `ast.parse()` + `inspect.getsource()` 交叉验证。

3. **venv 路径** — 多个 venv 各自有独立的 `__pycache__`。调试时必须用生产代码实际使用的 Python 解释器。

## 排查步骤

### Step 1: 验证实际执行的字节码
```bash
python3 -c "
import sys; sys.path.insert(0, '/path/to/scripts')
import script_name
import inspect, dis
src = inspect.getsource(script_name.function_name)
print(f'Source lines: {len(src.split(chr(10)))}')
print('Last 5 lines:', src.split('\n')[-5:])
for instr in dis.Bytecode(script_name.function_name):
    if 'RETURN' in instr.opname:
        print(f'Return at offset: {instr.offset}')
"
```

### Step 2: 检查 .pyc 文件时间戳
```bash
ls -la /path/to/scripts/__pycache__/*.pyc
stat /path/to/scripts/script.py | grep -E "Modify|Change"
```

### Step 3: 清理 .pyc 缓存
```bash
rm -f /path/to/scripts/__pycache__/*.pyc
```

### Step 4: AST 验证
```bash
python3 -c "import ast; ast.parse(open('/path/to/script.py').read()); print('✅ Syntax OK')"
```

## 核心经验
当 `hybrid_search` 修改后仍然返回空结果，但源码看起来正确时：根因是 stale `.pyc`（Python 执行的是旧字节码）。执行 `rm __pycache__/*.pyc` 后恢复正常。

## 本次案例 (2026-04-16)
- `rag_answer.py` 中 `_get_tag_filter` 意外去缩进变成模块级函数
- `hybrid_search` 在 `keywords = ...` 后直接 `return None`
- `__main__` 也忽略了 CLI 参数（无 `sys.argv` 解析）
- 修复：重建 `hybrid_search` 函数体 + 添加 CLI 参数解析
- 清理：删除 `__pycache__/*.pyc` 确保新代码被加载


## 验证

（待补充）
