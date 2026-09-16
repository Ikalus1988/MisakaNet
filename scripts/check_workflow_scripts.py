#!/usr/bin/env python3
"""
Check workflow shell scripts for common pitfalls (W1-W5).

W1-yaml      : YAML fails to parse (yaml.safe_load)
W2-gh-token  : `gh` used without GH_TOKEN/GITHUB_TOKEN env and without permissions: issues: write
W3-gh-stderr : `gh` without stderr redirect (2>/dev/null or 2>&1)
W4-backtick  : backtick command substitution in run:
W5-date-quote: $(date ...) with unquoted %H:%M etc.

Output format: file:line: RULE message
Exit 0 = no findings, 1 = findings. <10s, no secrets.
"""
import sys
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WORKFLOWS_DIR = REPO / ".github" / "workflows"

# rule -> description
RULES = {
    "W1-yaml": "YAML failed to parse",
    "W2-gh-token": "gh CLI used without GH_TOKEN/GITHUB_TOKEN env or permissions: issues: write",
    "W3-gh-stderr": "gh CLI without stderr redirect (add 2>/dev/null or 2>&1)",
    "W4-backtick": "backtick command substitution (use $(...) instead)",
    "W5-date-quote": "unquoted $(date ...) format with space (quote the format string)",
}

def check_file(path: Path):
    findings = []
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    # W1: yaml safe_load
    try:
        import yaml
        yaml.safe_load(text)
    except Exception as e:
        findings.append((1, "W1-yaml", f"YAML parse error: {e}"))
        # still continue to check other rules on raw lines

    # Determine file-level permissions and env presence for W2 heuristic
    has_gh_token_env = bool(re.search(r'\b(GH_TOKEN|GITHUB_TOKEN)\b', text))
    has_permissions_write = bool(re.search(r'permissions\s*:', text)) and bool(re.search(r'issues\s*:\s*write', text))

    for idx, line in enumerate(lines, 1):
        stripped = line.strip()
        # skip comments
        if stripped.startswith('#'):
            continue

        # W4: backtick in run context
        if '`' in line and '${{' not in line:
            # In shell, backticks inside single quotes are literal
            # Check if backtick is inside single quotes by counting quotes before it
            backtick_pos = line.find('`')
            before = line[:backtick_pos]
            # If odd number of single quotes before backtick, it's inside single quotes -> skip
            if before.count("'") % 2 == 1:
                pass
            else:
                findings.append((idx, "W4-backtick", "backtick substitution found, use $(...)"))

        # W5: $(date ...) unquoted - only when format string contains space (e.g., %H:%M UTC)
        if '$(date' in line:
            # Look for $(date ... +FORMAT) where FORMAT contains space (like "%Y-%m-%d %H:%M")
            m = re.search(r'\$\(date[^)]*\+([^)]+)\)', line)
            if m:
                fmt = m.group(1)
                if ' ' in fmt and '%H:%M' in fmt:
                    # Check if format is quoted: '+%..., "+%..., or whole $(date ...) quoted
                    has_quoted = ("'%" in m.group(0) or '"%' in m.group(0) or "'+" in line or '"+' in line)
                    # Also check if the date command itself is quoted
                    if '"' in line and '$(date' in line:
                        # If the date format is inside single quotes like '+%Y-%m-%d %H:%M UTC', it's quoted
                        if re.search(r"\+['\"]%Y", m.group(0)):
                            has_quoted = True
                    if not has_quoted:
                        findings.append((idx, "W5-date-quote", "unquoted $(date ...) with space, quote the format string"))

        # gh related checks (W2, W3) - only for run: lines and shell lines
        if re.search(r'\bgh\b', line):
            # W2: gh without token
            if not has_gh_token_env and not has_permissions_write:
                # check if this line is actually a gh invocation (not just comment)
                if re.search(r'\bgh\s+(issue|pr|api|repo|auth|run|workflow)', line):
                    findings.append((idx, "W2-gh-token", "gh CLI without GH_TOKEN/GITHUB_TOKEN env and without permissions: issues: write"))
            # W3: gh with stderr discarded (hides errors) - flag when 2>/dev/null present
            if '2>/dev/null' in line:
                if re.search(r'\bgh\s+(issue|pr|api|repo)', line):
                    findings.append((idx, "W3-gh-stderr", "gh call with stderr discarded (2>/dev/null hides errors)"))

    return findings

def main(argv=None):
    argv = argv or sys.argv[1:]
    files = []
    if argv:
        for a in argv:
            p = Path(a)
            if not p.is_absolute():
                p = REPO / a
            if p.is_dir():
                files.extend(sorted(p.glob("*.yml")))
                files.extend(sorted(p.glob("*.yaml")))
            elif p.exists():
                files.append(p)
            else:
                # try workflows dir
                cand = WORKFLOWS_DIR / a
                if cand.exists():
                    files.append(cand)
    else:
        files = sorted(WORKFLOWS_DIR.glob("*.yml")) + sorted(WORKFLOWS_DIR.glob("*.yaml"))

    all_findings = []
    for f in sorted(set(files)):
        if not f.exists():
            continue
        findings = check_file(f)
        for lineno, rule, msg in findings:
            rel = f.relative_to(REPO) if f.is_relative_to(REPO) else f
            print(f"{rel}:{lineno}: {rule} {msg}")
            all_findings.append((f, lineno, rule))

    return 1 if all_findings else 0

if __name__ == "__main__":
    sys.exit(main())
