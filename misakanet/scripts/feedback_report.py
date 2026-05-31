#!/usr/bin/env python3
"""
MisakaNet Feedback Reporter (节点侧)
=====================================
收集近期 skill 使用记录，通过 GitHub Issues 上报到 Hub。

运行方式:
  1. 手动: python3 /path/to/Agent-Medici/misakanet/scripts/feedback_report.py
  2. Cron: */5 * * * * python3 /path/to/Agent-Medici/misakanet/scripts/feedback_report.py

依赖: curl + GitHub token（从 ~/.git-credentials 读取）
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from misakanet.core.fetch import FetchError, fetch_json  # noqa: E402

REPO = "Ikalus1988/MisakaNet"
NODE_ID = os.environ.get("MISAKANET_NODE_ID", "hermes_wsl2")
GIT_CREDS_PATH = os.path.expanduser("~/.git-credentials")

# 去重状态文件：记录已上报的 (session_ref, skill) 组合
STATE_DIR = Path(__file__).parent / ".." / ".feedback" / NODE_ID
STATE_FILE = STATE_DIR / ".reported_state.json"


def _load_state():
    """读取已上报记录"""
    try:
        if STATE_FILE.exists():
            return json.loads(STATE_FILE.read_text())
    except Exception:
        pass
    return {}


def _save_state(state):
    """持久化已上报记录"""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def _is_already_reported(skill, session_ref):
    """检查是否已上报过"""
    state = _load_state()
    key = f"{session_ref}:{skill}" if session_ref else skill
    return key in state


def _mark_reported(skill, session_ref):
    """标记为已上报"""
    state = _load_state()
    key = f"{session_ref}:{skill}" if session_ref else skill
    state[key] = datetime.now(timezone.utc).isoformat()
    _save_state(state)


def _get_token():
    """从 git credentials 安全获取 GitHub token"""
    import subprocess as _sp
    # 优先用 git credential fill（不暴露在进程列表）
    try:
        result = _sp.run(
            ["git", "credential", "fill"],
            input="protocol=https\nhost=github.com\n",
            capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.split("\n"):
            if line.startswith("password="):
                return line.split("=", 1)[1].strip()
    except Exception:
        pass
    # 降级：直接从文件读（使用 with 确保关闭）
    try:
        with open(GIT_CREDS_PATH, 'r') as f:
            creds = f.read().strip()
        return creds.split("://")[1].split("@")[0].split(":")[1]
    except Exception as e:
        print(f"[error] 无法读取 token ({GIT_CREDS_PATH}): {e}", file=sys.stderr)
        return None


def create_feedback_issue(skill, result, scenario, tags=None, related_skills=None, session_ref=None):
    """上报一条 skill 使用反馈 (创建 GitHub Issue)"""

    # 去重：同一 session + skill 不重复上报
    if _is_already_reported(skill, session_ref):
        print(f"  [skip] {skill} (session={session_ref}) 已上报过")
        return None

    token = _get_token()
    if not token:
        return None

    result_icon = {"success": "✓", "partial": "⚠", "failure": "✗"}
    title = f"feedback: {skill} {result_icon.get(result, '?')}"

    extra = {}
    if tags:
        extra["tags"] = tags
    if related_skills:
        extra["related_skills"] = related_skills
    if session_ref:
        extra["session_ref"] = session_ref

    body = json.dumps({
        "node_id": NODE_ID,
        "skill": skill,
        "result": result,
        "scenario": scenario,
        "extra": extra,
    }, ensure_ascii=False)

    labels = [
        "feedback",
        "unprocessed",
        f"node:{NODE_ID}",
        f"skill:{skill}",
    ]

    payload = json.dumps({
        "title": title,
        "body": body,
        "labels": labels,
    })

    print(f"[上报] {skill} → {result}")
    print(f"  scenario: {scenario[:80]}...")

    # 用 Python requests 代替 curl（避免 token 在进程列表中泄漏）
    import urllib.request as _ur
    req = _ur.Request(
        f"https://api.github.com/repos/{REPO}/issues",
        data=payload.encode('utf-8'),
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "MisakaNet-Node",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        resp_data = fetch_json(req, timeout=20)
        if "number" in resp_data:
            url = resp_data["html_url"]
            print(f"  Issue #{resp_data['number']}: {url}")
            _write_local_cache(skill, result, scenario, extra, url)
            _mark_reported(skill, session_ref)
            return url
        print("  [error] feedback issue response did not include a number", file=sys.stderr)
        return None
    except FetchError as e:
        print(f"  Network request failed cleanly: {e}", file=sys.stderr)
        return None
    except json.JSONDecodeError as e:
        print(f"  API response was not valid JSON: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  feedback issue request failed: {e}", file=sys.stderr)
        return None


def _write_local_cache(skill, result, scenario, extra, issue_url):
    """Write a local .feedback/ backup record."""
    script_dir = Path(__file__).parent
    feedback_dir = script_dir / ".." / ".feedback" / NODE_ID
    feedback_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = feedback_dir / f"{ts}_{skill}.json"

    record = {
        "node_id": NODE_ID,
        "skill": skill,
        "result": result,
        "scenario": scenario,
        "extra": extra,
        "issue_url": issue_url,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    print(f"  cached: {path}")


PENDING_DIR = Path(__file__).parent / ".." / ".feedback" / "pending"


def _create_inventory_issue(node_id, skills, removed):
    """Create an inventory change issue."""
    token = _get_token()
    if not token:
        return None

    title = f"inventory: {node_id} - {len(skills)} skills"

    body = json.dumps({
        "type": "inventory",
        "node_id": node_id,
        "skills": skills,
        "removed": removed,
    }, ensure_ascii=False)

    labels = ["feedback", "inventory", f"node:{node_id}"]

    payload = json.dumps({"title": title, "body": body, "labels": labels})
    import urllib.request as _ur2
    req = _ur2.Request(
        f"https://api.github.com/repos/{REPO}/issues",
        data=payload.encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "MisakaNet-Node",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        resp_data = fetch_json(req, timeout=20)
        if "number" in resp_data:
            print(f"  inventory Issue #{resp_data['number']}: {resp_data['html_url']}")
            return resp_data["html_url"]
        print("  [error] inventory issue response did not include a number", file=sys.stderr)
        return None
    except FetchError as e:
        print(f"  Network request failed cleanly: {e}", file=sys.stderr)
        return None
    except json.JSONDecodeError as e:
        print(f"  API response was not valid JSON: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  inventory issue request failed: {e}", file=sys.stderr)
        return None


def _was_recently_reported(skill, result, cooldown_minutes=60):
    """检查同一 skill+result 在最近 cooldown_minutes 内是否已上报"""
    feedback_dir = Path(__file__).parent / ".." / ".feedback" / NODE_ID
    if not feedback_dir.exists():
        return False

    now = datetime.now(timezone.utc)
    for f in sorted(feedback_dir.glob("*.json"), reverse=True):
        try:
            data = json.loads(f.read_text())
            if data.get("skill") == skill and data.get("result") == result:
                ts = datetime.fromisoformat(data["timestamp"])
                delta = (now - ts).total_seconds()
                if delta < cooldown_minutes * 60:
                    return True
        except (json.JSONDecodeError, KeyError, ValueError):
            continue
    return False


def collect_pending():
    """
    从 pending 队列读取待上报记录，去重后返回。
    """
    if not PENDING_DIR.exists():
        return []

    records = []
    for f in sorted(PENDING_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text())
            record_type = data.get("type", "feedback")

            if record_type == "inventory":
                # 清单变更记录：直接上报，不经过 feedback 去重
                records.append({
                    "type": "inventory",
                    "node_id": data.get("node_id", "unknown"),
                    "skills": data.get("skills", []),
                    "removed": data.get("removed", []),
                    "_file": f,
                })
                continue

            skill = data.get("skill", "")
            result = data.get("result", "")

            if not skill or result not in ("success", "partial", "failure"):
                print(f"  [skip] 无效记录: {f.name}")
                continue

            if _was_recently_reported(skill, result):
                print(f"  [skip] {skill} — 最近已上报: {f.name}")
                f.unlink(missing_ok=True)
                continue

            records.append({
                "type": "feedback",
                "skill": skill,
                "result": result,
                "scenario": data.get("scenario", ""),
                "tags": data.get("extra", {}).get("tags"),
                "related_skills": data.get("extra", {}).get("related_skills"),
                "session_ref": data.get("extra", {}).get("session_ref"),
                "_file": f,
            })

        except (json.JSONDecodeError, KeyError) as e:
            print(f"  [skip] 解析失败: {f.name}: {e}")

    return records


def main():
    print(f"=== MisakaNet Feedback Reporter (node: {NODE_ID}) ===")

    token = _get_token()
    if not token:
        sys.exit(1)

    # 验证 token
    proc = subprocess.run(
        ["curl", "-s", "https://api.github.com/user",
         "-H", f"Authorization: Bearer {token}"],
        capture_output=True, text=True, timeout=10,
    )
    user = json.loads(proc.stdout) if proc.stdout else {}
    if "login" in user:
        print(f"  GitHub: @{user['login']} (token OK)")
    else:
        print(f"[error] Token 无效: {user.get('message', 'unknown')}", file=sys.stderr)
        sys.exit(1)

    # 检查 repo 可访问
    proc = subprocess.run(
        ["curl", "-s", f"https://api.github.com/repos/{REPO}",
         "-H", f"Authorization: Bearer {token}"],
        capture_output=True, text=True, timeout=10,
    )
    repo = json.loads(proc.stdout) if proc.stdout else {}
    if "full_name" in repo:
        print(f"  Repo: {repo['full_name']} (OK)")
    else:
        print(f"[error] 无法访问仓库: {repo.get('message', 'unknown')}", file=sys.stderr)
        sys.exit(1)

    # 上报 pending 队列中的使用记录
    records = collect_pending()
    archive_dir = Path(__file__).parent / ".." / ".feedback" / NODE_ID
    archive_dir.mkdir(parents=True, exist_ok=True)

    for r in records:
        pending_file = r.pop("_file", None)
        rtype = r.get("type", "feedback")

        if rtype == "inventory":
            url = _create_inventory_issue(r["node_id"], r["skills"], r["removed"])
        else:
            url = create_feedback_issue(**r)

        if url and pending_file and pending_file.exists():
            pending_file.rename(archive_dir / pending_file.name)
            print(f"  → 已归档: {pending_file.name}")

    print("=== done ===")


if __name__ == "__main__":
    main()
