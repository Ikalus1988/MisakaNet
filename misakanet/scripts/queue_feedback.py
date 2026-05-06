#!/usr/bin/env python3
"""
MisakaNet Queue Feedback (节点侧)
=================================
当前 session 中完成 skill 任务后，调用此脚本将一条待上报记录放入队列。
cron 的 feedback_report.py 会自动扫描队列并发送。

用法:
  # 上报 skill 使用反馈
  python3 misakanet/scripts/queue_feedback.py <skill> <result> <scenario> [--tags ...]

  # 上报节点技能清单变更
  python3 misakanet/scripts/queue_feedback.py sync-inventory \\
    --node node1 --skills "skill-a,skill-b" --removed "old-skill-x"
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

NODE_ID = os.environ.get("MISAKANET_NODE_ID", "node1")


def queue_feedback(skill, result, scenario, tags=None, related=None, session_ref=None):
    """写一条待上报反馈到 pending 队列"""
    valid_results = {"success", "partial", "failure"}
    if result not in valid_results:
        print(f"[error] result 必须是 {valid_results} 之一", file=sys.stderr)
        sys.exit(1)

    script_dir = Path(__file__).parent
    pending_dir = script_dir / ".." / ".feedback" / "pending"
    pending_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    path = pending_dir / f"{ts}_{skill}.json"

    record = {
        "type": "feedback",
        "node_id": NODE_ID,
        "skill": skill,
        "result": result,
        "scenario": scenario,
        "extra": {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if tags:
        record["extra"]["tags"] = [t.strip() for t in tags.split(",") if t.strip()]
    if related:
        record["extra"]["related_skills"] = [s.strip() for s in related.split(",") if s.strip()]
    if session_ref:
        record["extra"]["session_ref"] = session_ref

    path.write_text(json.dumps(record, ensure_ascii=False, indent=2))
    print(f"  feedback queued: {skill} -> {result}")


def sync_inventory(node_id, current_skills, removed_skills=None):
    """上报节点当前的技能清单变更（新增/删除）"""
    script_dir = Path(__file__).parent
    pending_dir = script_dir / ".." / ".feedback" / "pending"
    pending_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    path = pending_dir / f"inventory_{node_id}_{ts}.json"

    record = {
        "type": "inventory",
        "node_id": node_id,
        "skills": current_skills,
        "removed": removed_skills or [],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    path.write_text(json.dumps(record, ensure_ascii=False, indent=2))
    print(f"  inventory queued: {node_id} -> {len(current_skills)} skills, {len(removed_skills or [])} removed")


def main():
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "sync-inventory":
        node = sys.argv[sys.argv.index("--node") + 1] if "--node" in sys.argv else NODE_ID
        skills_str = sys.argv[sys.argv.index("--skills") + 1] if "--skills" in sys.argv else ""
        removed_str = sys.argv[sys.argv.index("--removed") + 1] if "--removed" in sys.argv else ""
        skills = [s.strip() for s in skills_str.split(",") if s.strip()]
        removed = [s.strip() for s in removed_str.split(",") if s.strip()]
        sync_inventory(node, skills, removed)
    else:
        if len(sys.argv) < 4:
            print(__doc__, file=sys.stderr)
            sys.exit(1)
        skill = sys.argv[1]
        result = sys.argv[2]
        scenario = sys.argv[3]
        tags = None
        related = None
        session_ref = None
        i = 4
        while i < len(sys.argv):
            if sys.argv[i] == "--tags" and i + 1 < len(sys.argv):
                tags = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] == "--related" and i + 1 < len(sys.argv):
                related = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] == "--session" and i + 1 < len(sys.argv):
                session_ref = sys.argv[i + 1]
                i += 2
            else:
                print(f"[error] unknown param: {sys.argv[i]}", file=sys.stderr)
                sys.exit(1)
        queue_feedback(skill, result, scenario, tags, related, session_ref)


if __name__ == "__main__":
    main()
