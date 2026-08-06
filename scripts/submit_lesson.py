#!/usr/bin/env python3
"""一键提交 Lesson — 检查 + 脱敏 + 提交 + 推送.

用法:
  python3 scripts/submit_lesson.py lessons/contrib/my-lesson.md                           # 提交单个文件
  python3 scripts/submit_lesson.py lessons/contrib/                                        # 提交整个目录
  python3 scripts/submit_lesson.py lessons/contrib/my-lesson.md --message "lesson: fix xx" # 自定义 commit 信息

功能:
  1. 文件名检查: 无中文, kebab-case, 无项目前缀
  2. Frontmatter 检查: JSON 合法, 必填字段
  3. 内容脱敏: 自动替换已知敏感模式
  4. 去重检查: 检查标题/内容是否与已有 lesson 相似
  5. 自动 git commit + push (从 JOIN.md 或环境变量读取 PAT)
"""

import json, re, sys, os, subprocess, hashlib
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LESSONS = REPO / "lessons"
CONTRIB = LESSONS / "contrib"

# ─── 敏感内容检查清单 (新增项加在这里) ────────────────────────────
SENSITIVE_PATTERNS = [
    # 硬编码路径
    (r'/mnt/c/Users/\w+/',                'hardcoded path → use <project-path>'),
    (r'C:\\Users\\\w+\\',                'hardcoded path → use <project-path>'),
    # 特定用户名 (非项目白名单)
    (r'\bzsxh1990\b',                     'username → use <user>'),
    (r'\bcc_haha\b',                      'username → use <agent>'),
    (r'\bIkalus1988\b(?![A-Z])',          'GitHub org → use <org>'),
    (r'\bsheldonisspark\b',               'username → remove or use <user>'),
    (r'\bsheldonisspark-lab\b',           'username → remove or use <user>'),
    (r'\bericjia1920-max\b',              'username → remove or use <user>'),
    # 特定项目/产品名 (内部代号, 外部不可见)
    (r'\bmify\b',                         'internal project name → use <platform> or remove'),
    (r'\bxiaomi\b(?!( )|$)',              'brand name → use <brand> or generalize'),
    (r'\bInternalGateway\b',              'internal service → use <gateway>'),
    (r'\bInternalModel\b',                'internal model → use <model>'),
    # 凭据/Token 模式
    (r'ghp_\w{36,40}',                    'GitHub PAT detected → REMOVE'),
    (r'github_pat_\w{80,100}',             'GitHub fine-grained PAT detected → REMOVE'),
    (r'sk-[a-zA-Z0-9]{20,}',              'API key detected → REMOVE'),
    (r'cfut_\w{40,}',                     'Cloudflare token detected → REMOVE'),
    (r'AKIA[0-9A-Z]{16}',                'AWS key detected → REMOVE'),
]

# ─── 自动替换模式 (程序化脱敏) ──────────────────────────────────
AUTO_REPLACE = [
    (r'/mnt/c/Users/\w+/',           '<project-path>/'),
    (r'C:\\Users\\\w+\\',            '<project-path>\\\\'),
    (r'\bzsxh1990\b',                '<user>'),
    (r'\bcc_haha\b',                 '<agent>'),
    (r'\bIkalus1988\b(?![A-Z])',     '<org>'),
]

# ─── 禁止文件名前缀 ────────────────────────────────────────────
BANNED_PREFIXES = [
    "cc-connect", "ccswitch", "codewhale", "deepseek-tui",
    "hermes-", "node_", "st2-", "node2-",
]

CHINESE_RE = re.compile(r'[\u4e00-\u9fff]')


def red(text): return f"\033[91m{text}\033[0m"
def green(text): return f"\033[92m{text}\033[0m"
def yellow(text): return f"\033[93m{text}\033[0m"


def find_pat() -> str:
    """从 JOIN.md 或环境变量获取 PAT."""
    # 1. 环境变量
    env_pat = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if env_pat:
        return env_pat
    # 2. JOIN.md hex PAT (已移除, 跳过)
    # 3. 报错
    print(red("❌ 未找到 GitHub PAT。设置方法:"))
    print("   export GH_TOKEN='<你的PAT>'")
    sys.exit(1)


def check_file(path: Path) -> list[dict]:
    """全面检查一个文件, 返回错误和警告."""
    results = []
    name = path.name
    content = path.read_text(encoding='utf-8')

    # ── 文件名检查 ──
    if CHINESE_RE.search(name):
        results.append({"type": "error", "msg": f"文件名含中文: {name}"})
    for prefix in BANNED_PREFIXES:
        if name.startswith(prefix):
            results.append({"type": "error", "msg": f"文件名含禁止前缀: {prefix}"})
    stem = path.stem
    if not re.match(r'^[a-z0-9][a-z0-9-]*[a-z0-9]$', stem):
        results.append({"type": "warn", "msg": f"文件名不是 kebab-case: {name}"})

    # ── Frontmatter ──
    m = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
    if not m:
        results.append({"type": "error", "msg": "缺少 frontmatter (---)"})
    else:
        try:
            fm = json.loads(m.group(1))
            for field in ["title", "domain", "status"]:
                if field not in fm:
                    results.append({"type": "error", "msg": f"frontmatter 缺字段: {field}"})
            title = fm.get("title", "")
            if CHINESE_RE.search(title):
                results.append({"type": "warn", "msg": f"标题含中文: {title}"})
        except json.JSONDecodeError as e:
            results.append({"type": "error", "msg": f"frontmatter JSON 解析失败: {e}"})

    # ── 敏感内容检查 ──
    for pattern, desc in SENSITIVE_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE):
            results.append({"type": "error" if "REMOVE" in desc or "PAT" in desc else "warn",
                          "msg": f"敏感内容: {desc}"})

    return results


def deduplicate(path: Path) -> list[str]:
    """去重检查: 标题和内容哈希."""
    warnings = []
    content = path.read_text(encoding='utf-8')
    m = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
    if not m:
        return warnings
    try:
        fm = json.loads(m.group(1))
    except json.JSONDecodeError:
        return warnings

    new_title = fm.get("title", "").lower().strip()
    new_hash = hashlib.md5(content.encode()).hexdigest()

    for f in sorted(CONTRIB.glob("*.md")):
        if f.resolve() == path.resolve():
            continue
        fc = f.read_text(encoding='utf-8')
        m2 = re.match(r'^---\s*\n(.*?)\n---', fc, re.DOTALL)
        if not m2:
            continue
        try:
            fm2 = json.loads(m2.group(1))
        except json.JSONDecodeError:
            continue
        existing_title = fm2.get("title", "").lower().strip()
        existing_hash = hashlib.md5(fc.encode()).hexdigest()

        # 标题相似
        if new_title and existing_title and (
            new_title == existing_title or
            new_title in existing_title or existing_title in new_title
        ):
            warnings.append(f"标题与 {f.name} 相似: '{fm2.get('title')}'")

        # 内容完全相同
        if new_hash == existing_hash:
            warnings.append(f"内容与 {f.name} 完全相同 (重复)")

    return warnings


def auto_sanitize(content: str) -> tuple[str, bool]:
    """自动替换已知敏感模式."""
    changed = False
    for pattern, replacement in AUTO_REPLACE:
        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            changed = True
            content = new_content
    return content, changed


def process_file(filepath: Path, dry_run: bool = False) -> bool:
    """处理单个文件: 检查 → 脱敏 → (可选提交)."""
    print(f"\n{'='*60}")
    print(f"  📄 {filepath.resolve().relative_to(REPO)}")
    print(f"{'='*60}")

    # 1. 检查
    checks = check_file(filepath)
    errors = [c for c in checks if c["type"] == "error"]
    warns = [c for c in checks if c["type"] == "warn"]

    for e in errors:
        print(f"  {red('❌')} {e['msg']}")
    for w in warns:
        print(f"  {yellow('⚠️')} {w['msg']}")

    if errors:
        print(red("\n  ❌ 存在严重问题, 请修复后重试"))
        return False

    # 2. 去重检查
    dups = deduplicate(filepath)
    for d in dups:
        print(f"  {yellow('⚠️')} 可能重复: {d}")

    # 3. 自动脱敏
    content = filepath.read_text(encoding='utf-8')
    sanitized, changed = auto_sanitize(content)
    if changed:
        filepath.write_text(sanitized, encoding='utf-8')
        print(f"  {green('🔧')} 自动脱敏: 替换了硬编码路径/用户名")

    if not warns and not dups and not changed:
        print(f"  {green('✅')} 所有检查通过")

    return True


def commit_and_push(files: list[Path], message: str | None):
    """git add → commit → push."""
    if not files:
        return

    pat = find_pat()
    os.environ["GH_TOKEN"] = pat
    os.environ["GIT_ASKPASS"] = "echo"  # 防止交互式密码提示

    # 设置 git remote 使用 PAT
    remote_url = f"https://ikalus:{pat}@github.com/Ikalus1988/MisakaNet.git"

    # add
    paths = [str(f.resolve().relative_to(REPO)) for f in files]
    subprocess.run(["git", "add", *paths], cwd=REPO, capture_output=True)

    # commit
    if not message:
        names = [f.stem for f in files[:3]]
        msg = f"lesson: {' + '.join(names)}{'...' if len(files)>3 else ''}"
    else:
        msg = message

    result = subprocess.run(
        ["git", "commit", "-s", "-m", msg],
        cwd=REPO, capture_output=True, text=True
    )
    if result.returncode != 0:
        print(yellow(f"  ⚠️ commit 可能无变更: {result.stderr.strip()}"))

    # push (带重试)
    for attempt in range(3):
        # 先 pull rebase
        subprocess.run(["git", "pull", "--rebase", "origin", "main"],
                       cwd=REPO, capture_output=True,
                       env={**os.environ, "GIT_ASKPASS": "echo"})
        # push
        result = subprocess.run(
            ["git", "remote", "set-url", "origin", remote_url,
             "&&", "git", "push", "origin", "main"],
            cwd=REPO, capture_output=True, text=True, shell=True,
            env={**os.environ, "GIT_ASKPASS": "echo"}
        )
        if result.returncode == 0:
            print(green(f"  🚀 推送成功! commit: {msg}"))
            return
        else:
            print(yellow(f"  ⏳ 推送失败 (尝试 {attempt+1}/3): {result.stderr[:100]}"))
    print(red("  ❌ 推送失败, 请手动 git push"))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    target = Path(sys.argv[1])
    message = None
    dry_run = False

    # 解析参数
    args = sys.argv[2:]
    for i, a in enumerate(args):
        if a == "--message" and i+1 < len(args):
            message = args[i+1]
        if a == "--dry-run":
            dry_run = True

    # 收集文件
    if target.is_dir():
        files = sorted(target.glob("*.md"))
        files = [f for f in files if f.name != "index.md" and f.name != "TEMPLATE.md"]
    elif target.is_file() and target.suffix == ".md":
        files = [target]
    else:
        print(red(f"❌ 无效路径: {target}"))
        sys.exit(1)

    print(f"📋 待处理: {len(files)} 个文件\n")

    # 逐个检查
    ok_files = []
    for f in files:
        if process_file(f, dry_run):
            ok_files.append(f)

    # 提交 + 推送
    if ok_files and not dry_run:
        print(f"\n{'='*60}")
        print(f"  🚀 提交 {len(ok_files)} 个文件...")
        commit_and_push(ok_files, message)
    elif dry_run:
        print(f"\n{yellow('⚠️')} dry-run 模式, 未提交")

    # 汇总
    print(f"\n{'='*60}")
    print(f"  总计: {len(files)} 文件, {len(ok_files)} 通过, {len(files)-len(ok_files)} 失败")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
