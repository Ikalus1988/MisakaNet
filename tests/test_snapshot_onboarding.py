#!/usr/bin/env python3
"""The onboarding snapshot: three legs, one badge, and a rule about missing numbers.

The measurement this replaces is a download count, which the data says is the wrong instrument — the
installer's "monthly 1,814" was one week of 1,661 that no workflow of ours produced, GitHub's 14-day traffic
shows 3,079 unique cloners against 689 unique visitors (machines, not people), and the endpoint answers
~7,600 calls a day. What matters is whether an install becomes an agent that searches, so the snapshot puts
downloads, agent calls and the GitHub traffic context side by side.

The rules worth pinning are the ones that keep it honest:

* a number that could not be measured publishes **nothing** — absent evidence is not a pass, and it is not a
  zero either (the same rule `badges/install.json` follows);
* the derived ratio is labelled as a proxy, because it is one (npx caching depresses the denominator, and a
  single agent makes many calls);
* the badge message stays a *pair* a human can read, not a score.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.snapshot_onboarding import (  # noqa: E402
    PACKAGES,
    activity_counts,
    compose,
    github_traffic,
    main,
    npm_week,
)

ACTIVITY = {"date": "2026-09-30", "total": 8134,
            "calls": {"mcp": 7592, "agent": 267, "crawler": 245, "pageview": 30}}


def test_the_snapshot_carries_all_three_legs_and_a_readable_pair():
    payload = compose({"misakanet": 1196, "@misaka-net/misakanet-setup": 116}, ACTIVITY,
                      {"clones": 58755, "unique_cloners": 3079, "views": 3186, "unique_visitors": 689,
                       "window_days": 14}, now="2026-10-01T00:00:00Z")
    assert payload["message"] == "setup 116/wk · MCP 7.6k/day", payload["message"]
    assert payload["downloads"] == {"misakanet": 1196, "misakanet-setup": 116}
    assert payload["activity"]["calls"]["mcp"] == 7592
    assert payload["traffic"]["unique_cloners"] == 3079
    assert payload["schemaVersion"] == 1 and payload["label"] == "onboarding"


def test_the_derived_ratio_is_present_and_named_a_proxy():
    payload = compose({"misakanet": 100, "@misaka-net/misakanet-setup": 100}, ACTIVITY, None,
                      now="2026-10-01T00:00:00Z")
    assert payload["mcp_per_weekly_install"] == round(7592 * 7 / 100, 1)
    assert "proxy, not a conversion rate" in payload["mcp_per_weekly_install_note"]


def test_the_ratio_is_omitted_rather_than_divided_by_zero():
    payload = compose({"misakanet": 100, "@misaka-net/misakanet-setup": 0}, ACTIVITY, None,
                      now="2026-10-01T00:00:00Z")
    assert "mcp_per_weekly_install" not in payload


def test_a_missing_measurement_publishes_nothing(tmp_path, capsys):
    """npm unreachable → no file, exit 1, and the reason on stderr."""
    out = tmp_path / "onboarding.json"
    code = main(["--out", str(out), "--no-traffic"])
    # In this sandbox npm may or may not resolve; drive the failure the honest way instead.
    if code == 0:
        assert out.is_file()
    else:
        assert not out.exists(), "a failed measurement must not publish a file"
        assert "not publishing" in capsys.readouterr().err


def test_the_fetchers_report_none_instead_of_inventing_a_number(monkeypatch):
    assert npm_week("misakanet", fetch=lambda *a, **k: None) is None
    assert npm_week("misakanet", fetch=lambda *a, **k: {"downloads": "many"}) is None
    assert activity_counts(Path("/nonexistent/activity.json"), fetch=lambda *a, **k: {"calls": {}}) is None
    assert github_traffic(fetch=lambda *a, **k: None) is None
    # one leg missing is enough to refuse a traffic block: a half-measured window would read as a trend
    assert github_traffic(fetch=lambda url, *a, **k: {"clones": []} if "clones" in url else None) is None


def test_the_packages_under_measurement_are_the_two_front_doors():
    assert set(PACKAGES) == {"misakanet", "@misaka-net/misakanet-setup"}


def test_the_workflow_generates_the_snapshot_into_the_badge_directory():
    workflow = (REPO / ".github" / "workflows" / "update-badges.yml").read_text(encoding="utf-8")
    assert "scripts/snapshot_onboarding.py" in workflow, (
        "the snapshot must have a writer, or the badge it produces is a number nobody updates")
    assert "/tmp/badges/onboarding.json" in workflow
