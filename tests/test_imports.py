#!/usr/bin/env python3
"""
MisakaNet 基础导入测试
验证所有模块可被正常导入，无语法错误或缺失依赖。

运行: python3 tests/test_imports.py
需要安装依赖: pip install -r requirements.txt
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 模块清单：(module_name, needs_deps, description)
MODULES = [
    ("storage.knowledge_graph",      ["networkx"],     "知识图谱"),
    ("storage.vector_store",         ["chromadb"],     "向量存储"),
    ("sync.feishu_notifier",         [],               "飞书通知器"),
    ("sync.feishu_ws_client",        [],               "飞书 WebSocket"),
    ("sync.sync_scheduler",          [],               "同步调度器"),
    ("sync.a2a_server",              ["aiohttp"],      "A2A 协议服务 (dead code)"),
    ("orchestrator.arbitration_queue", [],              "仲裁队列"),
    ("orchestrator.confidence",      [],               "置信度模型"),
    ("orchestrator.dedup_engine",    ["chromadb"],     "语义去重 (dead code)"),
    ("orchestrator.subscription",    [],               "订阅管理"),
    ("master.token_manager",         [],               "令牌管理"),
    ("master.command_handler",       [],               "Master 命令 (dead code)"),
]


def check_deps(needs):
    """检查依赖是否可用"""
    missing = []
    for dep in needs:
        try:
            __import__(dep)
        except ImportError:
            missing.append(dep)
    return missing


def main():
    passed = skipped = failed = 0
    print("MisakaNet 导入测试\n")
    print(f"{'模块':<35} {'状态':<8} 说明")
    print("-" * 70)

    for mod_name, needs, desc in MODULES:
        label = f"  {mod_name:<33}"
        missing = check_deps(needs)
        if missing:
            print(f"{label} ⏭  SKIP  缺少依赖: {', '.join(missing)}")
            skipped += 1
            continue
        try:
            __import__(mod_name)
            print(f"{label} ✅  OK    {desc}")
            passed += 1
        except SyntaxError as e:
            print(f"{label} ❌  SYNTAX {e}")
            failed += 1
        except ModuleNotFoundError as e:
            print(f"{label} ❌  MISS   {e.name}")
            failed += 1
        except Exception as e:
            print(f"{label} ❌  FAIL   {e}")
            failed += 1

    print(f"\n{'='*50}")
    print(f"  总计: {passed+skipped+failed}  |  ✅ {passed}  ⏭ {skipped}  ❌ {failed}")
    print(f"{'='*50}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
