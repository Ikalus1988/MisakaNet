#!/usr/bin/env python3
"""Build /api/feed.json — static feed of latest lessons, merged PRs, and open challenges.

Usage:
    python3 scripts/build_feed.py

Output: docs/data/feed.json

No token required. GitHub API calls degrade gracefully to empty arrays on failure.
"""
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LESSONS_PATH = REPO_ROOT / "data" / "lessons.json"
OUTPUT_PATH = REPO_ROOT / "docs" / "data" / "feed.json"


def load_recent_lessons(limit: int = 5) -> list[dict]:
    """Load latest lessons from data/lessons.json."""
    try:
        lessons = json.loads(LESSONS_PATH.read_text(encoding="utf-8"))
        # Sort by created/updated timestamp, newest first
        lessons.sort(key=lambda l: l.get("created", l.get("updated", "")), reverse=True)
        items = []
        for lesson in lessons[:limit]:
            items.append({
                "type": "lesson",
                "title": lesson.get("title", ""),
                "url": lesson.get("url", ""),
                "timestamp": lesson.get("created", lesson.get("updated", "")),
                "domain": lesson.get("domain", ""),
                "source": "lessons",
            })
        return items
    except Exception as e:
        print(f"[warn] Failed to load lessons: {e}", file=sys.stderr)
        return []


def load_merged_prs(limit: int = 5) -> list[dict]:
    """Load recent merged PRs via gh CLI. Falls back to empty on failure."""
    try:
        result = subprocess.run(
            ["gh", "api", f"repos/Ikalus1988/MisakaNet/pulls?state=closed&per_page=20&sort=updated&direction=desc",
             "--jq", "[.[] | select(.merged_at != null) | {title: .title, url: .html_url, merged_at: .merged_at}][:5]"],
            capture_output=True, text=True, timeout=15, encoding="utf-8", errors="replace"
        )
        if result.returncode != 0:
            print(f"[warn] gh api failed: {result.stderr[:100]}", file=sys.stderr)
            return []
        prs = json.loads(result.stdout)
        return [{"type": "merged_pr", "title": p["title"], "url": p["url"], "timestamp": p["merged_at"], "source": "github"} for p in prs]
    except Exception as e:
        print(f"[warn] Failed to load merged PRs: {e}", file=sys.stderr)
        return []


def load_challenges(limit: int = 5) -> list[dict]:
    """Load open competition issues via gh CLI. Falls back to empty on failure."""
    try:
        result = subprocess.run(
            ["gh", "api", "repos/Ikalus1988/MisakaNet/issues?labels=status:competition&state=open&per_page=10",
             "--jq", "[.[] | {title: .title, url: .html_url, labels: [.labels[].name], created_at: .created_at}][:5]"],
            capture_output=True, text=True, timeout=15, encoding="utf-8", errors="replace"
        )
        if result.returncode != 0:
            print(f"[warn] gh api failed: {result.stderr[:100]}", file=sys.stderr)
            return []
        issues = json.loads(result.stdout)
        return [{
            "type": "challenge",
            "title": i["title"],
            "url": i["url"],
            "labels": i["labels"],
            "timestamp": i["created_at"],
            "source": "github",
        } for i in issues]
    except Exception as e:
        print(f"[warn] Failed to load challenges: {e}", file=sys.stderr)
        return []


def build_feed() -> dict:
    """Build the complete feed."""
    lessons = load_recent_lessons(5)
    prs = load_merged_prs(5)
    challenges = load_challenges(5)

    items = lessons + prs + challenges
    # Sort by timestamp descending
    items.sort(key=lambda i: i.get("timestamp", ""), reverse=True)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo": "https://github.com/Ikalus1988/MisakaNet",
        "site": "https://misakanet.org",
        "item_count": len(items),
        "items": items,
    }


def main():
    feed = build_feed()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(feed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Feed written to {OUTPUT_PATH}: {feed['item_count']} items")
    print(f"  lessons: {sum(1 for i in feed['items'] if i['type'] == 'lesson')}")
    print(f"  merged_prs: {sum(1 for i in feed['items'] if i['type'] == 'merged_pr')}")
    print(f"  challenges: {sum(1 for i in feed['items'] if i['type'] == 'challenge')}")


if __name__ == "__main__":
    main()
