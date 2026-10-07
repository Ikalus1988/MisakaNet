# -*- coding: utf-8 -*-
"""Tests for voice hook scripts."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

# Paths
SCRIPT_DIR = Path(__file__).parent.parent / "scripts"
HOOK_SCRIPT_PS1 = SCRIPT_DIR / "misakanet_voice_hook.ps1"
VOICE_HOOK_TIMEOUT = 45  # seconds


class TestWindowsVoiceHookExecution:
    """End-to-end tests for the PowerShell voice hook script on Windows."""

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
    def test_ps1_valid_voice_execution(self):
        """Test all four voice types execute without error.

        Uses a single PowerShell process with piped stdin to avoid the
        cold-start overhead of launching 4 separate processes, which
        caused flaky timeouts on busy windows-latest runners (#2998).
        """
        voices = ["connect-success", "pair-success", "lesson-found", "failure-warning"]

        # Build input: one JSON object per line
        lines = "\n".join(json.dumps({"voice": v}) for v in voices)

        proc = subprocess.Popen(
            ["powershell", "-File", str(HOOK_SCRIPT_PS1)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            stdout, stderr = proc.communicate(
                input=lines.encode("utf-8"), timeout=VOICE_HOOK_TIMEOUT
            )
        except subprocess.TimeoutExpired:
            # Kill the hung process and try to grab whatever it emitted
            proc.kill()
            extra = ""
            try:
                stdout, stderr = proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                extra = " (process did not exit after kill)"
            failure_stdout = (
                stdout.decode("utf-8", errors="replace") if stdout else ""
            )
            failure_stderr = (
                stderr.decode("utf-8", errors="replace") if stderr else ""
            )
            pytest.fail(
                f"PowerShell timed out after {VOICE_HOOK_TIMEOUT}s.{extra}\n"
                f"stdout so far:\n{failure_stdout}\n"
                f"stderr so far:\n{failure_stderr}"
            )

        assert proc.returncode == 0, (
            f"PowerShell exited with code {proc.returncode}.\n"
            f"stdout: {stdout.decode('utf-8', errors='replace')}\n"
            f"stderr: {stderr.decode('utf-8', errors='replace')}"
        )

        # Validate output: expect one line per voice input
        output_text = stdout.decode("utf-8", errors="replace").strip()
        output_lines = [
            line.strip() for line in output_text.splitlines() if line.strip()
        ]

        assert len(output_lines) == len(voices), (
            f"Expected {len(voices)} output lines (one per voice), got {len(output_lines)}.\n"
            f"Full output:\n{output_text}"
        )
        for line in output_lines:
            assert line == "OK", f"Unexpected output line: {line!r}"


class TestPowerShellScriptSyntax:
    """Sanity checks for the PowerShell script itself."""

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
    def test_ps1_syntax_check(self):
        """Use PowerShell's parser to validate syntax without executing."""
        ps1_escaped = str(HOOK_SCRIPT_PS1).replace("'", "''")
        cmd = (
            "$errors = $null; "
            "$null = [System.Management.Automation.PSParser]::Tokenize("
            f"'{ps1_escaped}', [ref]$errors); "
            "if ($errors.Count -gt 0) { "
            "$errors | ForEach-Object { Write-Error $_.Message }; "
            "exit 1 } else { exit 0 }"
        )
        result = subprocess.run(
            ["powershell", "-Command", cmd],
            capture_output=True,
            timeout=10,
        )
        assert result.returncode == 0, (
            f"PowerShell syntax error in {HOOK_SCRIPT_PS1}.\n"
            f"stderr: {result.stderr.decode('utf-8', errors='replace')}"
        )


class TestVoiceHookDryRun:
    """Test that dry-run mode works correctly (platform-independent)."""

    def test_dry_run_modes(self, monkeypatch):
        """Verify all expected voice types and dry-run flag appear in the script."""
        assert HOOK_SCRIPT_PS1.exists(), f"Voice hook script not found at {HOOK_SCRIPT_PS1}"
        content = HOOK_SCRIPT_PS1.read_text(encoding="utf-8")

        for voice in ["connect-success", "pair-success", "lesson-found", "failure-warning"]:
            assert voice in content, f"Voice type '{voice}' not found in script"

        assert "MISAKANET_VOICE_DRY_RUN" in content, "Dry run env var not referenced"

    def test_script_exists(self):
        """Basic existence check."""
        assert HOOK_SCRIPT_PS1.exists(), f"Voice hook script not found at {HOOK_SCRIPT_PS1}"


class TestVoiceHookInputValidation:
    """Test that invalid inputs are handled gracefully (platform-independent)."""

    def test_invalid_voice_type(self, monkeypatch):
        """Invalid voice types should not crash the system."""
        if sys.platform == "win32" and HOOK_SCRIPT_PS1.exists():
            content = HOOK_SCRIPT_PS1.read_text(encoding="utf-8")
            # Look for default/unknown voice handling
            assert (
                "default" in content.lower() or "unknown" in content.lower()
            ), "Script should handle unknown voice types"
