import os
import json
import requests

# Import missing constants from the JS handler equivalents (converted to a Python module)
try:
    from workers.lib.handlers import GITHUB_API, REPO, PUBLIC_DATA_BASE
except Exception:
    # Fallback to environment variables if import fails
    GITHUB_API = os.getenv("GITHUB_API", "https://api.github.com")
    REPO = os.getenv("REPO", "Ikalus1988/MisakaNet")
    PUBLIC_DATA_BASE = os.getenv("PUBLIC_DATA_BASE", "https://misakanet.org/data")


def misakanet_submit_intake(problem: str, source: str = "unknown"):
    """Submit a failure case to the MCP intake system."""
    url = f"{GITHUB_API}/repos/{REPO}/issues"
    headers = {"Accept": "application/vnd.github+json"}
    payload = {
        "title": f"MCP Intake: {problem[:50]}",
        "body": f"**Source:** {source}\n\n{problem}",
        "labels": ["mcp-intake", "auto-generated"]
    }
    response = requests.post(url, headers=headers, data=json.dumps(payload))
    response.raise_for_status()
    issue = response.json()
    return {
        "submitted": True,
        "intake_id": f"issue-{issue.get('number')}",
        "status": "pending_review",
        "issue_url": issue.get("html_url"),
        "receipt": f"GitHub issue {issue.get('number')} created. No account or email required."
    }