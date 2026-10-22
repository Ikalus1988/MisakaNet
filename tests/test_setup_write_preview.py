#!/usr/bin/env python3
"""The install preview (#3690): what the npx installer says it is about to write — before it writes it.

The audience of `npx @misaka-net/misakanet-setup` is people who never open a checkout, so "it also
edited my agent's rules file" is not a thing they can find out before it happens — and that file is
the one that changes how the agent behaves. The install therefore prints a summary of the writes
*before* the first one: how many files, what kind of change each is, and the three ways out
(`--list-writes`, `--mcp-only`, `--uninstall`).

What is pinned here, and why each one is a fact rather than prose:

* the summary is printed **before** any write. The proof is a run whose first write cannot happen:
  a preview printed after the writes would never be seen, so its presence in a failed run is the
  evidence that it comes first. A test that only checked the text would pass for a summary printed
  at the very end, which is exactly the bug this issue is about;
* the summary is built from the same manifest `--list-writes` prints — one list, so the two cannot
  disagree about what the command would touch;
* `--mcp-only` really writes neither the rules block nor the hook (the preview's claim, checked
  against the disk instead of against the text);
* `--silent` and `--report-json` keep their existing contracts: a clean silent run is an empty log,
  and the CI form is exactly one JSON document.

The installer is driven as a subprocess with a throwaway `--home`, never the developer's real agent
config, and with `--no-register` so no run touches the network.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
INSTALLER = REPO / "packages" / "misakanet-setup" / "bin" / "misakanet-setup.mjs"

# The preview's first line: the file count. `--dry-run` adds a parenthetical to the same line.
COUNT_LINE = re.compile(r"^将修改 (\d+) 个文件")

# The three ways out of a write, in one line.
WAYS_OUT = ("--list-writes", "--mcp-only", "--uninstall")

# The three kinds of change the issue names, as the summary words them.
KIND_MCP = "MCP 端点"
KIND_RULES = "规则块（会改变 agent 的行为）"
KIND_HOOK = "钩子"

RULES_FILES = ("CLAUDE.md", "AGENTS.md", "SOUL.md")


@pytest.fixture(scope="module")
def node() -> str:
    found = shutil.which("node")
    if not found:
        pytest.skip("node is not on PATH")
    return found


def make_home(tmp_path: Path) -> Path:
    """A home with one detectable assistant (Claude Code), and nothing else."""
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    (home / ".claude.json").write_text('{"mcpServers": {}}', encoding="utf-8")
    (home / ".claude" / "settings.json").write_text("{}", encoding="utf-8")
    return home


def run_setup(node: str, home: Path, *flags: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [node, str(INSTALLER), "--home", str(home), "--no-register", *flags],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180,
    )


def parse_preview(stdout: str) -> dict:
    """The preview block: its file count, one entry per file, and the ways-out line.

    Parsed from the text rather than matched with one regex, because the block is what the *user*
    reads: a summary whose lines cannot be found again is a summary nobody can assert on.
    """
    lines = stdout.splitlines()
    for index, line in enumerate(lines):
        counted = COUNT_LINE.match(line)
        if not counted:
            continue
        files = []
        footer = ""
        for follow in lines[index + 1:]:
            if follow.startswith("  "):
                files.append(follow)
                continue
            if follow.strip():
                footer = follow.strip()
            break
        entries = []
        for entry in files:
            path, _, kind = entry.strip().partition(" + ")
            entries.append((path.strip(), [part.strip() for part in kind.split(" + ")]))
        return {"count": int(counted.group(1)), "files": entries, "footer": footer}
    return {"count": None, "files": [], "footer": ""}


# ── the preview itself ─────────────────────────────────────────────────────────────────────────────

def test_the_default_run_says_what_it_is_about_to_write(node, tmp_path):
    """The count, the kinds, and the three ways out — all before anything is written."""
    home = make_home(tmp_path)
    result = run_setup(node, home, "--only", "claude")
    assert result.returncode == 0, result.stdout + result.stderr

    preview = parse_preview(result.stdout)
    assert preview["count"] is not None, f"no preview in the output:\n{result.stdout}"
    assert preview["count"] == len(preview["files"]), (
        f"the header says {preview['count']} files but {len(preview['files'])} are listed:\n{result.stdout}")
    assert preview["count"] > 0, result.stdout

    kinds = {kind for _path, kinds in preview["files"] for kind in kinds}
    assert KIND_MCP in kinds, f"the MCP endpoint entry is missing:\n{result.stdout}"
    assert KIND_RULES in kinds, f"the rules block is missing:\n{result.stdout}"
    assert KIND_HOOK in kinds, f"the hook entry is missing:\n{result.stdout}"

    # The rules block is the one that changes the agent's behaviour, so the summary has to say so
    # in the same words the user will read later.
    rules = [path for path, kinds in preview["files"] if KIND_RULES in kinds]
    assert rules and rules[0].endswith(RULES_FILES), (
        f"the rules block must name the file it is appended to: {rules}")
    hook = [path for path, kinds in preview["files"] if KIND_HOOK in kinds]
    assert hook == ["~/.claude/settings.json"], (
        f"the hook entry belongs in the agent's settings file: {hook}")
    mcp = [path for path, kinds in preview["files"] if KIND_MCP in kinds]
    assert mcp == ["~/.claude.json"], f"the MCP endpoint entry belongs in the agent's config: {mcp}"

    for way in WAYS_OUT:
        assert way in preview["footer"], f"{way} is not offered: {preview['footer']!r}"


def test_the_preview_comes_before_the_first_write(node, tmp_path):
    """The ordering is the feature: a summary printed after the writes is a receipt, not a warning.

    Evidence that does not depend on timing: a run whose *first* write cannot happen (the state
    directory is a file, so the hook cannot be installed) dies with exit code 2 — and the preview is
    still on stdout. A preview printed after the writes would not be there.
    """
    home = make_home(tmp_path)
    (home / ".misakanet-agent").write_text("not a directory\n", encoding="utf-8")
    result = run_setup(node, home, "--only", "claude")
    assert result.returncode == 2, result.stdout + result.stderr
    preview = parse_preview(result.stdout)
    assert preview["count"] is not None, (
        "the preview must be printed before the writes, not after them:\n" + result.stdout)
    assert preview["count"] > 0, result.stdout


def test_the_preview_and_list_writes_name_the_same_files(node, tmp_path):
    """One source of truth: the summary a user reads and the manifest an operator approves are one list."""
    home = make_home(tmp_path)
    manifest = run_setup(node, home, "--only", "claude", "--list-writes")
    assert manifest.returncode == 0, manifest.stdout + manifest.stderr
    manifest_files = {row.split("\t")[2] for row in manifest.stdout.splitlines() if row.startswith("tier")}

    preview = parse_preview(manifest.stdout)
    assert preview["count"] is None, (
        "--list-writes prints the manifest itself; the summary would be a second list:\n" + manifest.stdout)

    home2 = make_home(tmp_path / "second")
    installed = run_setup(node, home2, "--only", "claude")
    assert installed.returncode == 0, installed.stdout + installed.stderr
    preview_files = {path for path, _kind in parse_preview(installed.stdout)["files"]}
    assert preview_files == manifest_files, (
        f"the preview and the manifest disagree:\n  preview: {sorted(preview_files)}\n"
        f"  manifest: {sorted(manifest_files)}")


# ── the claims the summary makes must be true on disk ──────────────────────────────────────────────

def test_mcp_only_writes_neither_the_rules_block_nor_the_hook(node, tmp_path):
    """`--mcp-only` is "the endpoint only": no rules block, no hook — checked against the disk."""
    home = make_home(tmp_path)
    result = run_setup(node, home, "--only", "claude", "--mcp-only")
    assert result.returncode == 0, result.stdout + result.stderr

    assert not (home / ".claude" / "CLAUDE.md").exists(), "the rules block must not be written"
    assert not (home / ".misakanet-agent" / "hook.mjs").exists(), "the hook must not be written"
    assert not (home / ".misakanet-agent" / "version").exists(), "the version stamp belongs to ③"
    assert (home / ".claude.json").exists(), "the MCP endpoint entry is what --mcp-only does write"

    # …and the summary agrees with the disk: it promises no rules block and no hook.
    preview = parse_preview(result.stdout)
    assert preview["count"] is not None, result.stdout
    kinds = {kind for _path, kinds in preview["files"] for kind in kinds}
    assert KIND_RULES not in kinds, f"--mcp-only must not promise a rules block: {preview['files']}"
    assert KIND_HOOK not in kinds, f"--mcp-only must not promise a hook: {preview['files']}"


def test_the_full_run_does_write_the_rules_block_and_the_hook(node, tmp_path):
    """The other half of the claim above: without --mcp-only, both are written."""
    home = make_home(tmp_path)
    result = run_setup(node, home, "--only", "claude")
    assert result.returncode == 0, result.stdout + result.stderr
    rules = home / ".claude" / "CLAUDE.md"
    assert rules.exists() and "misakanet:start" in rules.read_text(encoding="utf-8"), rules
    assert (home / ".misakanet-agent" / "hook.mjs").is_file()


# ── the existing output contracts the summary must not break ───────────────────────────────────────

def test_silent_keeps_its_empty_log_contract(node, tmp_path):
    """`--silent` is the MDM/GPO form: a clean run is an empty log, and the summary is progress."""
    home = make_home(tmp_path)
    result = run_setup(node, home, "--only", "claude", "--silent")
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "", f"a clean silent run must print nothing:\n{result.stdout}"


def test_the_ci_form_is_still_exactly_one_json_document(node, tmp_path):
    """`--report-json` is what CI collects: one JSON document on stdout, and nothing else."""
    home = make_home(tmp_path)
    result = run_setup(node, home, "--only", "claude", "--report-json")
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["schema"] == "misakanet-setup-report/1", payload
    assert "将修改" not in result.stdout, "the summary belongs to the install run, not to the report"


def test_dry_run_prints_the_summary_and_writes_nothing(node, tmp_path):
    """`--dry-run` says what it would change — the summary is that, one step earlier."""
    home = make_home(tmp_path)
    result = run_setup(node, home, "--only", "claude", "--dry-run")
    assert result.returncode == 0, result.stdout + result.stderr
    preview = parse_preview(result.stdout)
    assert preview["count"] is not None, result.stdout
    assert preview["count"] == len(preview["files"]), result.stdout
    assert not (home / ".claude" / "CLAUDE.md").exists(), "a dry run writes nothing"
    assert not (home / ".misakanet-agent").exists(), "a dry run creates no state"
