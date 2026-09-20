#!/usr/bin/env python3
"""The integration docs are the product's front door; three kinds of rot are gated here.

1. **`mcpServers` in the wrong file.** Claude Code reads MCP servers from `~/.claude.json`
   (local/user scope) and `.mcp.json` at the project root (project scope). `settings.json` holds
   hooks, permissions and env. Five documents — including the canonical `docs/mcp.md` — told readers
   to put `mcpServers` in `settings.json`, which contradicts both the official scope table
   (https://docs.claude.com/en/docs/claude-code/mcp) and this repository's own installer, which
   writes `~/.claude.json`. The symptom for a reader is an empty `/mcp` panel and no error.
2. **Agent lists that drift from capability.** The README describes which agents the installer
   manages; the installer's real target list is the `AGENTS` array in
   `packages/misakanet-setup/bin/misakanet-setup.mjs` (and its `--only` help text). A previous README
   sentence put Claude Code and Codex under "(MCP)" while calling only Hermes/OpenClaw/codewhale
   installer-managed — the opposite of the truth.
3. **Links inside `docs/integrations/`.** `status.md` pointed at its own evidence file with a path
   that did not exist (`agent-integration-matrix-2026-09-16.md` instead of
   `../field-reports/agent-integration-matrix-2026-09-16.md`), and the index linked
   `continue/README.md` when the file is `continue.md`. A reader following the "evidence" link got a
   404, which is worse than no link: it is the one place the table asks you to verify it.
"""
from __future__ import annotations

import re
import urllib.parse
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SETUP = REPO / "packages" / "misakanet-setup" / "bin" / "misakanet-setup.mjs"
DOCS = sorted((REPO / "docs").rglob("*.md")) + sorted(REPO.glob("*.md"))


# What `--only` accepts, spelled the way a human writes it in the docs.
AGENT_DISPLAY = {
    "claude": "Claude Code",
    "codex": "Codex",
    "hermes": "Hermes",
    "openclaw": "OpenClaw",
    "codewhale": "codewhale",
}


def installer_targets() -> list[str]:
    text = SETUP.read_text(encoding="utf-8")
    match = re.search(r"^const AGENTS = \[([^\]]+)\]", text, re.M)
    assert match, "the installer's AGENTS array moved; update this gate rather than deleting it"
    return re.findall(r"'([^']+)'", match.group(1))


def _json_blocks_with_mcp_servers(path: Path):
    """(line number, the preceding prose) for every ```json block that defines mcpServers."""
    lines = path.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        if not line.strip().startswith("```json"):
            continue
        block = []
        for follow in lines[i + 1:]:
            if follow.strip().startswith("```"):
                break
            block.append(follow)
        if not any('"mcpServers"' in b for b in block):
            continue
        yield i + 1, " ".join(lines[max(0, i - 4):i]).lower()


def test_no_doc_tells_claude_code_to_use_settings_json_for_mcp_servers():
    problems = []
    for path in DOCS:
        for line_no, prose in _json_blocks_with_mcp_servers(path):
            if "settings.json" not in prose:
                continue
            # Claude Desktop's own file legitimately contains mcpServers; `settings.json` does not.
            if "claude_desktop_config" in prose:
                continue
            # A sentence that *warns* against the wrong file is the fix, not the bug — the docs that
            # explain the trap necessarily name `settings.json` next to an `mcpServers` block. The
            # gap must allow dots, because the very path being warned about is `.claude/settings.json`.
            if re.search(r"(not|never|不是|不要|别)[^\n]{0,60}settings\.json", prose):
                continue
            problems.append(f"{path.relative_to(REPO)}:{line_no}")
    assert not problems, (
        "these docs put `mcpServers` in a settings.json: Claude Code reads MCP servers from "
        "`~/.claude.json` (local/user) or `.mcp.json` (project), and settings.json is hooks + "
        "permissions. A reader following this gets an empty /mcp panel:\n  " + "\n  ".join(problems)
    )


def test_the_readmes_installer_managed_list_equals_the_installers_targets():
    """The README's grouping is the public claim; AGENTS is the capability. They must agree."""
    text = (REPO / "README.md").read_text(encoding="utf-8")
    row = next(
        (l for l in text.splitlines() if l.startswith("| Installer-managed |")), None
    )
    assert row, (
        "README.md must keep a table row starting `| Installer-managed |` listing the agents "
        "`npx @misaka-net/misakanet-setup` configures — this gate reads that row"
    )
    claimed_cell = row.split("|")[2]
    claimed = {part.strip().lower() for part in claimed_cell.split("·") if part.strip()}
    expected = {AGENT_DISPLAY[a].lower() for a in installer_targets()}
    assert claimed == expected, (
        f"README says the installer manages {sorted(claimed)} but the installer's AGENTS are "
        f"{sorted(expected)} (packages/misakanet-setup/bin/misakanet-setup.mjs)"
    )


def test_relative_links_across_all_docs_resolve():
    problems = []
    for path in DOCS:
        text = path.read_text(encoding="utf-8")
        for target in re.findall(r"\]\((?!https?:|mailto:|#)([^)\s]+)", text):
            target = urllib.parse.unquote(target).split("#")[0]
            if not target:
                continue
            resolved = (path.parent / target).resolve()
            if not resolved.exists():
                problems.append(f"{path.relative_to(REPO)} → {target}")
    assert not problems, (
        "relative links across all docs must resolve (an evidence link that 404s is worse "
        "than no link):\n  " + "\n  ".join(problems)
    )


def test_relative_link_checker_handles_url_encoding_and_fragments(tmp_path):
    doc = tmp_path / "test.md"
    target = tmp_path / "my file.md"
    target.write_text("# Target", encoding="utf-8")
    doc.write_text("[link](my%20file.md#section)", encoding="utf-8")

    text = doc.read_text(encoding="utf-8")
    targets = re.findall(r"\]\((?!https?:|mailto:|#)([^)\s]+)", text)
    assert len(targets) == 1
    unquoted = urllib.parse.unquote(targets[0]).split("#")[0]
    resolved = (doc.parent / unquoted).resolve()
    assert resolved.exists()


def test_relative_link_checker_fails_on_broken_link(tmp_path):
    doc = tmp_path / "test.md"
    doc.write_text("[broken](non_existent_file.md)", encoding="utf-8")

    text = doc.read_text(encoding="utf-8")
    targets = re.findall(r"\]\((?!https?:|mailto:|#)([^)\s]+)", text)
    assert len(targets) == 1
    unquoted = urllib.parse.unquote(targets[0]).split("#")[0]
    resolved = (doc.parent / unquoted).resolve()
    assert not resolved.exists()

