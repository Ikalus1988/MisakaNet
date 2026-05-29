#!/usr/bin/env python3
"""
MisakaNet 交互式安装向导 — 检查环境、配置依赖、生成 config.yaml。

用法:
  python3 scripts/setup.py          ← 交互式向导
  python3 scripts/setup.py --check  ← 只检查环境，不配置
"""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REQUIRED_PYTHON = (3, 10)


def _check(msg: str, ok: bool) -> None:
    icon = "✅" if ok else "❌"
    print(f"  {icon} {msg}")


def _run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=30, **kw)


def check_environment() -> dict:
    """检查环境并返回状态字典。"""
    print("\n🔍 环境检查")
    print("-" * 40)
    state = {}

    # Python 版本
    v = sys.version_info
    ok = v >= REQUIRED_PYTHON
    _check(f"Python {v.major}.{v.minor}.{v.micro}", ok)
    state["python_ok"] = ok

    # Git
    git_path = shutil.which("git")
    ok = git_path is not None
    _check(f"Git: {git_path or '未找到'}", ok)
    state["git_ok"] = ok

    if ok:
        try:
            gv = _run([git_path, "--version"])
            _check(f"  {gv.stdout.strip()}", True)
        except Exception:
            pass

    # GitHub 认证
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        try:
            r = _run(["git", "credential", "fill"],
                     input="protocol=https\nhost=github.com\n")
            for line in r.stdout.split("\n"):
                if line.startswith("password="):
                    token = line.split("=", 1)[1].strip()
                    break
        except Exception:
            pass
    ok = bool(token)
    _check(f"GitHub 认证: {'已配置' if ok else '未配置'}", ok)
    state["github_auth_ok"] = ok

    # 核心依赖（纯 stdlib，无需安装）
    _check("核心搜索: 零依赖（纯 Python stdlib）", True)
    state["core_ok"] = True

    # Hub 依赖检查
    hub_deps = {"aiohttp": False, "PyYAML": False, "networkx": False, "chromadb": False}
    for pkg in hub_deps:
        try:
            __import__(pkg.replace("-", "_"))
            hub_deps[pkg] = True
        except ImportError:
            pass
    hub_installed = sum(1 for v in hub_deps.values() if v)
    _check(f"Hub 依赖: {hub_installed}/{len(hub_deps)} 已安装", hub_installed == len(hub_deps))
    state["hub_deps"] = hub_deps
    state["hub_ok"] = hub_installed == len(hub_deps)

    # Lessons 统计
    lessons = list(REPO.glob("lessons/**/*.md"))
    ignore_names = {"index.md"}
    lessons = [f for f in lessons if f.name not in ignore_names and not f.name.startswith(".")]
    _check(f"Lessons 知识库: {len(lessons)} 篇", len(lessons) > 0)
    state["lesson_count"] = len(lessons)

    # Git 仓库状态
    if git_path:
        try:
            r = _run([git_path, "status", "--porcelain"], cwd=str(REPO))
            dirty = bool(r.stdout.strip())
            _check(f"Git 工作区: {'有未提交更改' if dirty else '干净'}", not dirty)
            state["git_dirty"] = dirty
        except Exception:
            pass

    # 是否已配置 hub
    config_path = REPO / "config.yaml"
    ok = config_path.exists()
    _check(f"Hub 配置: {'已配置' if ok else '未配置 (config.yaml 不存在)'}", ok)
    state["config_ok"] = ok

    print()
    return state


def setup_wizard():
    """交互式配置向导。"""
    state = check_environment()

    print("=" * 50)
    print("  MisakaNet 安装向导")
    print("=" * 50)

    # 安装 Hub 依赖
    if not state.get("hub_ok"):
        print("\n📦 Hub 依赖未完全安装")
        ans = input("  安装 Hub 依赖? (Y/n): ").strip().lower()
        if ans != "n":
            req = REPO / "requirements.txt"
            if req.exists():
                _run([sys.executable, "-m", "pip", "install", "-r", str(req)])
                print("  ✅ Hub 依赖安装完成")
            else:
                print("  ⚠️ 未找到 requirements.txt")

    # 配置 GitHub Token
    if not state.get("github_auth_ok"):
        print("\n🔑 GitHub Token 配置")
        print("  贡献 lesson 需要 GitHub Token")
        print("  获取: GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens")
        token = input("  输入 Token (跳过直接回车): ").strip()
        if token:
            # 写入 .env 文件
            env_path = REPO / ".env"
            existing = env_path.read_text(encoding="utf-8") if env_path.exists() else ""
            if "GITHUB_TOKEN" not in existing:
                with open(env_path, "a") as f:
                    f.write(f"\n# MisakaNet setup\nexport GITHUB_TOKEN={token}\n")
                print("  ✅ Token 已写入 .env")
                print("  生效: source .env")

    # 生成 config.yaml
    config_path = REPO / "config.yaml"
    example_path = REPO / "config.yaml.example"
    if not config_path.exists() and example_path.exists():
        print("\n⚙️ Hub 配置")
        ans = input("  创建 config.yaml（从示例复制）? (Y/n): ").strip().lower()
        if ans != "n":
            shutil.copy(str(example_path), str(config_path))
            print("  ✅ config.yaml 已创建")
            print("  编辑: nano config.yaml")
            ans = input("  现在编辑 config.yaml? (y/N): ").strip().lower()
            if ans == "y":
                editor = os.environ.get("EDITOR", "nano")
                subprocess.run([editor, str(config_path)])

    print("\n" + "=" * 50)
    print("  ✅ MisakaNet 就绪")
    print("=" * 50)
    print(f"  搜索:   python3 search_knowledge.py \"关键词\"")
    print(f"  贡献:   python3 scripts/contribute.py path/to/lesson.md")
    print(f"  新建:   python3 scripts/new_lesson.py")
    print(f"  Hub:    python3 hub/misaka_hub.py")
    print()


def main():
    parser = argparse.ArgumentParser(description="MisakaNet 安装向导")
    parser.add_argument("--check", action="store_true", help="只检查环境，不配置")
    args = parser.parse_args()

    if args.check:
        check_environment()
    else:
        setup_wizard()


if __name__ == "__main__":
    main()
