#!/usr/bin/env python3
"""cron 兜底：重试 pending + 哈希扫描。每 10 分钟跑一次。"""

import hashlib, json, subprocess, time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LESSONS_DIR = REPO_ROOT / "lessons"
PENDING_DIR = REPO_ROOT / ".feedback" / "pending"
SKILLS_DIR = Path.home() / ".hermes" / "skills"
HASH_FILE = REPO_ROOT / ".feedback" / "skill_hashes.json"

def git(cmd):
    return subprocess.run(f"git {cmd}", shell=True, cwd=REPO_ROOT,
                          capture_output=True, text=True, timeout=30)

def retry_pending():
    if not PENDING_DIR.exists():
        return
    for f in sorted(PENDING_DIR.glob("*.md")):
        git("pull --ff-only")
        body = f.read_text(encoding="utf-8")
        slug = f.stem.lower().replace("_", "-")[:60]
        (LESSONS_DIR / f"{slug}.md").write_text(body, encoding="utf-8")
        git("add lessons/")
        git(f"commit -m 'lesson: retry pending {f.stem}'")
        r = git("push")
        if r.returncode == 0:
            f.unlink()
        else:
            git("restore lessons/")
            break  # 网络还是不通，等下一个 10 分钟

def scan_skill_hashes():
    old = json.loads(HASH_FILE.read_text()) if HASH_FILE.exists() else {}
    new = {}
    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        sm = skill_dir / "SKILL.md"
        if sm.exists():
            h = hashlib.md5(sm.read_bytes()).hexdigest()
            new[skill_dir.name] = h
            if skill_dir.name not in old or old[skill_dir.name] != h:
                print(f"CHANGED: {skill_dir.name}")
    HASH_FILE.parent.mkdir(parents=True, exist_ok=True)
    HASH_FILE.write_text(json.dumps(new, indent=2))

if __name__ == "__main__":
    retry_pending()
    scan_skill_hashes()
