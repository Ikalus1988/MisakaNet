#!/usr/bin/env python3
"""Bench Leaderboard Generator — bench_results → 天梯榜数据 + Reputation Card.

读取 bench_results/*.json 聚合各 Agent 的跑分数据，生成：
  1. data/bench_leaderboard.json — 天梯榜数据（供 misakanet.org 渲染）
  2. Reputation Card 文本摘要（每个 Agent 一张）
  3. data/leaderboard_meta.json — 记录当前榜首，用于 #1 变化检测

用法:
    python3 scripts/gen_leaderboard.py               # 全量生成
    python3 scripts/gen_leaderboard.py --dry-run      # 只预览
    python3 scripts/gen_leaderboard.py --top 10       # 前10名
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict

REPO = Path(__file__).resolve().parent.parent
RESULTS_DIR = REPO / "bench_results"
OUTPUT = REPO / "data" / "bench_leaderboard.json"
OUTPUT_DIR = OUTPUT.parent
META_FILE = REPO / "data" / "leaderboard_meta.json"


def load_all_results() -> list[dict]:
    """加载所有 bench 结果文件。"""
    runs = []
    if not RESULTS_DIR.exists():
        return runs

    for f in sorted(RESULTS_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            data["_source_file"] = f.name
            runs.append(data)
        except (json.JSONDecodeError, OSError):
            continue
    return runs


def aggregate_by_agent(runs: list[dict]) -> list[dict]:
    """按 Agent 聚合跑分数据。"""
    agents: dict[str, dict] = defaultdict(lambda: {
        "agent": "",
        "model": "",
        "total_runs": 0,
        "total_tasks": 0,
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "total_api_time": 0.0,
        "best_pass_rate": 0.0,
        "last_run": "",
        "domains": set(),
        "run_ids": [],
    })

    for run in runs:
        agent_key = run.get("agent", "unknown")
        a = agents[agent_key]
        a["agent"] = agent_key
        a["model"] = run.get("model", "?")
        a["total_runs"] += 1
        a["total_tasks"] += run.get("total_tasks", 0)
        a["passed"] += run.get("passed", 0)
        a["failed"] += run.get("failed", 0)
        a["skipped"] += run.get("skipped", 0)
        a["total_api_time"] += run.get("total_api_time", 0)

        # Best pass rate
        total = run.get("total_tasks", 1)
        passed = run.get("passed", 0)
        rate = passed / max(total, 1)
        if rate > a["best_pass_rate"]:
            a["best_pass_rate"] = rate

        # Domains from results
        for r in run.get("results", []):
            domain = r.get("domain", "")
            if domain:
                a["domains"].add(domain)

        ts = run.get("timestamp", "")
        if ts > a["last_run"]:
            a["last_run"] = ts

        a["run_ids"].append(run.get("run_id", "?"))

    # Post-process
    leaderboard = []
    for agent_key, a in agents.items():
        total = a["total_tasks"]
        passed = a["passed"]
        rate = passed / max(total, 1) * 100
        a["pass_rate"] = round(rate, 1)
        a["domains"] = sorted(a["domains"])
        a["run_count"] = len(a["run_ids"])

        # 等价人工价值估算 ($127/lesson, based on Phase A metrics)
        a["equivalent_human_value"] = round(passed * 127.0, 2)

        leaderboard.append(a)

    # 排序：通过数降序
    leaderboard.sort(key=lambda a: (-a["passed"], a["agent"]))
    for rank, a in enumerate(leaderboard, 1):
        a["rank"] = rank

    return leaderboard


def generate_reputation_card(agent: dict) -> str:
    """为单个 Agent 生成 Reputation Card 文本。"""
    return (
        f"🏆 **{agent['agent']}** (model: {agent['model']})\n"
        f"在 MisakaNet 真实故障基准中通过了 **{agent['passed']}/{agent['total_tasks']}** "
        f"项测试 ({agent['pass_rate']}%)，\n"
        f"等价人工修 Bug 价值 **${agent['equivalent_human_value']:,.2f}**，"
        f"当前全网排名 **#{agent['rank']}**。\n"
        f"覆盖领域: {', '.join(agent['domains'][:8])}\n"
        f"最近跑分: {agent['last_run'][:19]}\n"
    )


def load_meta() -> dict:
    """读取 leaderboard_meta.json，记录上次的榜首。"""
    if META_FILE.exists():
        try:
            return json.loads(META_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_meta(meta: dict):
    """原子写入 leaderboard_meta.json。"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    tmp = META_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(META_FILE)


def main():
    dry_run = "--dry-run" in sys.argv
    top_n = None
    for i, arg in enumerate(sys.argv):
        if arg == "--top" and i + 1 < len(sys.argv):
            try:
                top_n = int(sys.argv[i + 1])
            except ValueError:
                pass

    runs = load_all_results()
    if not runs:
        print("⚠️  No bench results found in bench_results/")
        print("   Run: python3 scripts/bench_orchestrator.py --include-drafts")
        return

    leaderboard = aggregate_by_agent(runs)
    if top_n:
        leaderboard = leaderboard[:top_n]

    # 输出天梯榜
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_agents": len(leaderboard),
        "total_runs": len(runs),
        "leaderboard": [],
    }

    for agent in leaderboard:
        entry = {
            "rank": agent["rank"],
            "agent": agent["agent"],
            "model": agent["model"],
            "pass_rate": agent["pass_rate"],
            "passed": agent["passed"],
            "total_tasks": agent["total_tasks"],
            "total_runs": agent["total_runs"],
            "best_pass_rate": round(agent["best_pass_rate"] * 100, 1),
            "total_api_time_s": round(agent["total_api_time"], 2),
            "equivalent_human_value": agent["equivalent_human_value"],
            "domains": agent["domains"],
            "last_run": agent["last_run"],
            "reputation_card": generate_reputation_card(agent),
        }
        output["leaderboard"].append(entry)

    if dry_run:
        print(json.dumps(output, ensure_ascii=False, indent=2)[:3000])
        print(f"\n... ({len(leaderboard)} agents, {len(runs)} runs)")
        return

    # 写入文件
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    # 打印摘要
    print(f"🏆 Bench Leaderboard — {len(leaderboard)} agents, {len(runs)} runs")
    print(f"   {OUTPUT}")
    print()
    for agent in leaderboard[:10]:
        card = f"#{agent['rank']} {agent['agent']} ({agent['model']}): "
        card += f"{agent['passed']}/{agent['total_tasks']} ({agent['pass_rate']}%) "
        card += f"| ${agent['equivalent_human_value']:,.0f}"
        print(f"  {card}")

    if top_n is None and len(leaderboard) > 10:
        print(f"  ... +{len(leaderboard) - 10} more")

    # --- #1 change detection & meta tracking ---
    if leaderboard:
        current_top = leaderboard[0]
        meta = load_meta()
        previous_top_agent = meta.get("top_agent", "")
        previous_top_score = meta.get("top_score", 0)

        if previous_top_agent and previous_top_agent != current_top["agent"]:
            # #1 changed — print notification for caller (leaderboard_watch.py)
            print(f"\n🔔 Leaderboard #1 changed: {previous_top_agent} → {current_top['agent']}")

        meta["top_agent"] = current_top["agent"]
        meta["top_score"] = current_top["passed"]
        meta["updated_at"] = datetime.now(timezone.utc).isoformat()
        meta["total_agents"] = len(leaderboard)
        save_meta(meta)
        print(f"   Meta saved to {META_FILE}")


if __name__ == "__main__":
    main()
