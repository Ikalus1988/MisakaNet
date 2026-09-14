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
import shutil
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


# An unroutable endpoint by default: unit tests must never register a real anonymous node
# on misakanet.org (that is why `test_installing_twice_changes_nothing` was flaky - the
# first run failed to register while the second one succeeded). Tests that DO want the
# network path point at the local stub instead.
OFFLINE_ENDPOINT = "http://127.0.0.1:9/mcp"


def run_installer(home: Path, *args: str, env_extra: dict | None = None) -> subprocess.CompletedProcess:
    env = dict(os.environ, MISAKANET_ENDPOINT=OFFLINE_ENDPOINT)
    env.update(env_extra or {})
    return subprocess.run(
        [sys.executable, str(INSTALLER), "--home", str(home), *args],
        capture_output=True, text=True, env=env,
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
    first = run_hook(payload, "prompt", state)
    assert "已接入失败经验库" in first, "turn 1 announces the install to a user who cannot inspect config"
    for turn in range(2, 20):
        assert run_hook(payload, "prompt", state) == "", f"turn {turn} should be silent"
    at_20 = run_hook(payload, "prompt", state)
    assert "检查点" in at_20 and "20" in at_20
    for _ in range(9):
        assert run_hook(payload, "prompt", state) == ""
    assert "30" in run_hook(payload, "prompt", state)


def test_sessions_are_counted_independently(tmp_path):
    state = tmp_path / "state"
    first_a = run_hook(json.dumps({"session_id": "a"}), "prompt", state)
    run_hook(json.dumps({"session_id": "b"}), "prompt", state)
    # Both are turn 1, so both announce; what matters is that each session has its own count.
    assert "已接入失败经验库" in first_a
    assert json.loads((state / "a.json").read_text())["turn"] == 1
    assert json.loads((state / "b.json").read_text())["turn"] == 1


def test_threshold_is_configurable(tmp_path):
    state = tmp_path / "state"
    payload = json.dumps({"session_id": "s"})
    env = {"MISAKANET_CHECKPOINT_AT": "2", "MISAKANET_CHECKPOINT_EVERY": "0"}
    assert "检查点" not in run_hook(payload, "prompt", state, env)
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
    for payload in ("", "not json", "[1,2,3]"):
        assert run_hook(payload, "prompt", tmp_path / "state") == ""
        assert run_hook(payload, "failure", tmp_path / "state") == ""
    # '{}' = valid empty payload on the default session → turn 1 announces (and must not
    # contain a traceback, because run_hook already asserts exit code 0).
    out = run_hook("{}", "prompt", tmp_path / "state-fresh")
    assert "Traceback" not in out and "已接入" in out

def test_installer_survives_a_non_utf8_console(tmp_path):
    """Windows zh-CN consoles default to GBK; printing the summary used to crash there.

    Verified the hard way: run through cmd.exe on Windows, the installer did all its work
    and then died with UnicodeEncodeError on the tick mark - the worst possible moment,
    because the files were already rewritten.
    """
    home = make_home(tmp_path)
    env = dict(os.environ, PYTHONIOENCODING="gbk")
    result = subprocess.run(
        [sys.executable, str(INSTALLER), "--home", str(home)],
        capture_output=True, text=True, env=env,
    )
    assert result.returncode == 0, f"installer crashed under a GBK console: {result.stderr}"
    assert (home / ".claude" / "CLAUDE.md").exists()


def test_hook_emits_utf8_even_when_the_console_is_gbk(tmp_path):
    """The injected reminder is read as UTF-8 by the agent; wrong bytes = garbled context."""
    state = tmp_path / "state"
    env = {"MISAKANET_CHECKPOINT_AT": "1", "MISAKANET_HOOK_STATE": str(state),
           "PYTHONIOENCODING": "gbk"}
    proc = subprocess.run(
        [sys.executable, str(HOOK), "prompt"],
        input=json.dumps({"session_id": "gbk"}).encode("utf-8"), capture_output=True, env=env,
    )
    assert proc.returncode == 0
    proc.stdout.decode("utf-8")   # must be valid UTF-8, not GBK bytes
    assert "检查点" in proc.stdout.decode("utf-8")

# ── one-click surfaces: --verify, identity provisioning, bootstrap ────
class _McpStub:
    """A local MCP endpoint so the installer's network paths are testable offline.

    Returns a canned tool result: a search hit for misakanet_search, a token for
    misakanet_register. No real network, no real node registrations in tests.
    """

    def __init__(self) -> None:
        import http.server
        import threading

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length) or b"{}")
                tool = payload.get("params", {}).get("name", "")
                if tool == "misakanet_register":
                    result = {"node_id": "MisakaTEST", "token": "mcp_testtoken",
                              "registered_at": "2026-09-13T00:00:00Z", "agent_type": "setup"}
                else:
                    result = {"results": [{"id": "stub-lesson", "type": "lesson"}], "query": "q"}
                body = json.dumps({"jsonrpc": "2.0", "id": 1, "result": {
                    "content": [{"type": "text", "text": json.dumps(result)}],
                    "structuredContent": result}}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):   # keep pytest output clean
                pass

        self.server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/mcp"

    def stop(self) -> None:
        self.server.shutdown()


def test_identity_is_provisioned_so_write_tools_need_no_setup(tmp_path):
    """The step that turns "installed" into "never used" is manual token plumbing."""
    stub = _McpStub()
    try:
        home = make_home(tmp_path)
        env = dict(os.environ, MISAKANET_ENDPOINT=stub.url)
        result = subprocess.run(
            [sys.executable, str(INSTALLER), "--home", str(home), "--only", "claude"],
            capture_output=True, text=True, env=env,
        )
        assert result.returncode == 0, result.stderr
        token = home / ".misakanet-agent" / "token"
        assert token.read_text(encoding="utf-8").strip() == "mcp_testtoken"
        assert (home / ".misakanet-agent" / "client_id").exists(), "client_id must be reused, not regenerated"
        assert (token.stat().st_mode & 0o777) == 0o600, "a token file must not be world-readable"

        # The token DOES belong in the local agent config - that is what lifts the anonymous
        # 5-reads/day limit for a user who will never run `misakanet_register` by hand. What
        # it must not do is show up anywhere else (stdout of the installer, the report URL).
        claude = json.loads((home / ".claude.json").read_text(encoding="utf-8"))
        assert claude["mcpServers"]["misakanet"]["headers"]["Authorization"] == "Bearer mcp_testtoken"
        assert "mcp_testtoken" not in result.stdout, "the installer must not echo the token"
        report = subprocess.run(
            [sys.executable, str(INSTALLER), "--home", str(home), "--report", "x"],
            capture_output=True, text=True, env=env,
        )
        assert "mcp_testtoken" not in report.stdout

        second = subprocess.run(
            [sys.executable, str(INSTALLER), "--home", str(home), "--only", "claude"],
            capture_output=True, text=True, env=env,
        )
        assert "已有 token" in second.stdout, "re-running must not re-register"
    finally:
        stub.stop()


def test_no_register_skips_identity(tmp_path):
    home = make_home(tmp_path)
    result = run_installer(home, "--only", "claude", "--no-register")
    assert result.returncode == 0
    assert not (home / ".misakanet-agent" / "token").exists()


def test_verify_is_ready_only_when_the_wiring_and_endpoint_both_work(tmp_path):
    stub = _McpStub()
    try:
        home = make_home(tmp_path)
        env = dict(os.environ, MISAKANET_ENDPOINT=stub.url,
                   MISAKANET_ENDPOINT_REAL=stub.url)
        before = subprocess.run(
            [sys.executable, str(INSTALLER), "--home", str(home), "--verify"],
            capture_output=True, text=True, env=env,
        )
        assert before.returncode == 1, "an unconfigured home must not report READY"
        assert "NOT READY" in before.stdout
        assert "✗ 缺失" in before.stdout

        subprocess.run([sys.executable, str(INSTALLER), "--home", str(home)],
                       capture_output=True, text=True, env=env, check=True)
        after = subprocess.run(
            [sys.executable, str(INSTALLER), "--home", str(home), "--verify"],
            capture_output=True, text=True, env=env,
        )
        assert after.returncode == 0, after.stdout + after.stderr
        assert "READY" in after.stdout and "端点可达" in after.stdout
    finally:
        stub.stop()


def test_verify_reports_an_unreachable_endpoint_without_crashing(tmp_path):
    home = make_home(tmp_path)
    env = dict(os.environ, MISAKANET_ENDPOINT="http://127.0.0.1:9/mcp")
    result = subprocess.run(
        [sys.executable, str(INSTALLER), "--home", str(home), "--verify"],
        capture_output=True, text=True, env=env,
    )
    assert result.returncode == 1
    assert "端点不可达" in result.stdout


def test_report_url_carries_no_identifying_paths(tmp_path):
    home = make_home(tmp_path)
    result = run_installer(home, "--report", "install failed")
    assert result.returncode == 0
    url = result.stdout.strip().splitlines()[-1]
    assert "issues/new" in url
    assert "install%20failed" in url or "install+failed" in url
    assert str(home) not in url and str(Path.home()) not in url


def test_bootstrap_downloads_and_hands_over(tmp_path):
    """The one-liner must work without a clone: fetch the three files, then run them."""
    bash = shutil.which("bash")
    if not bash:
        pytest.skip("bash unavailable")
    setup_dir = tmp_path / "setup"
    home = make_home(tmp_path)
    env = dict(
        os.environ,
        MISAKANET_RAW_BASE=f"file://{INTEGRATION.parent.parent}",   # repo root
        MISAKANET_SETUP_DIR=str(setup_dir),
        MISAKANET_ENDPOINT="http://127.0.0.1:9/mcp",
    )
    result = subprocess.run(
        [bash, str(INTEGRATION / "bootstrap.sh"), "--home", str(home), "--only", "claude", "--no-register"],
        capture_output=True, text=True, env=env, cwd=str(tmp_path),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    for name in ("install_misakanet_agent.py", "checkpoint_reminder.py", "prompt.md"):
        assert (setup_dir / name).exists(), name
    # the Node hook travels with the bootstrap: CC/Codex users have node, not python
    assert (setup_dir / "checkpoint_reminder.mjs").exists()
    assert "misakanet" in (home / ".claude.json").read_text(encoding="utf-8")

def test_the_hook_prefers_node_because_that_runtime_always_exists(tmp_path):
    """Claude Code and Codex are Node programs; Python may not be installed at all.

    A hook whose command cannot be resolved fails *silently* - the reminder never appears
    and nothing logs an error - so the runtime choice has to be the one that is present.
    """
    import shutil as _shutil

    if not _shutil.which("node"):
        pytest.skip("node unavailable")
    home = make_home(tmp_path)
    run_installer(home, "--only", "claude", "--no-register")
    settings = json.loads((home / ".claude" / "settings.json").read_text(encoding="utf-8"))
    commands = [
        hook["command"]
        for entries in settings["hooks"].values()
        for entry in entries
        for hook in entry.get("hooks", [])
        if "checkpoint_reminder" in hook.get("command", "")
    ]
    assert len(commands) == 2, commands
    for command in commands:
        executable = command.split('"')[1] if command.startswith('"') else command.split()[0]
        assert Path(executable).name.startswith("node"), f"expected node, got {command}"
        script = command.split('"')[3]
        assert script.endswith(".mjs") and Path(script).exists(), command


def test_verify_reports_a_hook_whose_interpreter_is_gone(tmp_path):
    """The silent-failure mode this check exists for: command present, binary missing."""
    home = make_home(tmp_path)
    run_installer(home, "--only", "claude", "--no-register")
    settings_path = home / ".claude" / "settings.json"
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    for entries in settings["hooks"].values():
        for entry in entries:
            for hook in entry.get("hooks", []):
                if "checkpoint_reminder" in hook.get("command", ""):
                    hook["command"] = hook["command"].replace("node", "definitely-not-here", 1)
    settings_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")

    result = run_installer(home, "--verify")
    assert result.returncode == 1
    assert "解释器不存在" in result.stdout

def test_a_run_without_a_token_still_configures_reads(tmp_path):
    """Offline first run: no token, so the config must still be valid and read-only usable."""
    home = make_home(tmp_path)
    result = run_installer(home, "--only", "claude,codex")
    assert result.returncode == 0
    claude = json.loads((home / ".claude.json").read_text(encoding="utf-8"))
    assert claude["mcpServers"]["misakanet"]["url"] == "https://misakanet.org/mcp"
    assert "headers" not in claude["mcpServers"]["misakanet"], "no token, no header"


def test_codex_config_carries_the_token_as_http_headers(tmp_path, monkeypatch):
    """`bearer_token_env_var` needs the user to export a variable; this user never will."""
    tomllib = pytest.importorskip("tomllib")
    home = make_home(tmp_path)
    (home / ".misakanet-agent").mkdir(exist_ok=True)
    (home / ".misakanet-agent" / "token").write_text("mcp_codex_token", encoding="utf-8")
    run_installer(home, "--only", "codex", "--no-register")

    data = tomllib.loads((home / ".codex" / "config.toml").read_text(encoding="utf-8"))
    table = data["mcp_servers"]["misakanet"]
    assert table["http_headers"]["Authorization"] == "Bearer mcp_codex_token"
    assert "bearer_token_env_var" not in table

def test_a_file_token_is_withheld_from_a_custom_endpoint(tmp_path):
    """Same policy as the Node hook/CLI, and the property CodeQL alerts are about.

    A token this code found on disk must only ever reach the canonical origin - otherwise a
    single environment variable redirects the secret. An exported MISAKANET_TOKEN is the
    user's explicit choice and is honoured anywhere (self-hosting).
    """
    import http.server
    import threading

    seen: list[str | None] = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            seen.append(self.headers.get("Authorization"))
            body = json.dumps({"jsonrpc": "2.0", "id": 1, "result": {
                "content": [{"type": "text", "text": json.dumps({"results": []})}],
                "structuredContent": {"results": []}}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}/mcp"
    import uuid

    # Derived at runtime: a literal that looks like a credential trips secret scanners even
    # when it is obviously fake (the repo has been bitten by that three times).
    file_token = f"file-{uuid.uuid4()}"
    exported_token = f"exported-{uuid.uuid4()}"
    token_file = tmp_path / "token"
    token_file.write_text(file_token, encoding="utf-8")
    try:
        env = {
            "MISAKANET_HOOK_FETCH": "1", "MISAKANET_ENDPOINT": url,
            "MISAKANET_TOKEN_FILE": str(token_file), "MISAKANET_HOOK_STATE": str(tmp_path / "st"),
        }
        run_hook(json.dumps({"error": "exit code 137"}), "failure", tmp_path / "st", env)
        assert seen, "the fetch must have happened (MISAKANET_HOOK_FETCH=1)"
        assert seen[0] is None, f"file token leaked to a custom endpoint: {seen[0]}"

        seen.clear()
        env["MISAKANET_TOKEN"] = exported_token
        run_hook(json.dumps({"error": "exit code 137"}), "failure", tmp_path / "st2", env)
        assert seen and seen[0] == f"Bearer {exported_token}", seen
    finally:
        server.shutdown()
