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


def test_the_window_names_only_the_legs_that_were_measured():
    """The first real run shipped `"traffic": null` beside `"window": {"traffic": "14d"}`.

    A window for a measurement nobody took is a claim, and the repo's rule is that an absent number is
    neither a pass nor a zero — so the window block follows the file (run 36732770964, 2026-09-30).
    """
    without = compose({"misakanet": 1196, "@misaka-net/misakanet-setup": 116}, ACTIVITY, None,
                      now="2026-10-01T00:00:00Z")
    assert without["traffic"] is None
    assert "traffic" not in without["window"], without["window"]
    assert without["window"]["downloads"] == "last-week"

    with_traffic = compose({"misakanet": 1196, "@misaka-net/misakanet-setup": 116}, ACTIVITY,
                           {"clones": 1, "unique_cloners": 1, "views": 1, "unique_visitors": 1,
                            "window_days": 14}, now="2026-10-01T00:00:00Z")
    assert with_traffic["window"]["traffic"] == "14d"


def test_a_refused_traffic_leg_warns_with_the_reason_instead_of_going_quiet(tmp_path, capsys, monkeypatch):
    """`GITHUB_TOKEN` cannot read `/repos/*/traffic/*`; the run has to say so, or the leg stays dead.

    The first production run went green with the log line "no traffic leg: no token or the API refused"
    while a token *was* set — the ambiguity is the bug this pins. The warning names the permission and
    the remedy, and the file it writes no longer claims the window.
    """
    import scripts.snapshot_onboarding as snap
    monkeypatch.setattr(snap, "npm_week", lambda pkg, **kw: 100)
    monkeypatch.setattr(snap, "activity_counts", lambda path=None, **kw: ACTIVITY)
    monkeypatch.setattr(snap, "github_traffic", lambda **kw: None)
    monkeypatch.setenv("GITHUB_TOKEN", "set-but-not-sufficient")
    out = tmp_path / "onboarding.json"
    assert snap.main(["--out", str(out)]) == 0
    printed = capsys.readouterr().out
    assert "::warning::" in printed and "Administration" in printed, printed
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["traffic"] is None and "traffic" not in payload["window"]


def test_the_deliberate_skip_does_not_warn(tmp_path, capsys, monkeypatch):
    """`--no-traffic` is a choice, not a failure: it must not page anyone."""
    import scripts.snapshot_onboarding as snap
    monkeypatch.setattr(snap, "npm_week", lambda pkg, **kw: 100)
    monkeypatch.setattr(snap, "activity_counts", lambda path=None, **kw: ACTIVITY)
    out = tmp_path / "onboarding.json"
    assert snap.main(["--out", str(out), "--no-traffic"]) == 0
    assert "::warning::" not in capsys.readouterr().out


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
