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
PROTOCOL_PATH = REPO / "misaka-protocol.json"

STAGES = ["newcomer", "active", "contributor"]
STAGE_SEARCH_THRESHOLD = 3    # 3 次搜索 → active
STAGE_LESSON_THRESHOLD = 1    # 1 条 lesson → contributor


def _load_protocol() -> dict:
    """Load trust tier definitions from misaka-protocol.json."""
    if PROTOCOL_PATH.exists():
        try:
            return json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


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


def get_trust_tier() -> str:
    """Return the trust tier name from profile, defaulting to 'anonymous'."""
    p = _load()
    return p.get("trust_tier", "anonymous")


def get_trust_tier_config(tier_name: str = None) -> dict:
    """Read trust tier config from misaka-protocol.json.
    
    Args:
        tier_name: Tier name to look up. If None, uses current profile's tier.
    
    Returns:
        Dict with method, trust_level, requires_verification, badge_display, search_ranking_boost.
        Falls back to anonymous tier defaults if not found.
    """
    protocol = _load_protocol()
    trust_tiers = protocol.get("trust_tiers", {})
    
    if tier_name is None:
        tier_name = get_trust_tier()
    
    default = {
        "method": "none",
        "trust_level": "unverified",
        "requires_verification": False,
        "badge_display": "👤",
        "search_ranking_boost": 1.0
    }
    
    return trust_tiers.get(tier_name, default)


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
    """lesson 计数+1，跨阈值时自动升阶段，同时重置搜索配额。"""
    p = _load()
    p["lesson_count"] = p.get("lesson_count", 0) + 1
    p["last_active"] = datetime.now(timezone.utc).isoformat()
    n = p["lesson_count"]
    if p["stage"] == "active" and n >= STAGE_LESSON_THRESHOLD:
        p["stage"] = "contributor"
        print("  升级: active -> contributor")
        print("  提示: 你的 lesson 已进入共享池，影响范围扩大")
    elif n > 0 and n % 5 == 0:
        print(f"  累计 {n} 条 lesson，节点权重提升")
    _save(p)
    # 贡献 lesson 自动重置搜索配额
    reset_quota()


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
    """基于阶段的检索权重加成，读取 trust_tiers 配置。"""
    p = _load()
    stage = p.get("stage", "newcomer")
    stage_weights = {"newcomer": 1.0, "active": 1.05, "contributor": 1.10}
    stage_weight = stage_weights.get(stage, 1.0)
    
    # Apply trust tier boost from protocol config
    tier_config = get_trust_tier_config()
    trust_boost = tier_config.get("search_ranking_boost", 1.0)
    
    return stage_weight * trust_boost


# ── 轻量配额制 (Proof of Access lite) ──
# 新节点默认 5 次免费搜索，用完后引导贡献。
# 存储: misakanet/.quota.json（gitignore 未跟踪，每 clone 独立）
# 有 lesson 贡献的节点不受配额限制。

FREE_SEARCH_QUOTA = 5
_QUOTA_PATH = REPO / "misakanet" / ".quota.json"


def _load_quota() -> dict:
    """读取配额文件，不存在时创建初始配额。"""
    if _QUOTA_PATH.exists():
        try:
            return json.loads(_QUOTA_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    # 新节点：满额配额
    quota = {"search_count": 0, "quota_max": FREE_SEARCH_QUOTA}
    _save_quota(quota)
    return quota


def _save_quota(quota: dict):
    _QUOTA_PATH.parent.mkdir(parents=True, exist_ok=True)
    _QUOTA_PATH.write_text(
        json.dumps(quota, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def check_quota() -> tuple:
    """检查当前节点是否还有搜索配额。

    Returns:
        (allowed: bool, reason: str) — True 允许搜索，False 配额用尽
    """
    # 有 lesson 贡献的节点不受配额限制
    lesson_count = get_lesson_count()
    if lesson_count > 0:
        return True, ""

    q = _load_quota()
    used = q.get("search_count", 0)
    remaining = FREE_SEARCH_QUOTA - used

    if remaining <= 0:
        return (
            False,
            f"[MisakaNet] 搜索额度已用尽 ({FREE_SEARCH_QUOTA}/{FREE_SEARCH_QUOTA})。\n"
            f"    贡献 1 条 lesson 即可恢复额度：\n"
            f"    python3 scripts/queue_lesson.py -t '标题' -d <domain> '...'",
        )
    if remaining <= 2:
        return (
            True,
            f"[MisakaNet] 搜索额度剩余 {remaining}/{FREE_SEARCH_QUOTA}。\n"
            f"    额度用完后需贡献 lesson 来恢复。",
        )
    return True, ""


def consume_quota():
    """消耗 1 次搜索配额。搜索成功后调用。"""
    q = _load_quota()
    q["search_count"] = q.get("search_count", 0) + 1
    _save_quota(q)


def reset_quota():
    """重置搜索配额 — lesson 贡献后调用。"""
    q = {"search_count": 0, "quota_max": FREE_SEARCH_QUOTA}
    _save_quota(q)
    print("[MisakaNet] 搜索额度已重置（感谢贡献！）")
