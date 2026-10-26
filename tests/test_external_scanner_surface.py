"""Decide here what the third-party scanner will say about this repository.

hol-guard's `plugin-scanner` reads the whole repository and uploads its findings as SARIF
(`.github/workflows/guarded-repository.yml`). It runs on a push to `main` and every Monday — so
a finding arrives days after the change that caused it, as an alert on the repository's front
page. On 2026-10-25 that is how twelve alerts arrived, and not one of them was a credential:

  * `docs/_redirects:65` — the slug `di`sk-`full-from-agent-tmp-dirs-gc-pattern`. The scanner's
    `sk-` rule reads the "sk-" inside an English word as the start of an OpenAI-style key;
  * `scripts/gate_mutation_audit.py:473` — this repository's own mutation audit, which plants a
    fake token on purpose, written in the shape the scanner reads;
  * two DSH lessons and their two generated projections — the string `danger-full-access`, in
    prose that explains the trade-off rather than in a configuration.

A copy of somebody else's rules is only worth having if it still detects what it is for and is
applied to the same files, so this module copies the scanner's own rules (verbatim, from
`checks/security.py` of plugin-scanner 2.2.128 — the version whose line numbers reproduce the
alerts above) and applies them to the two surfaces where each rule means what it says:

  * **HARDCODED_SECRET on code**: a credential-shaped literal in `scripts/`, `lib/`, `workers/`,
    `packages/`, `integrations/`, `tests/` or `.github/` is a defect, not a lesson about one.
  * **RISKY_APPROVAL_DEFAULT on shipped configuration**: the rule targets a configuration that
    defaults to bypassed approvals. The corpus is documentation — it names that setting while
    explaining why the narrower option is preferable — and prose is not a default.

The corpus is not left unguarded by that split: `scripts/check_published_secrets.py` scans
`docs/**` and `lessons/**` for credentials and blocks every PR, and `.plugin-scanner.toml` tells
the scanner itself that the corpus and the generated tables are out of scope for these two rules.

What this module does **not** do is claim to be the scanner. It is a predictor, and the
predictor has to be able to fail: `test_the_gate_goes_red_on_a_planted_credential` proves it.
"""
from __future__ import annotations

import re
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CONFIG = REPO / ".plugin-scanner.toml"

# ── the scanner's rules, copied (plugin-scanner 2.2.128, checks/security.py) ────────────────────
SECRET_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("aws_secret_key", re.compile(r"aws_secret_access_key\s*[=:]\s*[\"']?([A-Za-z0-9/+=]{40})", re.I)),
    ("private_key_block", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----")),
    ("password_assignment", re.compile(r"password\s*[=:]\s*[\"']([^\s\"']{8,})", re.I)),
    ("secret_assignment", re.compile(r"secret\s*[=:]\s*[\"']([^\s\"']{8,})", re.I)),
    ("token_assignment", re.compile(r"token\s*[=:]\s*[\"']([^\s\"']{8,})", re.I)),
    ("api_key_assignment", re.compile(r"api_?key\s*[=:]\s*[\"']([^\s\"']{8,})", re.I)),
    ("private_key_assignment", re.compile(r"PRIVATE_KEY\s*[=:]\s*[\"']([^\s\"']{8,})")),
    ("github_token", re.compile(r"gh[pous]_[A-Za-z0-9]{36}")),
    ("github_pat", re.compile(r"github_pat_[A-Za-z0-9_]{20,}")),
    ("gitlab_token", re.compile(r"glpat-[A-Za-z0-9\-]{20}")),
    ("slack_token", re.compile(r"(?:xox[bpas]-|xoxe-|xoxr-|xapp-)[A-Za-z0-9\-]{10,}")),
    ("openai_key", re.compile(r"sk-(?:proj-|ant-)?[A-Za-z0-9_-]{20,}")),
)

APPROVAL_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("danger_full_access", re.compile(r"danger-full-access")),
    ("approval_policy_never", re.compile(r'approval[_ -]?policy["\']?\s*[:=]\s*["\']never["\']', re.I)),
    ("approval_mode_bypass", re.compile(r'approvalMode["\']?\s*[:=]\s*["\']bypass["\']', re.I)),
)

# The scanner's own exemptions, copied for the same reason (checks/security.py, 2.2.128).
EXAMPLE_PATH_HINTS = {
    "docs", "doc", "skills", "skill", "prompts", "prompt", "instructions", "instruction",
    "examples", "example", "samples", "sample", "guides", "guide", "tutorials", "tutorial",
    "rules", "tests", "test", "__tests__", "fixtures", "fixture",
}
DOCUMENTATION_EXTS = {".md", ".mdx", ".markdown", ".rst", ".adoc", ".asciidoc"}
TEST_FILE_RE = re.compile(r"(^test_.*|.*(?:\.test|\.spec)\.[^.]+$|.*_test\.[^.]+$)", re.I)
PLACEHOLDER_MARKERS = ("redacted", "changeme", "set-at-runtime", "set_at_runtime")
EXAMPLE_GENERIC_VALUES = {
    "admin123", "adminpass123", "mypassword123", "password123", "secret-value",
    "secure123", "securep@ss1", "testpass123",
}
BINARY_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".woff", ".woff2", ".ttf", ".eot",
    ".otf", ".zip", ".tar", ".gz", ".7z", ".rar", ".wasm", ".pyc", ".so", ".dylib", ".mp3",
    ".mp4", ".pdf", ".exe", ".dll",
}
SKIP_DIRS = {
    "node_modules", ".git", "dist", "build", ".next", "coverage", ".turbo", "__pycache__",
    ".venv", "venv", "archive",
}

# The code surfaces: where a credential-shaped literal is a defect rather than a lesson.
CODE_SURFACES = ("scripts", "lib", "workers", "packages", "integrations", ".github", "tests",
                 "misakanet", "scripts", "agents")
# The surfaces the scanner is told are out of scope (`.plugin-scanner.toml`): the corpus and the
# tables generated from it. The scanner's own rules for them are noise, and the repository's own
# published-secret gate covers the credential case there.
CORPUS_SURFACES = ("data", "docs", "lessons")

# Reviewed findings on the code surfaces: (path, rule) -> why it is not a credential. Every entry
# names the GitHub alert that was dismissed for it, so a new entry cannot be a guess.
REVIEWED: dict[tuple[str, str], str] = {
    ("lib/client.js", "token_assignment"): (
        "the slash-command claim `/misakanet`, not a credential — dismissed as a false positive "
        "in alerts #318/#319"
    ),
}


def _is_example_surface(relative_path: Path) -> bool:
    """The scanner's own exemption test (checks/security.py, 2.2.128)."""
    parts = {part.lower() for part in relative_path.parts}
    return (
        relative_path.suffix.lower() in DOCUMENTATION_EXTS
        or bool(parts & EXAMPLE_PATH_HINTS)
        or bool(TEST_FILE_RE.search(relative_path.name))
    )


def _is_test_surface(relative_path: Path) -> bool:
    """Test and fixture files: their subject is secret-shaped input, not a shipped credential.

    `tests/test_scanner_secret_patterns.py` keeps the same discipline with `EXEMPT_FILES`, where
    every exemption names its reason and has to still match.
    """
    parts = {part.lower() for part in relative_path.parts}
    return bool(parts & {"tests", "test", "__tests__", "fixtures", "fixture"}) or bool(
        TEST_FILE_RE.search(relative_path.name))


def _looks_like_placeholder(value: str) -> bool:
    """The scanner's placeholder test, copied (checks/security.py, 2.2.128)."""
    normalized = value.strip().strip("\"'`")
    if normalized.lower().startswith("bearer "):
        normalized = normalized[7:].strip()
    lowered = normalized.lower()
    if not normalized:
        return True
    if normalized.startswith(("${", "{{", "<", "[")):
        return True
    if "..." in normalized or "…" in normalized:
        return True
    if lowered.startswith(("your-", "your_", "your", "example-", "sample-", "demo-")):
        return True
    if lowered.endswith(("-here", "_here", "example", "sample")):
        return True
    if lowered in PLACEHOLDER_MARKERS:
        return True
    return bool(re.search(r"(?i)(?:^|[-_])(x{4,}|\*{3,})(?:[-_]|$)", normalized))


def _looks_like_example_generic(value: str) -> bool:
    """The scanner's example-value test, copied (checks/security.py, 2.2.128)."""
    normalized = re.sub(r"[^a-z0-9]", "", value.strip().strip("\"'`").lower())
    return normalized in EXAMPLE_GENERIC_VALUES


def _iter_files(surfaces: tuple[str, ...]) -> list[Path]:
    files: list[Path] = []
    for surface in surfaces:
        root = REPO / surface
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.is_symlink():
                continue
            if any(part in SKIP_DIRS for part in path.relative_to(REPO).parts):
                continue
            if path.suffix.lower() in BINARY_EXTS:
                continue
            files.append(path)
    return files


def _relative(path: Path) -> Path:
    """The path as the scanner sees it — relative to the repository root when it is inside it."""
    try:
        return path.relative_to(REPO)
    except ValueError:
        return Path(path.name)


def _secret_hits(path: Path) -> list[tuple[str, int]]:
    """The secret rules over one file, with the scanner's exemptions applied."""
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    relative = _relative(path)
    hits: list[tuple[str, int]] = []
    for name, pattern in SECRET_RULES:
        for match in pattern.finditer(content):
            value = match.group(1) if match.groups() else match.group(0)
            if _is_example_surface(relative):
                if _looks_like_placeholder(value) or _looks_like_example_generic(value):
                    continue
            hits.append((name, content[: match.start()].count("\n") + 1))
    return hits


def _approval_hits(path: Path) -> list[tuple[str, int]]:
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    return [
        (name, content[: match.start()].count("\n") + 1)
        for name, pattern in APPROVAL_RULES
        for match in pattern.finditer(content)
    ]


def _config_ignore_paths() -> list[str]:
    payload = tomllib.loads(CONFIG.read_text(encoding="utf-8"))
    return list(payload.get("scanner", {}).get("ignore_paths", []))


# ── the gate ────────────────────────────────────────────────────────────────────────────────────
def test_no_credential_shaped_literal_appears_on_the_code_surfaces():
    """Every secret-shaped literal in the code must be a reviewed finding, and only that.

    A new entry here is a new finding by the scanner — the thing that used to arrive on Monday
    with an alert number. `REVIEWED` says why an existing one is not a credential.
    """
    unclassified: list[str] = []
    for path in _iter_files(CODE_SURFACES):
        relative = path.relative_to(REPO)
        if _is_test_surface(relative):
            continue
        for name, line in _secret_hits(path):
            reason = REVIEWED.get((relative.as_posix(), name))
            if reason is None:
                unclassified.append(f"{relative.as_posix()}:{line} ({name})")
    assert unclassified == [], (
        "these would be reported as HARDCODED_SECRET by hol-guard's plugin-scanner, and none of "
        "them is reviewed:\n  " + "\n  ".join(unclassified)
    )


def test_no_shipped_configuration_defaults_to_bypassing_approvals():
    """The rule's own target: a configuration that defaults to bypassed approvals.

    The corpus names the setting while explaining why the narrower option is preferable; that is
    prose. A configuration file that *ships* the setting is a different thing, and none does.
    """
    offenders: list[str] = []
    for path in _iter_files(CODE_SURFACES):
        relative = path.relative_to(REPO)
        if relative.suffix.lower() not in {".json", ".yaml", ".yml", ".toml"}:
            continue
        if _is_test_surface(relative):
            continue
        for name, line in _approval_hits(path):
            offenders.append(f"{relative.as_posix()}:{line} ({name})")
    assert offenders == [], (
        "a shipped configuration defaults to bypassing approvals:\n  " + "\n  ".join(offenders)
    )


def test_every_reviewed_finding_is_still_earned():
    """A reviewed finding that stopped matching is a stale exemption — and a stale exemption is
    a hole in the baseline, not tidiness. It also means the file changed under the reason."""
    for (path, rule), reason in REVIEWED.items():
        target = REPO / path
        assert target.is_file(), f"REVIEWED names {path}, which does not exist"
        assert reason.strip(), f"REVIEWED names {path} ({rule}) without a reason"
        names = [name for name, _ in _secret_hits(target)]
        assert rule in names, (
            f"{path} no longer matches {rule}: the reviewed finding is stale, and the reason "
            f"recorded for it no longer applies — re-review it instead of keeping the entry"
        )


def test_the_scanner_config_covers_the_corpus_and_names_only_real_paths():
    """`.plugin-scanner.toml` is the scanner's own out-of-scope list, so it has to stay true.

    It must cover the corpus and the tables generated from it (otherwise the corpus hits come
    back every scan), and every path it names must exist (a stale path is a promise the scanner
    cannot keep).
    """
    ignore_paths = _config_ignore_paths()
    assert ignore_paths, "the scanner config must say what is out of scope, not nothing"
    for surface in CORPUS_SURFACES:
        assert any(pattern.startswith(f"{surface}/") for pattern in ignore_paths), (
            f"{surface}/ is not out of scope for the scanner's heuristics — the corpus is prose, "
            f"and prose that names a setting is not a configuration"
        )
    for pattern in ignore_paths:
        head = pattern.split("/", 1)[0]
        assert (REPO / head).exists(), f"the scanner config ignores {pattern}, which does not exist"


def test_the_copied_rules_still_detect_what_they_are_for():
    """Guard the guard: a copy of somebody else's rules is worth nothing if it stopped detecting."""
    samples = {
        "aws_access_key": "AKIA" + "IOSFODNN7EXAMPLE",
        "github_token": "ghp_" + "a" * 36,
        "github_pat": "github_pat_" + "a" * 20,
        "gitlab_token": "glpat-" + "a" * 20,
        "slack_token": "xoxb-" + "1" * 12,
        "openai_key": "sk-" + "a" * 48,
        "token_assignment": 'token: "' + "b" * 12 + '"',
        "secret_assignment": 'secret = "' + "c" * 12 + '"',
        "password_assignment": 'password: "' + "d" * 12 + '"',
        "api_key_assignment": 'api_key: "' + "e" * 12 + '"',
        "private_key_block": "-----BEGIN RSA " + "PRIVATE KEY-----\nabc\n-----END RSA PRIVATE KEY-----",
    }
    for name, sample in samples.items():
        pattern = dict(SECRET_RULES)[name]
        assert pattern.search(sample), f"the copied {name} rule no longer detects its own sample"

    for name, sample in {
        "danger_full_access": "permissionMode: danger-full-access",
        "approval_policy_never": '"approvalPolicy": "never"',
        "approval_mode_bypass": '"approvalMode": "bypass"',
    }.items():
        pattern = dict(APPROVAL_RULES)[name]
        assert pattern.search(sample), f"the copied {name} rule no longer detects its own sample"


def test_the_gate_goes_red_on_a_planted_credential(tmp_path):
    """The gate has to be able to fail, or it is decoration."""
    planted = tmp_path / "worker.mjs"
    planted.write_text('export const client = { token: "' + "z" * 24 + '" };\n', encoding="utf-8")
    hits = _secret_hits(planted)
    assert hits, "a planted credential-shaped literal must be reported by the copied rules"

    unclassified = [name for name, _ in hits
                    if REVIEWED.get((_relative(planted).as_posix(), name)) is None]
    assert unclassified, "a planted credential must be unclassified, or the gate would pass it"
