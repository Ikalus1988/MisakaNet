#!/usr/bin/env python3
"""Validate `docs/field-reports/*` against the evidence bar the schema already describes (#2042).

Why this exists
---------------
`docs/field-reports/` holds free-text claims of the form "I ran client X against the live MCP
endpoint". A schema for exactly that report already exists — `misakanet-setup-report/1`, emitted by
`packages/misakanet-setup` (`--report`) and documented in `docs/maintainer/setup-health-ci.md` — and
nothing ever checked a submission against it. So "I ran this" and "here is a run record" looked
identical in the repository:

* on 2026-09-21 three submissions were closed for carrying **zero executable evidence**;
* #1976 claimed a *verified* run whose quoted `tools/list` returned **1** tool, against a live
  endpoint that returns **7**, and named the host `misakanet.com` (ours is `misakanet.org`). A
  human caught it by reading; the bar for the next one is that a machine catches it first.

What this checks (machine-checkable only)
-----------------------------------------
FR1  endpoint host        every `misakanet.<tld>` host is `misakanet.org`; a URL ending in `/mcp`
                          is on our host. `misakanet.com` is called out by name — it is the exact
                          mistake of #1976 and is never a legitimate spelling of our endpoint.
FR2  tool count           every stated endpoint tool count is 7 (the live endpoint advertises
                          `misakanet_register`, `misakanet_search`, `misakanet_get_lesson`,
                          `misakanet_submit_intake`, `misakanet_write_lesson`, `misakanet_preflight`,
                          `misakanet_me_events`). A report quoting "1 tool" is contradicted by the
                          endpoint it claims to have called.
FR3  home path            no unredacted `C:\\Users\\<name>`, `/mnt/<d>/Users/<name>`, `/home/<name>`
                          or `/Users/<name>`, per the redaction rules in
                          `docs/field-reports/README.md` (the directory is published).
FR4  search envelope      a report naming `misakanet_search` must show the machine-readable result
                          envelope (`results` / `no_match`), not a prose paraphrase of it. "returned
                          a structured result" cannot be re-run; `{"results":[…]}` can.
FR5  handshake count      a report naming `tools/list` must state how many tools came back — the
                          element #1976 got wrong in the one direction a human cannot see.
FR6  client version       a report claiming a configured/registered client session names a version
                          for the client or the installer.
FR7  config path          the same report names the config file it wrote (the schema's "config path"
                          field is what lets a reader go and look).
FR8  (info)               the report makes no live-endpoint claim at all, so the setup-report schema
                          does not apply to it. Reported so that "nothing was checked here" is never
                          silent — it is explicitly out of scope rather than passed.

What this deliberately does NOT do
----------------------------------
It does **not** judge semantic truth. A rule can see that a report's numbers disagree with a known
constant (7 tools) or with our own host name; it cannot see whether `{"results":[…]}` was typed by
hand or produced by a run, whether the quoted log line belongs to the machine it names, or whether
the conclusion follows from the evidence. Those remain a human reviewer's job — this gate exists so
that the review starts from a structurally checkable artifact instead of from prose.

The escape hatch, and why it is not a hole
------------------------------------------
A report may *decline* to provide evidence for a surface it explicitly marks as unverified
("未验证", "unverified", "could not be tested", "not installed", … within 3 lines of the claim). That
is honesty, not a violation: a gate that punishes "I could not test this" gets reports that stop
saying it. It cannot be used to fake a claim — a fabricated run states numbers, and the numbers are
what FR2 checks.

Exit codes (the repository's convention: `scripts/check_workflow_scripts.py`)
  0  no gating findings
  1  gating findings
  2  the checker could not run (unreadable directory, unresolvable `--base`)

Usage
  python3 scripts/check_field_reports.py                     # strict: every report is judged
  python3 scripts/check_field_reports.py --dir <dir>         # another corpus (tests use this)
  python3 scripts/check_field_reports.py --base origin/main  # CI: changed files gate, the rest is
                                                             # reported as LEGACY (advisory)
  python3 scripts/check_field_reports.py --changed a.md      # explicit changed set (tests)
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DIR = REPO_ROOT / "docs" / "field-reports"

# The corpus is `docs/field-reports/*` written by humans; YAML/JSON are accepted because the schema
# itself is emitted in those encodings (#1784).
SUFFIXES = (".md", ".yaml", ".yml", ".json")

# `README.md` is the instruction page, not a submission: it holds the template (with placeholders
# like `YYYY-MM-DD`) and the redaction *examples*. It still gets the content rules (a `misakanet.com`
# in the instructions would be just as wrong), but never the shape rules.
SHAPE_EXEMPT = {"README.md"}

# The live endpoint's tool list (AGENTS.md §3.2).
EXPECTED_TOOL_COUNT = 7
LIVE_TOOLS = (
    "misakanet_register",
    "misakanet_search",
    "misakanet_get_lesson",
    "misakanet_submit_intake",
    "misakanet_write_lesson",
    "misakanet_preflight",
    "misakanet_me_events",
)

# rule id -> (severity, one-line purpose). `truth` = factually wrong or a leak; `evidence` = a claim
# without the field the schema requires; `info` = out of scope, never gates.
RULES: dict[str, tuple[str, str]] = {
    "FR1-endpoint-host": ("truth", "a named MisakaNet host must be misakanet.org"),
    "FR2-tool-count": ("truth", f"a stated endpoint tool count must be {EXPECTED_TOOL_COUNT}"),
    "FR3-home-path": ("truth", "no unredacted home path (the directory is published)"),
    "FR4-search-envelope": ("evidence", "a named misakanet_search needs its results/no_match envelope"),
    "FR5-tools-list-count": ("evidence", "a named tools/list needs the number of tools it returned"),
    "FR6-client-version": ("evidence", "a claimed client session needs a version"),
    "FR7-config-path": ("evidence", "a claimed client session needs the config path it wrote"),
    "FR8-no-run-claim": ("info", "no live-endpoint claim: the setup-report schema does not apply"),
}

# Rules that gate the *whole* corpus even in `--base` mode. Only FR1 is here, and deliberately:
# the issue's own words are that a wrong endpoint domain "应直接判红" — it is a false statement about
# infrastructure we own, with no legitimate reading. Everything else that is merely missing evidence
# is legacy debt: reported on every run, gating only the file a PR actually touches, so that one
# pre-existing prose report cannot hold every PR in the repository (the failure mode lesson-gate.yml
# was fixed for on 2026-09-21).
GATING_ALWAYS = frozenset({"FR1-endpoint-host"})

# ── FR1: hosts ───────────────────────────────────────────────────────────────────────────────────

# `misakanet.<something>`. The lookarounds keep filenames such as `misakanet.mjs` out of the match
# list via FILE_EXT_LOOKALIKE rather than by making the pattern guess at "host-ness".
_HOST_RE = re.compile(r"(?<![\w.-])misakanet\.([a-z]{2,12})(?![\w-])")
# Extensions that are not TLDs, for the day a report names `bin/misakanet.mjs`.
_FILE_EXT_LOOKALIKE = frozenset({
    "mjs", "cjs", "js", "jsx", "ts", "tsx", "py", "md", "json", "jsonl", "yml", "yaml", "toml",
    "txt", "sh", "bash", "zsh", "ps1", "lock", "html", "css", "whl", "tgz", "gz", "zip", "svg",
    "png", "jpg", "log", "db", "sql", "ini", "cfg", "env", "local",
})
_OUR_HOST = "misakanet.org"
_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "[::1]", "::1"})
_URL_RE = re.compile(r"https?://([A-Za-z0-9._~%!$&'()*+,;=:@\[\]-]+)([^\s\)\]\"'`>]*)")
_MCP_PATH_RE = re.compile(r"/mcp(?:[/?#]|$)")

# ── FR2: tool counts ─────────────────────────────────────────────────────────────────────────────
#
# Every spelling in the corpus that actually states "the endpoint exposes N tools". A bare `"tools":
# N` inside a `toolSummary` is a *call* count, not a tool-list count, so a quoted key is excluded.
_COUNT_PATTERNS = (
    ("endpoint-tools", re.compile(r"endpoint-tools\s*:\s*(\d+)")),
    ("tools-visible", re.compile(r"tools-visible\s*:\s*\{[^}\n]*?:\s*(\d+)")),
    ("<N> tool(s)", re.compile(r"(?<![\w.])(\d+)\s*(?:个\s*)?tool(?:s|\(s\))?\b", re.IGNORECASE)),
    ("<N> 个工具", re.compile(r"(?<![\w.])(\d+)\s*个\s*工具")),
    ("tools: <N>", re.compile(r"(?<![\"'`])\btools?\s*[:=]\s*(\d+)\b")),
)

# ── FR3: home paths ──────────────────────────────────────────────────────────────────────────────

_HOME_PATH_PATTERNS = (
    ("windows", re.compile(r"[A-Za-z]:\\+Users\\+([^\s\\/\"'`,;:)]+)", re.IGNORECASE)),
    ("wsl", re.compile(r"/mnt/[a-z]/Users/([^\s/\"'`,;:)]+)")),
    ("posix", re.compile(r"/home/([A-Za-z0-9._-]+)")),
    ("macos", re.compile(r"/Users/([A-Za-z0-9._-]+)")),
)
# Names that are already a redaction. `/home/<user>/` does not even reach the regex (the angle
# brackets are not in the character class) — this set covers the spelled-out forms.
_PLACEHOLDERS = frozenset({
    "user", "users", "username", "youruser", "your-user", "your_user", "name", "me", "you",
    "someone", "somebody", "example", "redacted", "xxx", "foo", "bar", "baz", "alice", "bob",
    "tester", "test", "runner", "yourname", "your-name", "your_name",
})
_PLACEHOLDER_RE = re.compile(r"[<$%{][\w-]*[>$%}]?|%username%|\$\{?\w+\}?")

# ── FR4/FR5: search evidence and handshake count ─────────────────────────────────────────────────

_SEARCH_TOOL_RE = re.compile(r"\bmisakanet_search\b")
# The envelope `misakanet_search` returns: `{results: [...]}` or `{no_match: true, …}`.
_ENVELOPE_RE = re.compile(r'"results"|(?<![\w.])results\s*:|\bno_match\b')
_TOOLS_LIST_RE = re.compile(r"\btools/list\b")

# ── FR6/FR7: client session claims and the fields they owe ───────────────────────────────────────

# A "session claim": the report says a client was configured, registered or actually answered a tool
# call. A bare mention of `tools/call` in prose is not one — `2026-09-20-gemini-cli-mcp-headless.md`
# says the handshake needs no token "for `tools/list` or `tools/call`" while explicitly declining to
# verify any client session, and it must not be read as a claim.
_SESSION_CLAIM_PATTERNS = (
    re.compile(r"schema\s*:\s*misakanet-setup-report/1"),
    re.compile(r"detected-agents\s*:"),
    re.compile(r"\bmcp\s+(?:list|add|tools|test)\b"),
    re.compile(r"registered\s+\d+\s+tool"),
    re.compile(r"MCP\s*注册"),
    re.compile(r"tools-visible\s*:"),
    re.compile(r"\btoolSummary\b"),
    re.compile(r"<untrusted_tool_result\b"),
    re.compile(r"\btool_call\b"),
    re.compile(r"Tool call:"),
    re.compile(r"工具调用序列"),
)
_VERSION_RE = re.compile(r"\bv?\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.\-]+)?\b")
_VERSION_KV_RE = re.compile(r"(?i)\bver(?:sion)?\s*[:=]\s*[\"']?(?:v)?\d+\.\d+")
_CONFIG_PATH_RE = re.compile(
    r"[\w./~$<>-]*(?:config|settings|mcp|openclaw|claude|codex|gemini|hermes|dsh)[\w.-]*"
    r"\.(?:json|toml|ya?ml)\b",
    re.IGNORECASE,
)

# A live-endpoint claim at all (FR8 is emitted when a report has none of these).
_LIVE_CLAIM_PATTERNS = (
    re.compile(r"https?://[^\s\)\]\"'`>]*/mcp(?:[/?#]|$)"),
    re.compile(r"\btools/list\b"),
    re.compile(r"\bmisakanet_(?:register|search|get_lesson|submit_intake|write_lesson|preflight|me_events)\b"),
    re.compile(r"\bmisakanet[-_]setup\b"),
    re.compile(r"misakanet-setup-report"),
)

# ── the "declined on purpose" window ─────────────────────────────────────────────────────────────

DECLINED_WINDOW = 3
_DECLINED_MARKERS = (
    "未验证", "未确证", "无法验证", "没能验证", "未测",
    "unverified", "not verified", "could not be verified", "couldn't be verified",
    "cannot be verified", "can not be verified", "could not be tested", "not tested",
    "not from a local run", "not installed", "not available on this host",
)


@dataclass(frozen=True)
class Finding:
    rule: str
    line: int
    message: str
    #: label of the file the finding was made in (path relative to the invocation, or the filename)
    path: str = ""

    @property
    def severity(self) -> str:
        return RULES[self.rule][0]

    def render(self) -> str:
        """`file:line: RULE message`, the format `scripts/check_workflow_scripts.py` uses."""
        where = f"{self.path}:{self.line}" if self.path else f"line {self.line}"
        return f"{where}: {self.rule}: {self.message}"


def _declined(lines: list[str]) -> set[int]:
    """1-based line numbers within `DECLINED_WINDOW` of an explicit "I could not verify this"."""
    out: set[int] = set()
    for idx, line in enumerate(lines, 1):
        low = line.lower()
        if any(marker in low for marker in _DECLINED_MARKERS):
            out.update(range(max(1, idx - DECLINED_WINDOW), idx + DECLINED_WINDOW + 1))
    return out


def _check_hosts(lines: list[str], path: str) -> list[Finding]:
    findings: list[Finding] = []
    for lineno, line in enumerate(lines, 1):
        for match in _HOST_RE.finditer(line):
            tld = match.group(1)
            if tld in _FILE_EXT_LOOKALIKE or tld == "org":
                continue
            extra = (" — `misakanet.com` is the spelling used by the rejected report #1976; the "
                     "endpoint has never been on that host") if tld == "com" else ""
            findings.append(Finding(
                "FR1-endpoint-host", lineno,
                f"named host `misakanet.{tld}` is not ours (only `{_OUR_HOST}` is){extra}",
                path))
        for match in _URL_RE.finditer(line):
            host, tail = match.group(1).lower(), match.group(2)
            if "@" in host:                      # strip userinfo
                host = host.rsplit("@", 1)[1]
            host = host.split(":", 1)[0] if not host.startswith("[") else host
            if not _MCP_PATH_RE.search(tail):
                continue
            if host == _OUR_HOST or host in _LOCAL_HOSTS:
                continue
            findings.append(Finding(
                "FR1-endpoint-host", lineno,
                f"an MCP endpoint URL on `{host}` is not the live endpoint (`https://{_OUR_HOST}/mcp`)",
                path))
    return findings


def _check_tool_counts(lines: list[str], path: str) -> list[Finding]:
    findings: list[Finding] = []
    for lineno, line in enumerate(lines, 1):
        for label, pattern in _COUNT_PATTERNS:
            for match in pattern.finditer(line):
                count = int(match.group(1))
                if count == EXPECTED_TOOL_COUNT:
                    continue
                findings.append(Finding(
                    "FR2-tool-count", lineno,
                    f"states {count} tool(s) ({label}: `{match.group(0).strip()}`); the live "
                    f"endpoint advertises {EXPECTED_TOOL_COUNT} "
                    f"({', '.join(LIVE_TOOLS)})",
                    path))
    return findings


def _check_home_paths(lines: list[str], path: str) -> list[Finding]:
    findings: list[Finding] = []
    for lineno, line in enumerate(lines, 1):
        # Longest match wins: `/mnt/c/Users/Eric` also contains `/Users/Eric`, and reporting the same
        # leak twice under two platform labels reads like two leaks.
        spans: list[tuple[int, int]] = []
        hits: list[tuple[int, str, str]] = []
        for kind, pattern in _HOME_PATH_PATTERNS:
            for match in pattern.finditer(line):
                if any(start <= match.start() < end for start, end in spans):
                    continue
                if match.group(1).lower() in _PLACEHOLDERS or _PLACEHOLDER_RE.fullmatch(match.group(1)):
                    continue
                spans.append(match.span())
                hits.append((match.start(), kind, match.group(0)))
        for _, kind, text in sorted(hits):
            findings.append(Finding(
                "FR3-home-path", lineno,
                f"unredacted {kind} home path `{text}` — this directory is published; redact it to "
                f"`/home/<user>/` (docs/field-reports/README.md)",
                path))
    return findings


def _check_claims(lines: list[str], text: str, path: str) -> list[Finding]:
    """FR4–FR8: the evidence rules, each tied to an explicit claim."""
    findings: list[Finding] = []
    declined = _declined(lines)
    has_envelope = bool(_ENVELOPE_RE.search(text))
    counts = [m for _, p in _COUNT_PATTERNS for m in p.finditer(text)]

    live_claim = any(p.search(text) for p in _LIVE_CLAIM_PATTERNS)
    if not live_claim:
        findings.append(Finding(
            "FR8-no-run-claim", 1,
            "this report claims no run against the live MCP endpoint (no endpoint URL, no "
            "`tools/list`, no `misakanet_*` tool, no setup report), so the `misakanet-setup-report/1` "
            "fields do not apply to it: only FR1–FR3 were enforced. Not a failure — a statement of "
            "scope, so that an unchecked report is never a silent one.",
            path))
        return findings

    # FR4 — `misakanet_search` named, but the result is prose.
    for lineno, line in enumerate(lines, 1):
        if not _SEARCH_TOOL_RE.search(line) or lineno in declined:
            continue
        if has_envelope:
            break
        findings.append(Finding(
            "FR4-search-envelope", lineno,
            "names `misakanet_search` but shows no result envelope; quote the JSON "
            "(`{\"results\": […]}` or `{\"no_match\": true, …}`) instead of describing it, or mark "
            "the call unverified",
            path))
        break

    # FR5 — `tools/list` named, but no count.
    for lineno, line in enumerate(lines, 1):
        if not _TOOLS_LIST_RE.search(line) or lineno in declined:
            continue
        if counts:
            break
        findings.append(Finding(
            "FR5-tools-list-count", lineno,
            f"names `tools/list` but states no tool count; \"it answered\" is not checkable, "
            f"\"{EXPECTED_TOOL_COUNT} tools\" is (the live endpoint's list)",
            path))
        break

    # FR6/FR7 — a client session is claimed, so a version and a config path are owed.
    claims = [lineno for lineno, line in enumerate(lines, 1)
              if lineno not in declined and any(p.search(line) for p in _SESSION_CLAIM_PATTERNS)]
    if claims:
        first_claim = claims[0]
        if not (_VERSION_RE.search(text) or _VERSION_KV_RE.search(text)):
            findings.append(Finding(
                "FR6-client-version", first_claim,
                "claims a configured/registered client session but names no version for the client "
                "or the installer; the schema's client-version field is what makes a run "
                "reproducible — say which build produced the evidence, or mark it unverified",
                path))
        if not _CONFIG_PATH_RE.search(text):
            findings.append(Finding(
                "FR7-config-path", first_claim,
                "claims a configured/registered client session but names no config file it wrote; "
                "the schema's config-path field is what lets a reader go and look "
                "(e.g. `~/.codex/config.toml`)",
                path))
    return findings


def check_text(path_label: str, text: str) -> list[Finding]:
    """Every rule, over one file's text. Shape rules are skipped for `README.md`."""
    lines = text.splitlines()
    findings = _check_hosts(lines, path_label)
    findings += _check_tool_counts(lines, path_label)
    findings += _check_home_paths(lines, path_label)
    if Path(path_label).name not in SHAPE_EXEMPT:
        findings += _check_claims(lines, text, path_label)
    return sorted(findings, key=lambda f: (f.path, f.line, f.rule))


def _changed_via_git(directory: Path, base: str) -> set[Path]:
    """Files under `directory` added or modified since `base`, plus untracked ones.

    Raises `RuntimeError` rather than returning an empty set: "the base ref cannot be resolved" and
    "nothing changed" are different answers, and the first one must not look like a clean pass.
    """
    def git(*args: str) -> str:
        proc = subprocess.run(["git", "-C", str(REPO_ROOT), *args],
                              capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
        return proc.stdout

    try:
        rel_dir = directory.resolve().relative_to(REPO_ROOT)
    except ValueError:
        raise RuntimeError(
            f"--base only works for a corpus inside the repository ({directory} is outside "
            f"{REPO_ROOT}); pass --changed <file>… instead")
    rel = str(rel_dir)
    names = git("diff", "--name-only", "--diff-filter=AM", f"{base}...HEAD", "--", rel)
    untracked = git("ls-files", "--others", "--exclude-standard", "--", rel)
    out = set()
    for line in (names + untracked).splitlines():
        if line.strip():
            out.add((REPO_ROOT / line.strip()).resolve())
    return out


def collect(directory: Path, changed: set[Path] | None, strict_all: bool) -> tuple[list[Finding], list[Finding], int]:
    """Returns `(gating, legacy, files_scanned)`. With no `changed` set everything is gating."""
    files = sorted(p for p in directory.iterdir() if p.is_file() and p.suffix in SUFFIXES)
    gating: list[Finding] = []
    legacy: list[Finding] = []
    for path in files:
        label = str(path.relative_to(directory)) if directory in path.parents else path.name
        findings = check_text(label, path.read_text(encoding="utf-8", errors="replace"))
        for finding in findings:
            if strict_all or changed is None or path.resolve() in changed:
                gating.append(finding)
            elif finding.rule in GATING_ALWAYS:
                gating.append(finding)
            else:
                legacy.append(finding)
    return gating, legacy, len(files)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dir", default=str(DEFAULT_DIR),
                        help="report directory (default: docs/field-reports)")
    parser.add_argument("--base", default="",
                        help="git ref to diff against; findings on files this PR did not change "
                             "are reported as LEGACY (advisory) instead of gating")
    parser.add_argument("--changed", nargs="*", default=None,
                        help="explicit changed-file list instead of --base (for tests)")
    parser.add_argument("--strict-all", action="store_true",
                        help="every file gates, even with --base (corpus audits)")
    args = parser.parse_args(argv)

    directory = Path(args.dir)
    if not directory.is_dir():
        print(f"cannot run: {directory} is not a directory", file=sys.stderr)
        return 2

    try:
        if args.changed is not None:
            changed = {(Path(p).resolve()) for p in args.changed}
        elif args.base and not args.strict_all:
            changed = _changed_via_git(directory, args.base)
        else:
            changed = None
    except RuntimeError as exc:
        print(f"cannot run: {exc}", file=sys.stderr)
        return 2

    gating, legacy, scanned = collect(directory, changed, strict_all=args.strict_all or changed is None)

    scope = "every report (strict)" if changed is None else f"{len(changed)} changed file(s)"
    print(f"# field reports: {directory}  ·  {scanned} file(s)  ·  scope: {scope}")
    if changed is not None:
        print(f"# changed: {', '.join(sorted(p.name for p in changed)) or '(none)'}")
    for finding in gating:
        print(finding.render())
    if legacy:
        print(f"# LEGACY ({len(legacy)} finding(s) in files this run did not change — advisory, "
              f"not gating; fix them when you touch the file, or run --strict-all to audit)")
        for finding in legacy:
            print(f"legacy: {finding.render()}")
    n_info = sum(1 for f in gating if f.severity == "info")
    n_red = sum(1 for f in gating if f.severity != "info")
    print(f"SUMMARY files={scanned} gating={n_red} info={n_info} legacy={len(legacy)} "
          f"verdict={'FAIL' if n_red else 'PASS'}")
    return 1 if n_red else 0


if __name__ == "__main__":
    sys.exit(main())
