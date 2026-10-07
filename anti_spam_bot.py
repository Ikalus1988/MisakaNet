import os
import requests
import time
from typing import List, Dict, Optional

REPO_OWNER = "Ikalus1988"
REPO_NAME = "MisakaNet"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

# Known spam bot account that dominates issue comments with identical template
SPAM_ACCOUNTS = {"onlymrneo"}

# Template signature to detect automated claim spam
SPAM_TEMPLATE_PATTERNS = [
    "Autonomous Agent Solution Claim",
    "Bitcoin Payout Wallet",
    "/opire try",
]

SPAM_DELETE_LIMIT_PER_RUN = 50


def get_github_headers() -> Dict[str, str]:
    return {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def api_get(path: str) -> list | dict:
    """GET a GitHub API path, returns parsed JSON."""
    url = f"https://api.github.com{path}"
    resp = requests.get(url, headers=get_github_headers(), timeout=30)
    resp.raise_for_status()
    return resp.json()


def api_patch(path: str, body: dict) -> dict:
    """PATCH a GitHub API path, returns parsed JSON."""
    url = f"https://api.github.com{path}"
    resp = requests.patch(url, json=body, headers=get_github_headers(), timeout=30)
    resp.raise_for_status()
    return resp.json()


def lock_issue(issue_number: int) -> bool:
    """Lock an issue so no further comments can be posted."""
    path = f"/repos/{REPO_OWNER}/{REPO_NAME}/issues/{issue_number}"
    api_patch(path, {"locked": True})
    print(f"[LOCK] Locked issue #{issue_number}")
    return True


def delete_comment(comment_id: int) -> bool:
    """Delete a spam comment."""
    path = f"/repos/{REPO_OWNER}/{REPO_NAME}/issues/comments/{comment_id}"
    api_patch(path, {"body": ""})
    try:
        requests.delete(
            f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/issues/comments/{comment_id}",
            headers=get_github_headers(),
            timeout=30,
        )
        print(f"[DELETE] Deleted spam comment id={comment_id}")
        return True
    except requests.HTTPError as e:
        print(f"[ERROR] Failed to delete comment {comment_id}: {e}")
        return False


def is_spam_comment(body: str, author: str) -> bool:
    """Return True if the comment looks like automated spam."""
    if author in SPAM_ACCOUNTS:
        # High-confidence: any comment from known spam account is spam
        return True
    for pattern in SPAM_TEMPLATE_PATTERNS:
        if pattern in body:
            return True
    return False


def get_all_issues(
    state: str = "all", sort: str = "created", direction: str = "desc"
) -> List[Dict]:
    """Paginate through all issues of the repo."""
    issues = []
    page = 1
    while True:
        params = {
            "state": state,
            "sort": sort,
            "direction": direction,
            "per_page": 100,
            "page": page,
        }
        raw = api_get(f"/repos/{REPO_OWNER}/{REPO_NAME}/issues", params=params)
        if not raw:
            break
        issues.extend(raw)
        page += 1
    return issues


def get_issue_comments(issue_number: int) -> List[Dict]:
    """Get all comments for a given issue (paginated)."""
    comments = []
    page = 1
    while True:
        params = {"per_page": 100, "page": page}
        raw = api_get(
            f"/repos/{REPO_OWNER}/{REPO_NAME}/issues/{issue_number}/comments",
            params=params,
        )
        if not raw:
            break
        comments.extend(raw)
        page += 1
    return comments


def process_issue(issue_number: int) -> Dict[str, int]:
    """Process a single issue: lock if needed and delete spam comments."""
    result = {"deleted": 0, "locked": False}
    try:
        issue_info = api_get(
            f"/repos/{REPO_OWNER}/{REPO_NAME}/issues/{issue_number}"
        )
        if issue_info.get("locked"):
            # Already locked, skip
            return result

        comments = get_issue_comments(issue_number)
        spam_comments = [c for c in comments if is_spam_comment(c["body"], c["user"]["login"])]

        if len(comments) > 50 or len(spam_comments) > 20:
            # Issue is under attack — lock it immediately to stop further noise
            lock_issue(issue_number)
            result["locked"] = True

        # Delete spam comments (respect rate limit)
        deleted = 0
        for comment in spam_comments[:SPAM_DELETE_LIMIT_PER_RUN]:
            if delete_comment(comment["id"]):
                deleted += 1

        result["deleted"] = deleted
        return result

    except Exception as e:
        print(f"[ERROR] Failed to process issue #{issue_number}: {e}")
        return result


def main():
    if not GITHUB_TOKEN:
        raise RuntimeError("GITHUB_TOKEN environment variable is required")

    print("=" * 60)
    print("MisakaNet Anti-Spam Bot - Starting")
    print("=" * 60)

    all_issues = get_all_issues(state="all")
    print(f"Found {len(all_issues)} total issues to scan")

    total_deleted = 0
    total_locked = 0

    for issue in all_issues:
        number = issue["number"]
        # Skip PRs (GitHub counts them as issues too)
        if "pull_request" in issue:
            continue

        result = process_issue(number)
        total_deleted += result["deleted"]
        total_locked += 1 if result["locked"] else 0

        if result["deleted"] > 0 or result["locked"]:
            print(
                f"  Issue #{number}: locked={result['locked']}, deleted={result['deleted']}"
            )

        # Gentle rate limiting
        time.sleep(1)

    print("=" * 60)
    print(f"Done. Total deleted: {total_deleted}, Total locked: {total_locked}")
    print("=" * 60)


if __name__ == "__main__":
    main()
>>>ENDFILE<<<
