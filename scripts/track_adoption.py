#!/usr/bin/env python3
"""Track MCP discovery and adoption metrics across distribution channels.

Collects download/view counts from npm, PyPI, GitHub, and correlates
with internal feedback signals. Outputs a weekly summary report.

Usage:
    python scripts/track_adoption.py [--json] [--output report.md]

Channels tracked:
    - npm: @misaka-net/fatal-guard download count
    - PyPI: misakanet download stats
    - GitHub: repo traffic (views, clones, search hits)
    - Internal: feedback entries (search-feedback.jsonl, issues)

Closes #588
"""

import argparse
import json
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

NPM_PACKAGE = "@misaka-net/fatal-guard"
PYPI_PACKAGE = "misakanet"
GITHUB_REPO = "Ikalus1988/MisakaNet"


def fetch_json(url: str, timeout: int = 10) -> dict | None:
    """Fetch JSON from a URL, returning None on failure."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MisakaNet-Adoption-Tracker/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError):
        return None


def get_npm_downloads(package: str) -> dict:
    """Get npm download counts (last day, week, month)."""
    result = {"package": package, "daily": None, "weekly": None, "monthly": None}
    for period, key in [("last-day", "daily"), ("last-week", "weekly"), ("last-month", "monthly")]:
        data = fetch_json(f"https://api.npmjs.org/downloads/point/{period}/{package}")
        if data and "downloads" in data:
            result[key] = data["downloads"]
    return result


def get_pypi_downloads(package: str) -> dict:
    """Get PyPI download stats via pypistats API."""
    result = {"package": package, "daily": None, "weekly": None, "monthly": None}
    data = fetch_json(f"https://pypistats.org/api/packages/{package}/recent")
    if data and "data" in data:
        result["daily"] = data["data"].get("last_day")
        result["weekly"] = data["data"].get("last_week")
        result["monthly"] = data["data"].get("last_month")
    return result


def get_github_traffic(repo: str, token: str | None = None) -> dict:
    """Get GitHub repo traffic (requires token with repo scope)."""
    result = {"repo": repo, "views": None, "unique_visitors": None, "clones": None, "unique_cloners": None}
    headers = {"User-Agent": "MisakaNet-Adoption-Tracker/1.0", "Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"
    for endpoint, count_key, unique_key in [("views", "views", "unique_visitors"), ("clones", "clones", "unique_cloners")]:
        try:
            req = urllib.request.Request(f"https://api.github.com/repos/{repo}/traffic/{endpoint}", headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                result[count_key] = data.get("count")
                result[unique_key] = data.get("uniques")
        except (urllib.error.URLError, urllib.error.HTTPError, OSError):
            pass
    return result


def get_internal_feedback() -> dict:
    """Count internal feedback entries from search-feedback.jsonl."""
    result = {"total_feedback": 0, "by_type": {}, "source": "data/search-feedback.jsonl"}
    feedback_file = REPO_ROOT / "data" / "search-feedback.jsonl"
    if feedback_file.exists():
        for line in feedback_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            result["total_feedback"] += 1
            try:
                entry = json.loads(line)
                ftype = entry.get("type", "unknown")
                result["by_type"][ftype] = result["by_type"].get(ftype, 0) + 1
            except json.JSONDecodeError:
                result["by_type"]["parse_error"] = result["by_type"].get("parse_error", 0) + 1
    return result


def get_github_issues_stats(repo: str) -> dict:
    """Get open issue count as engagement signal."""
    result = {"open_issues": None}
    data = fetch_json(f"https://api.github.com/repos/{repo}")
    if data:
        result["open_issues"] = data.get("open_issues_count")
    return result


def generate_report(metrics: dict, as_json: bool = False) -> str:
    """Generate a human-readable or JSON adoption report."""
    if as_json:
        return json.dumps(metrics, indent=2, ensure_ascii=False)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    npm = metrics["npm"]
    pypi = metrics["pypi"]
    gh = metrics["github"]
    ghi = metrics["github_issues"]
    fb = metrics["feedback"]

    def val(v):
        return v if v is not None else "N/A"

    lines = [
        "# MisakaNet MCP Adoption Report",
        f"**Generated:** {now}",
        "",
        "## Distribution Channel Metrics",
        "",
        "### npm (@misaka-net/fatal-guard)",
        f"- Daily downloads: {val(npm['daily'])}",
        f"- Weekly downloads: {val(npm['weekly'])}",
        f"- Monthly downloads: {val(npm['monthly'])}",
        "",
        "### PyPI (misakanet)",
        f"- Daily downloads: {val(pypi['daily'])}",
        f"- Weekly downloads: {val(pypi['weekly'])}",
        f"- Monthly downloads: {val(pypi['monthly'])}",
        "",
        "### GitHub Traffic",
        f"- Views (14d): {val(gh['views'])}",
        f"- Unique visitors: {val(gh['unique_visitors'])}",
        f"- Clones (14d): {val(gh['clones'])}",
        f"- Unique cloners: {val(gh['unique_cloners'])}",
        f"- Open issues: {val(ghi['open_issues'])}",
        "",
        "## Internal Feedback Signals",
        "",
        f"- Total feedback entries: {fb['total_feedback']}",
    ]
    if fb["by_type"]:
        lines.append("- By type:")
        for ftype, count in sorted(fb["by_type"].items()):
            lines.append(f"  - {ftype}: {count}")

    lines.extend([
        "",
        "## MCP Registry Status",
        "",
        "| Channel | Status | URL |",
        "|---------|--------|-----|",
        "| MCP Registry | Published | io.github.Ikalus1988/misakanet |",
        "| Glama | Indexed | glama.ai/mcp/servers/Ikalus1988/MisakaNet |",
        "| PyPI | Published | pypi.org/project/misakanet |",
        "| Smithery | Not started | - |",
        "",
        "---",
        "*Run weekly: `python scripts/track_adoption.py --output reports/adoption-YYYYMMDD.md`*",
    ])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Track MisakaNet MCP adoption metrics")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--output", "-o", type=str, help="Write report to file")
    parser.add_argument("--github-token", type=str, default=None, help="GitHub token for traffic API")
    args = parser.parse_args()

    print("Collecting adoption metrics...", file=sys.stderr)
    metrics = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "npm": get_npm_downloads(NPM_PACKAGE),
        "pypi": get_pypi_downloads(PYPI_PACKAGE),
        "github": get_github_traffic(GITHUB_REPO, args.github_token),
        "github_issues": get_github_issues_stats(GITHUB_REPO),
        "feedback": get_internal_feedback(),
    }
    report = generate_report(metrics, as_json=args.json)
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report, encoding="utf-8")
        print(f"Report written to {out_path}", file=sys.stderr)
    else:
        print(report)


if __name__ == "__main__":
    main()
