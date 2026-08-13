#!/usr/bin/env python3
"""bench_orchestrator — Phase B Agent Benchmark Runner.

Feeds tasks/*.json to an LLM Agent, collects responses, and
validates via scripts/verify_task.py.

Usage:
    python3 scripts/bench_orchestrator.py                    # run all tasks
    python3 scripts/bench_orchestrator.py --max-tasks 5      # limit to 5
    python3 scripts/bench_orchestrator.py --agent minimax    # specify agent
    python3 scripts/bench_orchestrator.py --dry-run          # preview only
    python3 scripts/bench_orchestrator.py --seed 42          # deterministic seed
    python3 scripts/bench_orchestrator.py --compare <run_id> # compare with previous run
"""
from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TASKS_DIR = REPO_ROOT / "tasks"
RESULTS_DIR = REPO_ROOT / "bench_results"
HISTORY_DIR = REPO_ROOT / "bench" / "history"

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

def setup_seed(seed: int | None = None) -> int:
    """Set deterministic random seed if provided."""
    if seed is not None:
        random.seed(seed)
        return seed
    return random.randint(1, 10000)

def load_tasks(include_drafts: bool = False) -> list[dict]:
    """Load task index. Optionally include draft lessons as dynamic tasks."""
    tasks = []
    index = TASKS_DIR / "index.json"
    if index.exists():
        tasks = json.loads(index.read_text(encoding="utf-8"))

    if include_drafts:
        drafts_dir = REPO_ROOT / "lessons" / "drafts"
        if drafts_dir.exists():
            for md_file in sorted(drafts_dir.glob("*.md")):
                try:
                    draft = _parse_draft_as_task(md_file)
                    if draft:
                        tasks.append(draft)
                except Exception:
                    continue

    return tasks

def _parse_draft_as_task(md_path: Path) -> dict | None:
    """Parse a draft lesson .md file into a bench task entry."""
    content = md_path.read_text(encoding="utf-8", errors="replace")

    # Extract frontmatter
    fm_match = content.split("---")
    if len(fm_match) < 3:
        return None

    try:
        fm = json.loads(fm_match[1].strip())
    except json.JSONDecodeError:
        return None

    if fm.get("status") != "draft":
        return None

    # Extract problem section
    problem_match = content.split("## Problem")
    problem = ""
    if len(problem_match) > 1:
        problem = problem_match[1].split("##")[0].strip()[:500]

    draft_id = f"draft-{md_path.stem}"
    return {
        "task_id": draft_id,
        "title": fm.get("title", draft_id),
        "domain": fm.get("domain", "general"),
        "problem": problem,
        "solution": "TODO: Agent must provide solution",
        "source": str(md_path.relative_to(REPO_ROOT)),
        "test_cmd": "",
        "draft": True,
        "tombstone_hash": fm.get("tombstone_hash", ""),
    }

def load_task_detail(task_id: str) -> dict:
    """Load task detail. Handles both regular tasks and draft tasks."""
    # Regular task
    path = TASKS_DIR / f"{task_id}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))

    # Draft task (task_id starts with "draft-")
    if task_id.startswith("draft-"):
        md_stem = task_id.replace("draft-", "")
        drafts_dir = REPO_ROOT / "lessons" / "drafts"
        md_path = drafts_dir / f"{md_stem}.md"
        if md_path.exists():
            content = md_path.read_text(encoding="utf-8", errors="replace")
            fm_match = content.split("---")
            fm = json.loads(fm_match[1].strip()) if len(fm_match) >= 3 else {}
            problem_match = content.split("## Problem")
            problem = problem_match[1].split("##")[0].strip()[:500] if len(problem_match) > 1 else ""
            return {
                "task_id": task_id,
                "title": fm.get("title", task_id),
                "domain": fm.get("domain", "general"),
                "problem": problem,
                "solution": "TODO: Agent must provide solution",
                "source": str(md_path.relative_to(REPO_ROOT)),
                "test_cmd": "",
                "draft": True,
            }

    return {}

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
        reply =