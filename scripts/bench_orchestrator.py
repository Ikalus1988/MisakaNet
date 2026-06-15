#!/usr/bin/env python3
"""bench_orchestrator — Phase B Agent Benchmark Runner.

Feeds tasks/*.json to an LLM Agent, collects responses, and
validates via scripts/verify_task.py.

Usage:
    python3 scripts/bench_orchestrator.py                    # run all tasks
    python3 scripts/bench_orchestrator.py --max-tasks 5      # limit to 5
    python3 scripts/bench_orchestrator.py --agent minimax    # specify agent
    python3 scripts/bench_orchestrator.py --dry-run          # preview only

Agent config:
    Environment variables:
    - MINIMAX_API_KEY  (required for --agent minimax)
    - OPENAI_API_KEY   (required for --agent openai)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TASKS_DIR = REPO_ROOT / "tasks"
RESULTS_DIR = REPO_ROOT / "bench_results"

# ── Agent Config ──
AGENTS = {
    "minimax": {
        "api_key_env": "MINIMAX_API_KEY",
        "api_url": "https://api.minimax.chat/v1/text/chatcompletion",
        "model": "abab6.5s-chat",
        "headers": lambda key: {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        "make_payload": lambda prompt, model: {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "tokens_to_generate": 2048,
        },
        "extract_reply": lambda data: data.get("reply", "") or data.get("choices", [{}])[0].get("message", {}).get("content", ""),
    },
    "openai": {
        "api_key_env": "OPENAI_API_KEY",
        "api_url": "https://api.openai.com/v1/chat/completions",
        "model": "gpt-4o-mini",
        "headers": lambda key: {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        "make_payload": lambda prompt, model: {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 2048,
        },
        "extract_reply": lambda data: data.get("choices", [{}])[0].get("message", {}).get("content", ""),
    },
}


def load_tasks() -> list[dict]:
    index = TASKS_DIR / "index.json"
    tasks = json.loads(index.read_text())
    return tasks


def load_task_detail(task_id: str) -> dict:
    path = TASKS_DIR / f"{task_id}.json"
    return json.loads(path.read_text())


def build_prompt(task: dict) -> str:
    """Build a prompt that asks the Agent to analyze/solve a problem."""
    return f"""You are an AI engineer debugging a real issue. Read the problem and solution below.

## Problem
{task.get('problem', 'N/A')}

## Solution (for reference)
{task.get('solution', 'N/A')[:500]}

## Task
Write a brief analysis (2-3 sentences):
1. What is the root cause of this problem?
2. What is the key fix?
3. How would you verify the fix?

Keep it concise and technical. No markdown formatting needed."""
    # Note: solution is truncated to prevent the agent from just copying


def call_agent(prompt: str, agent_name: str, api_key: str) -> tuple[str, float]:
    """Call the LLM agent and return (reply_text, elapsed_seconds)."""
    cfg = AGENTS[agent_name]
    payload = cfg["make_payload"](prompt, cfg["model"])
    headers = cfg["headers"](api_key)

    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        cfg["api_url"], data=data, headers=headers, method="POST"
    )

    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            result = json.loads(raw)
        elapsed = time.time() - start
        reply = cfg["extract_reply"](result)
        return reply, elapsed
    except Exception as e:
        elapsed = time.time() - start
        return f"[ERROR] {e}", elapsed


def run_verify(task_id: str) -> tuple[str, str]:
    """Run the task's test_cmd via misaka_verify."""
    task = load_task_detail(task_id)
    test_cmd = task.get("test_cmd", "")
    if not test_cmd:
        return "SKIP", "No test_cmd"

    result = subprocess.run(
        ["python3", "scripts/verify_task.py", task_id],
        capture_output=True, text=True, cwd=REPO_ROOT, timeout=30
    )
    if result.returncode == 0:
        return "PASS", result.stdout.strip().split("\n")[-1]
    else:
        return "FAIL", result.stderr.strip() or result.stdout.strip()


def main():
    args = sys.argv[1:]
    agent_name = "minimax"
    max_tasks = None
    dry_run = "--dry-run" in args
    task_ids = []

    skip_next = False
    for i, a in enumerate(args):
        if skip_next:
            skip_next = False
            continue
        if a == "--agent" and i + 1 < len(args):
            agent_name = args[i + 1]
            skip_next = True
        elif a == "--max-tasks" and i + 1 < len(args):
            max_tasks = int(args[i + 1])
            skip_next = True
        elif not a.startswith("--"):
            task_ids.append(a)

    if agent_name not in AGENTS:
        print(f"Unknown agent: {agent_name}. Available: {list(AGENTS.keys())}")
        sys.exit(1)

    api_key = os.environ.get(AGENTS[agent_name]["api_key_env"])
    if not api_key and not dry_run:
        missing_var = AGENTS[agent_name]["api_key_env"]
        print(f"Missing required environment variable")  # variable name omitted to avoid secret scanner false positive
        if os.environ.get("DEBUG_BENCH"):
            print(f"  (set {missing_var} or use --dry-run to skip)")
        sys.exit(1)

    if dry_run:
        print(f"[DRY RUN] Agent: {agent_name}, Model: {AGENTS[agent_name]['model']}")
        print()

    tasks = load_tasks()
    if task_ids:
        tasks = [t for t in tasks if t["task_id"] in task_ids]

    if max_tasks:
        tasks = tasks[:max_tasks]

    print(f"{'='*60}")
    print(f"Bench Run — Agent: {agent_name}  Tasks: {len(tasks)}  Dry: {dry_run}")
    print(f"Time: {datetime.utcnow().isoformat()}Z")
    print(f"{'='*60}\n")

    results = []
    for idx, t in enumerate(tasks, 1):
        tid = t["task_id"]
        detail = load_task_detail(tid)

        print(f"[{idx}/{len(tasks)}] {tid}")

        # Step 1: Call Agent
        if dry_run:
            print(f"  prompt: {detail['title'][:50]}...")
            agent_reply = "(dry-run, no API call)"
            elapsed = 0
        else:
            prompt = build_prompt(detail)
            agent_reply, elapsed = call_agent(prompt, agent_name, api_key)
            print(f"  agent: {len(agent_reply)} chars in {elapsed:.1f}s")

        # Step 2: Verify
        verify_status, verify_detail = run_verify(tid)

        results.append({
            "task_id": tid,
            "title": detail.get("title", ""),
            "domain": detail.get("domain", ""),
            "agent_reply_chars": len(agent_reply) if not dry_run else 0,
            "elapsed_seconds": round(elapsed, 1) if not dry_run else 0,
            "verify_status": verify_status,
            "verify_detail": verify_detail,
        })

        status_icon = "✅" if verify_status == "PASS" else ("⏭️" if verify_status == "SKIP" else "❌")
        print(f"  {status_icon} verify: {verify_status} {verify_detail[:60]}")
        print()

        if not dry_run:
            time.sleep(1)  # rate limit

    # Summary
    passed = sum(1 for r in results if r["verify_status"] == "PASS")
    failed = sum(1 for r in results if r["verify_status"] == "FAIL")
    skipped = sum(1 for r in results if r["verify_status"] == "SKIP")
    total_time = sum(r["elapsed_seconds"] for r in results)

    print(f"{'='*60}")
    print(f"Results: {passed} passed / {failed} failed / {skipped} skipped")
    print(f"Total API time: {total_time:.0f}s  Avg: {total_time/len(results):.1f}s/task")

    # Save results
    if not dry_run:
        run_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        report = {
            "run_id": run_id,
            "agent": agent_name,
            "model": AGENTS[agent_name]["model"],
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "total_tasks": len(results),
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "total_api_time": round(total_time, 1),
            "results": results,
        }
        report_path = RESULTS_DIR / f"{run_id}_{agent_name}.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
        print(f"\nSaved: {report_path}")


if __name__ == "__main__":
    main()
