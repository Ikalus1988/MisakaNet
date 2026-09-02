#!/usr/bin/env python3
"""Build an actionable PR Genius report from GitHub pull-request metadata."""

from __future__ import annotations

import argparse
import json
import os
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

try:
    from scripts.pr_genius_rules import (
        build_rule_list,
        evaluate_body_rules,
        evaluate_path_rules,
        get_enabled_rules,
    )
except ImportError:
    from pr_genius_rules import (
        build_rule_list,
        evaluate_body_rules,
        evaluate_path_rules,
        get_enabled_rules,
    )

CODE_SUFFIXES = {
    ".c", ".cc", ".cpp", ".cs", ".go", ".java", ".js", ".jsx", ".kt",
    ".php", ".py", ".rb", ".rs", ".sh", ".swift", ".ts", ".tsx",
}
TEST_PARTS = {"test", "tests", "spec", "specs", "__tests__"}
ISSUE_REFERENCE = re.compile(
    r"(?i)(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+(?:[\w.-]+/[\w.-]+)?#\d+|(?<!\w)#\d+"
)

# ── Config loading ──

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = REPO_ROOT / ".pr-genius.yaml"

_DEFAULT_CONFIG = {
    "rules": {
        "issue_link": {"patterns": [], "required": True},
        "pr_size": {"max_lines": 500, "warning_lines": 300},
        "patterns": {
            "pr_too_large": {"enabled": True, "severity": "high"},
            "missing_tests": {"enabled": True, "severity": "medium"},
            "doc_code_mismatch": {"enabled": True, "severity": "low"},
            "mixed_concerns": {"enabled": True, "severity": "medium"},
            "no_issue_reference": {"enabled": True, "severity": "low"},
            "missing_dco": {"enabled": True, "severity": "medium"},
        },
    }
}


def load_config() -> dict[str, Any]:
    """Load .pr-genius.yaml, falling back to defaults."""
    if not CONFIG_FILE.exists():
        return _DEFAULT_CONFIG
    try:
        import yaml  # optional dependency
        with open(CONFIG_FILE, encoding="utf-8") as f:
            user = yaml.safe_load(f) or {}
    except ImportError:
        # Minimal YAML parser for flat key: value and lists
        print("USING MINIMAL"); user = _parse_yaml_minimal(CONFIG_FILE.read_text(encoding="utf-8"))
    # Merge user config with defaults
    config = _deep_merge(_DEFAULT_CONFIG, user)
    return config


def _parse_yaml_minimal(text: str) -> dict:
    """Minimal YAML parser for .pr-genius.yaml (no dependency)."""
    import re as _re
    result: dict = {}
    stack = [result]
    indent_levels = [-1]
    
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        
        match = _re.match(r'^(\w[\w_]*)\s*:\s*(.*)', stripped)
        if not match:
            continue
            
        key, value = match.group(1), match.group(2).strip().strip('"').strip("'")
        
        if value:
            try:
                value = int(value)
            except ValueError:
                if value.lower() in ("true", "false"):
                    value = value.lower() == "true"
        else:
            value = {}
            
        while indent <= indent_levels[-1] and len(stack) > 1:
            stack.pop()
            indent_levels.pop()
            
        stack[-1][key] = value
        
        if isinstance(value, dict):
            stack.append(value)
            indent_levels.append(indent)
            
    return result


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep merge override into base (override wins)."""
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def is_test(path: str) -> bool:
    parsed = PurePosixPath(path)
    name = parsed.name.lower()
    return bool(
        TEST_PARTS.intersection(part.lower() for part in parsed.parts)
        or name.startswith("test_")
        or ".test." in name
        or ".spec." in name
    )


def is_documentation(path: str) -> bool:
    parsed = PurePosixPath(path)
    return parsed.suffix.lower() in {".md", ".mdx", ".rst"} or bool(
        parsed.parts and parsed.parts[0].lower() in {"doc", "docs"}
    )


def is_code(path: str) -> bool:
    return PurePosixPath(path).suffix.lower() in CODE_SUFFIXES and not is_test(path)


def size_label(total: int) -> str:
    if total <= 100:
        return "small"
    if total <= 500:
        return "medium"
    return "large"


def component(path: str) -> str:
    parts = PurePosixPath(path).parts
    return parts[0] if len(parts) > 1 else "repository root"


def analyze(
    pr: dict[str, Any],
    files: list[dict[str, Any]],
    commits: list[dict[str, Any]],
    checks: list[dict[str, Any]] | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = (config or _DEFAULT_CONFIG).get("rules", {})
    pattern_cfg = cfg.get("patterns", {})
    pr_size_cfg = cfg.get("pr_size", {})
    max_lines = pr_size_cfg.get("max_lines", 500)

    # Build rule list (repo-agnostic + repo-specific)
    rules = build_rule_list(config or _DEFAULT_CONFIG)

    additions = sum(int(item.get("additions", 0)) for item in files)
    deletions = sum(int(item.get("deletions", 0)) for item in files)
    total = additions + deletions
    paths = [str(item.get("filename", "")) for item in files]
    code_paths = [path for path in paths if is_code(path)]
    test_paths = [path for path in paths if is_test(path)]
    doc_paths = [path for path in paths if is_documentation(path)]
    components = sorted({component(path) for path in paths})

    patterns: list[dict[str, str]] = []
    suggestions: list[str] = []

    def _is_enabled(rule_id: str) -> bool:
        return pattern_cfg.get(rule_id, {}).get("enabled", True)

    def _severity(rule_id: str, default: str) -> str:
        return pattern_cfg.get(rule_id, {}).get("severity", default)

    # ── Layer 1: Repo-agnostic core rules ──

    if _is_enabled("pr_too_large") and total > max_lines:
        sev = _severity("pr_too_large", "high")
        patterns.append({"rule": "pr_too_large", "severity": sev})
        suggestions.append(
            f"Split the change into focused PRs of at most {max_lines} changed lines."
        )
    if _is_enabled("missing_tests") and code_paths and not test_paths:
        sev = _severity("missing_tests", "medium")
        patterns.append({"rule": "missing_tests", "severity": sev})
        suggestions.append("Add or update tests for the changed code paths.")
    if _is_enabled("doc_code_mismatch") and doc_paths and not code_paths and not test_paths:
        sev = _severity("doc_code_mismatch", "low")
        patterns.append({"rule": "doc_code_mismatch", "severity": sev})
        suggestions.append(
            "Confirm this documentation-only change intentionally needs no code update."
        )

    concern_groups = set()
    if code_paths:
        concern_groups.add("code")
    if test_paths:
        concern_groups.add("tests")
    if doc_paths:
        concern_groups.add("docs")
    if any(path.startswith(".github/") for path in paths):
        concern_groups.add("automation")
    lock_files = {"package-lock.json", "uv.lock", "poetry.lock"}
    if any(PurePosixPath(path).name.lower() in lock_files for path in paths):
        concern_groups.add("dependencies")
    if _is_enabled("mixed_concerns") and len(concern_groups) >= 3 and len(components) >= 3:
        sev = _severity("mixed_concerns", "medium")
        patterns.append({"rule": "mixed_concerns", "severity": sev})
        suggestions.append(
            "Explain why these components belong together or split unrelated concerns."
        )

    body = str(pr.get("body") or "")
    issue_cfg = cfg.get("issue_link", {})
    custom_issue_patterns = issue_cfg.get("patterns", [])
    issue_matched = ISSUE_REFERENCE.search(body)
    if custom_issue_patterns:
        for pat in custom_issue_patterns:
            if re.search(pat, body):
                issue_matched = True
                break
    issue_required = issue_cfg.get("required", True)
    if _is_enabled("no_issue_reference") and not issue_matched and issue_required:
        sev = _severity("no_issue_reference", "low")
        patterns.append({"rule": "no_issue_reference", "severity": sev})
        suggestions.append("Link the issue this PR closes or explain why no issue is needed.")

    unsigned = []
    for item in commits:
        commit = item.get("commit") or {}
        message = str(commit.get("message") or "")
        if not re.search(r"(?im)^Signed-off-by:\s*.+<[^>]+>\s*$", message):
            unsigned.append(str(item.get("sha", "unknown"))[:7])
    if _is_enabled("missing_dco") and unsigned:
        patterns.append({"rule": "missing_dco", "severity": _severity("missing_dco", "medium")})
        suggestions.append("Sign off every commit with `git commit --signoff`.")

    # Draft PR detection
    if _is_enabled("draft_pr") and pr.get("draft"):
        patterns.append({"rule": "draft_pr", "severity": _severity("draft_pr", "info")})
        suggestions.append("PR is in draft state — mark as ready when it's time for review.")

    # Review staleness (>14 days without approval)
    if _is_enabled("review_stale"):
        created_at = pr.get("created_at", "")
        if created_at:
            try:
                created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                days_open = (now - created).days
                has_approval = any(
                    (c.get("state") or "").upper() == "APPROVED"
                    for c in (pr.get("reviews") or [])
                )
                if days_open > 14 and not has_approval:
                    patterns.append({
                        "rule": "review_stale",
                        "severity": _severity("review_stale", "medium"),
                    })
                    msg = (
                        f"PR has been open {days_open} days without"
                        " approval — ping reviewers or address feedback."
                    )
                    suggestions.append(msg)
            except (ValueError, TypeError):
                pass

    # ── Layer 2: Repo-specific rules ──

    # Path-triggered rules
    path_findings = evaluate_path_rules(rules, paths)
    for finding in path_findings:
        patterns.append({"rule": finding["rule"], "severity": finding["severity"]})
        if finding.get("detail"):
            suggestions.append(finding["detail"])

    # Body/title pattern rules
    title = str(pr.get("title") or "")
    body_findings = evaluate_body_rules(rules, body, title)
    for finding in body_findings:
        patterns.append({"rule": finding["rule"], "severity": finding["severity"]})
        if finding.get("detail"):
            suggestions.append(finding["detail"])

    # ── CI checks ──

    relevant_checks = [
        check for check in (checks or []) if "pr genius" not in str(check.get("name", "")).lower()
    ]
    failed_conclusions = {
        "action_required",
        "cancelled",
        "failure",
        "startup_failure",
        "timed_out",
    }
    if any(check.get("conclusion") in failed_conclusions for check in relevant_checks):
        ci_status, ci_detail = "FAIL", "one or more checks failed"
    elif any(check.get("status") != "completed" for check in relevant_checks):
        ci_status, ci_detail = "PENDING", "checks are still running"
    elif relevant_checks:
        ci_status, ci_detail = "PASS", f"{len(relevant_checks)} check(s) completed"
    else:
        ci_status, ci_detail = "UNKNOWN", "no completed CI checks found"

    checklist = [
        {"name": "ci_passing", "status": ci_status, "detail": ci_detail},
        {
            "name": "dco_signoff",
            "status": "FAIL" if unsigned else "PASS",
            "detail": f"{len(unsigned)} unsigned commit(s)" if unsigned else "all commits signed",
        },
        {
            "name": "tests_updated",
            "status": "PASS" if test_paths or not code_paths else "FAIL",
            "detail": f"{len(test_paths)} test file(s) changed",
        },
        {
            "name": "issue_reference",
            "status": "PASS" if ISSUE_REFERENCE.search(body) else "FAIL",
            "detail": (
                "linked issue found" if ISSUE_REFERENCE.search(body) else "no linked issue found"
            ),
        },
    ]

    if not suggestions:
        suggestions.append("No structural changes suggested; proceed with normal review.")

    return {
        "size": {
            "additions": additions,
            "deletions": deletions,
            "total": total,
            "label": size_label(total),
        },
        "impact": {"files_changed": len(paths), "components": components},
        "checklist": checklist,
        "anti_patterns": patterns,
        "suggestions": suggestions,
        "rules_applied": {
            "core": len(get_enabled_rules(rules, "core")),
            "repo": len(get_enabled_rules(rules, "repo")),
        },
    }


def render(report: dict[str, Any], risk: str) -> str:
    size = report["size"]
    impact = report["impact"]
    components = ", ".join(impact["components"]) or "none"
    rules_applied = report.get("rules_applied", {})
    lines = [
        "## PR Genius Analysis",
        f"- **Risk Level:** {risk or 'unknown'}",
        (
            f"- **PR Size:** +{size['additions']}/-{size['deletions']} "
            f"({size['total']} lines, {size['label']})"
        ),
        f"- **Impact:** {impact['files_changed']} files changed ({components})",
        (
            f"- **Rules:** {rules_applied.get('core', '?')} core"
            f" + {rules_applied.get('repo', '?')} repo-specific"
        ),
        "",
        "### Checklist",
    ]
    for item in report["checklist"]:
        lines.append(f"- **{item['name']} ({item['status']})** — {item['detail']}")
    lines.extend(["", "### Anti-Patterns Detected"])
    if report["anti_patterns"]:
        for item in report["anti_patterns"]:
            lines.append(f"- **{item['rule']}** ({item['severity']})")
    else:
        lines.append("- None detected")
    lines.extend(["", "### Suggestions"])
    lines.extend(f"- {suggestion}" for suggestion in report["suggestions"])
    return "\n".join(lines)


def github_get(url: str, token: str) -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def github_get_all(url: str, token: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    page = 1
    separator = "&" if "?" in url else "?"
    while True:
        batch = github_get(f"{url}{separator}per_page=100&page={page}", token)
        items.extend(batch)
        if len(batch) < 100:
            return items
        page += 1


def github_get_check_runs(url: str, token: str) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    page = 1
    while True:
        response = github_get(f"{url}?per_page=100&page={page}", token)
        batch = response.get("check_runs", [])
        checks.extend(batch)
        if len(batch) < 100:
            return checks
        page += 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", required=True, help="GitHub pull_request event JSON")
    parser.add_argument("--risk", default="unknown")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of Markdown")
    args = parser.parse_args()

    with open(args.event, encoding="utf-8") as handle:
        event = json.load(handle)
    pr = event["pull_request"]
    repository = event["repository"]["full_name"]
    number = pr["number"]
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        raise SystemExit("GITHUB_TOKEN is required")
    base = f"https://api.github.com/repos/{repository}/pulls/{number}"
    files = github_get_all(f"{base}/files", token)
    commits = github_get_all(f"{base}/commits", token)
    checks_url = (
        f"https://api.github.com/repos/{repository}/commits/{pr['head']['sha']}/check-runs"
    )
    checks = github_get_check_runs(checks_url, token)
    config = load_config()
    report = analyze(pr, files, commits, checks, config=config)
    output = json.dumps(report, indent=2) if args.json else render(report, args.risk)
    print(output)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary and not args.json:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write(output + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
