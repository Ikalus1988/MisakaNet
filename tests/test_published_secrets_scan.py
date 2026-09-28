#!/usr/bin/env python3
"""The published-prose credential gate, and the two ways it has to be right (#1982).

Both directions matter and only one of them is obvious:

* **it must catch a token** — a docs-only PR (#1982) was one merge away from publishing two live-looking
  node tokens in its smoke reports, and no scanner in this repository read `docs/`;
* **it must not catch the corpus** — this repository is full of `mcp_…` strings that are tool names
  (`mcp__misakanet__search`) or placeholders. A gate that flags those is red on every PR, gets muted,
  and then the first direction stops mattering.

The threshold that separates them was measured, not chosen: the two strings from #1982 have 25 and 26
distinct characters; every other `mcp_…` string in the tree tops out at 15. `MIN_DISTINCT` is 20, and
`test_the_threshold_sits_in_the_measured_gap` fails if it ever drifts out of that gap.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.check_published_secrets import (  # noqa: E402
    MIN_DISTINCT,
    RULES,
    candidate_files,
    looks_like_a_credential,
    main,
    scan_file,
)

WORKFLOW = REPO / ".github" / "workflows" / "pr-checks.yml"
MCP_RULE = RULES[0]

# Bodies of the same *shape* as the leaked ones, generated here rather than copied: writing the real
# strings into this file would do the very thing the gate exists to prevent, and they are already public
# in #1982's diff. Generated deterministically rather than typed, because hand-counted fixtures were
# wrong twice while writing this file — and the length matters: 32 characters is what
# `misakanet_register` issues. Real tokens show 25–26 distinct characters; these show 32, i.e. at least
# as random, so a rule that catches them catches the real ones too.
_TOKEN_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"


def _token_shaped(start: int) -> str:
    body = "".join(_TOKEN_ALPHABET[(start + i * 7) % len(_TOKEN_ALPHABET)] for i in range(32))
    assert len(body) == 32 and len(set(body)) == 32, body
    return body


TOKEN_SHAPED = [_token_shaped(0), _token_shaped(23)]
# Everything the real corpus contains, by measurement.
PLACEHOLDER_SHAPED = [
    "x" * 32,
    "_misakanet__misakanet__search"[:32],
    "misakanet_misakanet_misakanet_mis",
    "YOUR_TOKEN_HERE_YOUR_TOKEN_HERE_Y",
]


def _rule_flags(body: str) -> bool:
    return looks_like_a_credential(MCP_RULE.kind, body, MCP_RULE)


# ── direction 1: it catches a token ─────────────────────────────────────────────────
def test_a_token_shaped_body_is_flagged():
    for body in TOKEN_SHAPED:
        assert len(body) == 32, body
        assert _rule_flags(body), f"{len(set(body))} distinct characters went unflagged"


def test_a_flagged_body_anywhere_in_a_file_is_found(tmp_path):
    """The scanner reads lines, so the finding must survive the `Authorization: Bearer …` wrapper."""
    path = tmp_path / "report.md"
    path.write_text('    "Authorization": "Bearer mcp_' + TOKEN_SHAPED[0] + '",\n', encoding="utf-8")
    assert scan_file(path) == [(1, MCP_RULE.kind)]


# ── direction 2: it does not catch the corpus ───────────────────────────────────────
def test_the_repositorys_own_prose_is_clean():
    """This is the direction that keeps the gate alive: main must be green, or every PR is red."""
    files = candidate_files()
    assert len(files) > 200, f"only {len(files)} files scanned — check SCAN_DIRS/ROOT_FILES"
    findings = [(str(p.relative_to(REPO)), n, kind) for p in files for n, kind in scan_file(p)]
    assert findings == [], findings


def test_the_surface_the_leak_was_on_is_actually_scanned():
    """A file count is not coverage: `docs/` could drop out of `SCAN_DIRS` with the suite still green,
    because lessons/ alone is >200 files and the count assertion above would not notice. #1982's tokens
    were in `docs/field-reports/`, so that directory is the thing this scanner exists for — the first
    version of this file proved only "we scanned a lot of files"."""
    scanned = {p.as_posix() for p in candidate_files()}
    assert any("/docs/field-reports/" in f for f in scanned), (
        "docs/field-reports/ is not scanned — that is exactly where #1982's two tokens were"
    )
    assert any("/docs/integrations/" in f for f in scanned), "docs/integrations/ is not scanned"
    assert any("/lessons/" in f for f in scanned), "lessons/ (published knowledge) is not scanned"
    for name in ("README.md", "AGENTS.md"):
        assert any(f.endswith("/" + name) for f in scanned), f"{name} is not scanned"


def test_placeholders_and_tool_names_are_not_flagged():
    for body in PLACEHOLDER_SHAPED:
        assert not _rule_flags(body), f"{body!r} ({len(set(body))} distinct) was flagged"


def test_a_high_entropy_tool_name_is_excluded_by_the_underscore_rule():
    """Rule 1, made load-bearing.

    Every real tool name in the tree repeats a small alphabet (≤15 distinct), so rule 3 would exclude
    them anyway — the redundancy is deliberate, and only a *high-entropy* `mcp__…` body shows rule 1
    doing anything. Without this test the underscore rule could be deleted with the suite still green.
    """
    body = "_" + _TOKEN_ALPHABET[:31]        # 32 characters, 32 distinct, and it starts with `_`
    assert len(body) == 32 and len(set(body)) == 32
    assert _rule_flags(body[1:]), "the fixture stopped being high-entropy"
    assert not _rule_flags(body), "a `mcp__…` name was treated as a token"


def test_the_threshold_sits_in_the_measured_gap():
    """Measured 2026-09-25: leaked bodies 25/26 distinct, everything legitimate ≤ 15."""
    assert all(len(set(b)) >= 25 for b in TOKEN_SHAPED), "the fixtures stopped being token-shaped"
    assert max(len(set(b)) for b in PLACEHOLDER_SHAPED) <= 15
    assert 15 < MIN_DISTINCT <= 25, (
        f"MIN_DISTINCT={MIN_DISTINCT} is not between the two measured populations — either the gate "
        "starts missing tokens or it starts flagging tool names"
    )


def test_without_the_entropy_gate_a_placeholder_would_be_flagged():
    """Rule 3's only job, stated honestly.

    Measured 2026-09-25: with the entropy gate switched off, the repository's own prose produces **0**
    findings — the tool-name exclusion and the exact-32-character test already cover everything in the
    tree, so this cannot be demonstrated on the corpus. The first version of this test claimed it could,
    and failed, correctly. What the gate is for is the placeholder somebody writes tomorrow.
    """
    from scripts.check_published_secrets import Rule

    ungated = Rule(MCP_RULE.kind, MCP_RULE.pattern, MCP_RULE.distinct_after, 1)
    match = ungated.pattern.search("mcp_" + "x" * 32)
    assert match, "the fixture stopped matching the shape rule"
    assert looks_like_a_credential(ungated.kind, match.group(1), ungated), "the ungated rule missed it"
    assert not _rule_flags(match.group(1)), "the gated rule flagged a placeholder"


# ── what it prints, and how it exits ────────────────────────────────────────────────
def test_a_finding_never_echoes_the_credential(tmp_path, monkeypatch, capsys):
    """A finding is written into a build log, which may itself be public — so it names the place, not
    the value (the worker scanner has followed this rule for longer than this one has existed)."""
    path = tmp_path / "leak.md"
    path.write_text("Bearer mcp_" + TOKEN_SHAPED[0] + "\n", encoding="utf-8")
    monkeypatch.setattr("scripts.check_published_secrets.candidate_files", lambda: [path])
    assert main([]) == 1
    out = capsys.readouterr().out
    assert TOKEN_SHAPED[0] not in out, out
    assert "leak.md:1" in out, out
    assert "misakanet node token" in out, out


def test_a_clean_run_exits_zero_and_says_how_much_it_read(tmp_path, monkeypatch, capsys):
    path = tmp_path / "ok.md"
    path.write_text("Use `mcp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` as a placeholder.\n", encoding="utf-8")
    monkeypatch.setattr("scripts.check_published_secrets.candidate_files", lambda: [path])
    assert main([]) == 0
    assert "1 published prose files" in capsys.readouterr().out


def test_no_files_is_an_error_not_a_pass(tmp_path, monkeypatch, capsys):
    """An empty scan and a clean scan must not look the same — the failure this whole issue is about."""
    monkeypatch.setattr("scripts.check_published_secrets.candidate_files", list)
    assert main([]) == 2
    assert "no published prose files" in capsys.readouterr().err


# ── the wiring: the gate has to run for the PR that needs it ────────────────────────
def _secret_scan_step() -> dict:
    for job in yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"].values():
        for step in job.get("steps") or []:
            if step.get("id") == "secrets":
                return step
    raise AssertionError("the audit has no `secrets` step — the scan is the point of this file")


def test_the_scan_runs_for_every_scope_including_docs_only():
    """#1982 was docs-only, and the old condition `scope == 'full'` is precisely why nothing looked."""
    step = _secret_scan_step()
    assert "if" not in step, (
        f"the secret scan is conditional again ({step.get('if')!r}) — a docs-only or ci-only PR would "
        "skip it, which is the case that nearly published a token in #1982"
    )


def test_the_scan_invokes_the_published_prose_scanner():
    run = _secret_scan_step()["run"]
    assert "check_published_secrets.py" in run, run
    assert "check_worker_secrets.py" in run, "the worker scan was dropped while adding the new one"


def test_one_scanner_failing_does_not_hide_the_other():
    """Two scans, one exit code: if the worker scan fails first and the step chained with `&&`, the prose
    scan would be skipped — and its findings are exactly the ones nobody else reports."""
    run = _secret_scan_step()["run"]
    assert "|| FAILED=1" in run, run
    assert "&& python3 scripts/check_published_secrets.py" not in run, run
