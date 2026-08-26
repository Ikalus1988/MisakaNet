import os
import json
import requests
from workers.lib.handlers import GITHUB_API, REPO, PUBLIC_DATA_BASE

def submit_intake(problem: str, source: str = "unknown"):
    if not GITHUB_API:
        raise RuntimeError("GITHUB_API is not defined")
    if not REPO:
        raise RuntimeError("REPO is not defined")
    if not PUBLIC_DATA_BASE:
        raise RuntimeError("PUBLIC_DATA_BASE is not defined")

    payload = {
        "title": f"MCP Intake: {problem[:50]}",
        "body": f"Source: {source}\n\nProblem:\n{problem}",
    }
    headers = {
        "Authorization": f"token {GITHUB_API}",
        "Accept": "application/vnd.github+json",
    }
    response = requests.post(
        f"https://api.github.com/repos/{REPO}/issues",
        headers=headers,
        data=json.dumps(payload),
    )
    response.raise_for_status()
    issue = response.json()
    receipt = f"GitHub issue {issue['number']} created. No account or email required."
    return {
        "submitted": True,
        "intake_id": f"issue-{issue['number']}",
        "status": "pending_review",
        "issue_url": issue["html_url"],
        "receipt": receipt,
    }

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python misakanet_submit_intake.py <problem>")
        sys.exit(1)
    problem_text = sys.argv[1]
    result = submit_intake(problem_text, source="cli")
    print(json.dumps(result, ensure_ascii=False, indent=2))