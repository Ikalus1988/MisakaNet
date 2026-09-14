"""Tests for integrations/agent-autostart (installer + checkpoint hook).

These exist because the first version of the installer was wrong in three ways that
only a test could see:

  * the injected rules block contains literal ``\\n`` (it documents the intake call), and
    ``re.sub`` interpreted those escapes — so every run rewrote the file (idempotency
    broken, silently);
  * the checkpoint hook searched for the *command* of a failed tool call rather than its
    error text, which retrieves nothing from the corpus;
  * the Codex TOML blocks used prefix-overlapping markers (``misakanet:end`` is a prefix
    of ``misakanet-top:end``), so spanning the second block deleted it on install.

Everything here runs against a temporary HOME, so the developer's real agent configs are
never touched.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
INTEGRATION = REPO / "integrations" / "agent-autostart"
INSTALLER = INTEGRATION / "install_misakanet_agent.py"
HOOK = INTEGRATION / "checkpoint_reminder.py"

pytestmark = pytest.mark.skipif(
    not INSTALLER.exists(), reason="integrations/agent-autostart is not present"
)

SEED_CLAUDE_JSON = {"mcpServers": {"cloudflare": {"type": "http", "url": "https://x"}}}
SEED_SETTINGS = {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo hi"}]}]}}
SEED_CODEX_TOML = 'model = "gpt-5"\n\n[mcp_servers.context7]\ncommand = "npx"\n'


def make_home(tmp_path: Path) -> Path:
    home = tmp_path / "home"
    for sub in (".claude", ".codex", ".hermes", ".dsh"):
        (home / sub).mkdir(parents=True, exist_ok=True)
    (home / ".claude.json").write_text(json.dumps(SEED_CLAUDE_JSON), encoding="utf-8")
    (home / ".claude" / "settings.json").write_text(json.dumps(SEED_SETTINGS), encoding="utf-8")
    (home / ".codex" / "config.toml").write_text(SEED_CODEX_TOML, encoding="utf-8")
    (home / ".hermes" / "config.yaml").write_text("name: hermes\n", encoding="utf-8")
    return home


def run_installer(home: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(INSTALLER), "--home", str(home), *args],
        capture_output=True, text=True,
    )


def snapshot(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): p.read_text(encoding="utf-8")
        for p in sorted(root.rglob("*")) if p.is_file()
    }


# ── installer ───────────────────────────────────────────────────────
def test_install_wires_every_detected_agent(tmp_path):
    home = make_home(tmp_path)
    result = run_installer(home)
    assert result.returncode == 0, result.stdout + result.stderr

    claude = json.loads((home / ".claude.json").read_text(encoding="utf-8"))
    assert claude["mcpServers"]["misakanet"] == {"type": "http", "url": "https://misakanet.org/mcp"}
    assert "cloudflare" in claude["mcpServers"], "existing servers must survive"

    settings = json.loads((home / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert "Stop" in settings["hooks"], "the user's own hooks must survive"
    flat = json.dumps(settings["hooks"])
    assert "checkpoint_reminder" in flat and "UserPromptSubmit" in settings["hooks"]
    assert "PostToolUseFailure" in settings["hooks"]

    for rel in (".claude/CLAUDE.md", ".codex/AGENTS.md", ".hermes/SOUL.md"):
        text = (home / rel).read_text(encoding="utf-8")
        assert "misakanet:start" in text and "misakanet:end" in text, rel
        assert "misakanet_search" in text, rel
    assert (home / ".agents" / "skills" / "misakanet" / "SKILL.md").exists()


def test_codex_toml_stays_parseable_and_keeps_the_top_level_key_at_top(tmp_path):
    tomllib = pytest.importorskip("tomllib")
    home = make_home(tmp_path)
    run_installer(home, "--only", "codex")

    data = tomllib.loads((home / ".codex" / "config.toml").read_text(encoding="utf-8"))
    assert data["experimental_use_rmcp_client"] is True, (
        "a top-level key placed after a [table] would be scoped to that table")
    assert data["mcp_servers"]["misakanet"]["url"] == "https://misakanet.org/mcp"
    assert data["mcp_servers"]["misakanet"]["type"] == "streamable-http"
    assert "context7" in data["mcp_servers"], "existing servers must survive"
    assert data["model"] == "gpt-5"


def test_installing_twice_changes_nothing(tmp_path):
    home = make_home(tmp_path)
    run_installer(home)
    first = snapshot(home)
    result = run_installer(home)
    assert result.returncode == 0
    assert snapshot(home) == first, "second run must be a no-op (idempotency)"


def test_the_injected_block_keeps_literal_backslash_n(tmp_path):
    """The block documents `problem="## Problem\\n…"`; escapes must stay literal."""
    home = make_home(tmp_path)
    run_installer(home, "--only", "claude")
    text = (home / ".claude" / "CLAUDE.md").read_text(encoding="utf-8")
    assert 'problem="## Problem\\n' in text, (
        "re.sub() rewrote the escapes into real newlines — pass a lambda replacement")


def test_backups_are_written_before_rewriting(tmp_path):
    home = make_home(tmp_path)
    run_installer(home, "--only", "claude")
    assert (home / ".claude.json.misakanet.bak").read_text(encoding="utf-8") == json.dumps(SEED_CLAUDE_JSON)
    assert (home / ".claude" / "settings.json.misakanet.bak").exists()


def test_uninstall_restores_the_original_state(tmp_path):
    home = make_home(tmp_path)
    run_installer(home)
    result = run_installer(home, "--uninstall")
    assert result.returncode == 0

    claude = json.loads((home / ".claude.json").read_text(encoding="utf-8"))
    assert "misakanet" not in claude["mcpServers"]
    assert claude["mcpServers"] == SEED_CLAUDE_JSON["mcpServers"]

    settings = json.loads((home / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert settings["hooks"] == SEED_SETTINGS["hooks"], "empty event keys must not be left behind"

    assert "misakanet" not in (home / ".codex" / "config.toml").read_text(encoding="utf-8")
    assert not (home / ".claude" / "CLAUDE.md").exists(), "a file created only for our block should go"


def test_dry_run_writes_nothing(tmp_path):
    home = make_home(tmp_path)
    before = snapshot(home)
    result = run_installer(home, "--dry-run")
    assert result.returncode == 0
    assert snapshot(home) == before


def test_only_skips_absent_agents(tmp_path):
    home = tmp_path / "bare"
    home.mkdir()
    result = run_installer(home)
    assert result.returncode == 0
    assert "未检测到" in result.stdout
    assert not any(home.rglob("*"))


# ── checkpoint hook ─────────────────────────────────────────────────
def run_hook(payload: str, mode: str, state: Path, env_extra: dict | None = None) -> str:
    env = dict(os.environ)
    env["MISAKANET_HOOK_STATE"] = str(state)
    env.update(env_extra or {})
    proc = subprocess.run(
        [sys.executable, str(HOOK), mode], input=payload, capture_output=True, text=True, env=env,
    )
    assert proc.returncode == 0, f"hooks must never break the session: {proc.stderr}"
    return proc.stdout


def test_checkpoint_fires_at_the_threshold_and_every_interval(tmp_path):
    state = tmp_path / "state"
    payload = json.dumps({"session_id": "s1"})
    for turn in range(1, 20):
        assert run_hook(payload, "prompt", state) == "", f"turn {turn} should be silent"
    at_20 = run_hook(payload, "prompt", state)
    assert "检查点" in at_20 and "20" in at_20
    for _ in range(9):
        assert run_hook(payload, "prompt", state) == ""
    assert "30" in run_hook(payload, "prompt", state)


def test_sessions_are_counted_independently(tmp_path):
    state = tmp_path / "state"
    assert run_hook(json.dumps({"session_id": "a"}), "prompt", state) == ""
    assert run_hook(json.dumps({"session_id": "b"}), "prompt", state) == ""
    assert json.loads((state / "a.json").read_text())["turn"] == 1
    assert json.loads((state / "b.json").read_text())["turn"] == 1


def test_threshold_is_configurable(tmp_path):
    state = tmp_path / "state"
    payload = json.dumps({"session_id": "s"})
    env = {"MISAKANET_CHECKPOINT_AT": "2", "MISAKANET_CHECKPOINT_EVERY": "0"}
    assert run_hook(payload, "prompt", state, env) == ""
    assert "检查点" in run_hook(payload, "prompt", state, env)


def test_failure_mode_prefers_error_text_over_the_command(tmp_path):
    """The error fragment is what the corpus is indexed by; the command retrieves nothing."""
    payload = json.dumps({
        "tool_input": {"command": "docker compose up"},
        "error": "Error response from daemon: exit code 137",
    })
    out = run_hook(payload, "failure", tmp_path / "state")
    assert "exit code 137" in out
    assert "docker compose up" not in out


def test_failure_mode_falls_back_to_the_command(tmp_path):
    out = run_hook(json.dumps({"tool_input": {"command": "npm run build"}}), "failure", tmp_path / "state")
    assert "npm run build" in out


def test_hook_survives_junk_input(tmp_path):
    for payload in ("", "not json", "{}", "[1,2,3]"):
        assert run_hook(payload, "prompt", tmp_path / "state") == ""
        assert run_hook(payload, "failure", tmp_path / "state") == ""
