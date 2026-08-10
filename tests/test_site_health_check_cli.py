#!/usr/bin/env python3
"""CLI-mode tests for the site health checker (Issue #914).

The pure-function tests in test_site_health_check.py cover run_checks /
render_markdown, but the CLI wiring (--json, --write, --strict exit codes)
was untested. These tests exercise main() with a fake fetcher so the
behaviour is deterministic and network-free.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.site_health_check import (  # noqa: E402
    REPO,
    main,
    run_checks,
)

from test_site_health_check import BODIES, fake_fetch  # noqa: E402


def _run_main(args, monkeypatch, capsys):
    """Run main() with the fake fetcher injected and return its exit code."""
    import scripts.site_health_check as shc

    monkeypatch.setattr(sys, "argv", ["site_health_check.py", *args])
    monkeypatch.setattr(shc, "run_checks", lambda base, timeout=20: run_checks(
        base, fetch=fake_fetch(), timeout=timeout
    ))
    return main()


def test_default_mode_prints_markdown(monkeypatch, capsys):
    code = _run_main(["--base-url", "https://example.test"], monkeypatch, capsys)
    out = capsys.readouterr().out
    assert code == 0
    assert out.startswith("# Site Health Snapshot — ")
    assert "| Endpoint | Status | Notes |" in out


def test_json_mode_prints_machine_readable_report(monkeypatch, capsys):
    code = _run_main(["--base-url", "https://example.test", "--json"], monkeypatch, capsys)
    out = capsys.readouterr().out
    assert code == 0
    report = json.loads(out)  # must be valid JSON
    assert report["healthy"] is True
    assert "checks" in report and "warnings" in report


def test_strict_mode_exits_zero_when_healthy(monkeypatch, capsys):
    code = _run_main(["--base-url", "https://example.test", "--strict"], monkeypatch, capsys)
    assert code == 0


def test_strict_mode_exits_one_on_warnings(monkeypatch, capsys):
    import scripts.site_health_check as shc

    def degraded(base, timeout=20):
        report = run_checks(base, fetch=fake_fetch(), timeout=timeout)
        report["warnings"] = [{"label": "x", "notes": "boom"}]
        report["healthy"] = False
        return report

    monkeypatch.setattr(sys, "argv", ["site_health_check.py", "--base-url", "https://example.test", "--strict"])
    monkeypatch.setattr(shc, "run_checks", degraded)
    assert main() == 1


def test_write_mode_creates_snapshot_file(monkeypatch, capsys, tmp_path):
    import scripts.site_health_check as shc

    monkeypatch.setattr(sys, "argv", ["site_health_check.py", "--base-url", "https://example.test", "--write"])
    monkeypatch.setattr(shc, "REPO", tmp_path)
    monkeypatch.setattr(shc, "run_checks", lambda base, timeout=20: run_checks(
        base, fetch=fake_fetch(), timeout=timeout
    ))
    code = main()
    assert code == 0
    snapshot = tmp_path / "docs" / "maintainer" / "site-health-2026-08-10.md"
    assert snapshot.exists()
    text = snapshot.read_text(encoding="utf-8")
    assert "| Endpoint | Status | Notes |" in text


def test_write_mode_reports_the_written_path(monkeypatch, capsys, tmp_path):
    import scripts.site_health_check as shc

    monkeypatch.setattr(sys, "argv", ["site_health_check.py", "--base-url", "https://example.test", "--write"])
    monkeypatch.setattr(shc, "REPO", tmp_path)
    monkeypatch.setattr(shc, "run_checks", lambda base, timeout=20: run_checks(
        base, fetch=fake_fetch(), timeout=timeout
    ))
    main()
    assert "Wrote" in capsys.readouterr().err
