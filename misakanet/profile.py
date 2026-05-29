"""MisakaNet 用户档案 — 阶段管理与推荐链。

三段用户阶段:
    newcomer  →  active  →  contributor
    首次使用       3次搜索       1条 lesson

存储: misakanet/profile.json（git 跟踪，与节点绑定）

推荐链:
    referral_code  < 8 位随机短码
    referred_by    < 推荐节点的 referral_code
"""
import json
import os
import random
import string
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PROFILE_PATH = REPO / "misakanet" / "profile.json"
LESSONS_DIR = REPO / "lessons"

STAGES = ["newcomer", "active", "contributor"]
STAGE_SEARCH_THRESHOLD = 3    # 3 次搜索 → active
STAGE_LESSON_THRESHOLD = 1    # 1 条 lesson → contributor


def _load() -> dict:
    """读取 profile.json，不存在时尝试倒推。"""
    if PROFILE_PATH.exists():
        try:
            return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return _backfill()


def _save(profile: dict):
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROFILE_PATH.write_text(
        json.dumps(profile, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _backfill() -> dict:
    """从 git log / lessons 贡献记录倒推当前阶段。"""
    profile = {
        "stage": "newcomer",
        "referral_code": _generate_code(),
        "referred_by": "",
        "search_count": 0,
        "lesson_count": 0,
        "last_active": datetime.now(timezone.utc).isoformat(),
    }
    # 查 git log 中 lessons/ 下是否有当前用户提交
    try:
        node_id = os.environ.get("MISAKANET_NODE_ID", "")
        if node_id:
            r = subprocess.run(
                ["git", "log", "--author=" + node_id, "--oneline", "--", "lessons/"],
                capture_output=True, text=True, timeout=5, cwd=str(REPO),
            )
            if r.stdout.strip():
                # 有提交记录
                lesson_count = len(r.stdout.strip().split("\n"))
                profile["lesson_count"] = lesson_count
                if lesson_count >= STAGE_LESSON_THRESHOLD:
                    profile["stage"] = "contributor"
                else:
                    profile["stage"] = "active"
    except Exception:
        pass
    _save(profile)
    return profile


def _generate_code(length: int = 8) -> str:
    return "M" + "".join(random.choices(string.ascii_uppercase + string.digits, k=length - 1))


def get_stage() -> str:
    """返回当前阶段字符串。"""
    return _load()["stage"]


def get_referral_code() -> str:
    return _load().get("referral_code", "")


def get_search_count() -> int:
    return _load().get("search_count", 0)


def get_lesson_count() -> int:
    return _load().get("lesson_count", 0)


def increment_search():
    """搜索计数+1，跨阈值时自动升阶段并持久化。"""
    p = _load()
    p["search_count"] = p.get("search_count", 0) + 1
    p["last_active"] = datetime.now(timezone.utc).isoformat()
    if p["stage"] == "newcomer" and p["search_count"] >= STAGE_SEARCH_THRESHOLD:
        p["stage"] = "active"
        print("  🎉 升级: newcomer → active")
        print("  提示: 试试 python3 scripts/new_lesson.py 贡献第一条 lesson")
    _save(p)


def increment_lesson():
    """lesson 计数+1，跨阈值时自动升阶段。"""
    p = _load()
    p["lesson_count"] = p.get("lesson_count", 0) + 1
    p["last_active"] = datetime.now(timezone.utc).isoformat()
    n = p["lesson_count"]
    if p["stage"] == "active" and n >= STAGE_LESSON_THRESHOLD:
        p["stage"] = "contributor"
        print("  🎉 升级: active → contributor")
        print("  提示: 你的 lesson 已进入共享池，影响范围扩大")
    elif n > 0 and n % 5 == 0:
        print(f"  🏆 累计 {n} 条 lesson，节点权重提升")
    _save(p)


def apply_referral(code: str) -> bool:
    """首次注册时填写推荐码。"""
    if not code or len(code) < 4:
        return False
    p = _load()
    if p.get("referred_by"):
        return False  # 已绑定，不可修改
    p["referred_by"] = code.upper()
    _save(p)
    return True


def get_credit_weight() -> float:
    """基于阶段的检索权重加成。"""
    p = _load()
    stage = p.get("stage", "newcomer")
    weights = {"newcomer": 1.0, "active": 1.05, "contributor": 1.10}
    return weights.get(stage, 1.0)
