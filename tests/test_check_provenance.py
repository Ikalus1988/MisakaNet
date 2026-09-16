#!/usr/bin/env python3
"""Tests for scripts/check_provenance.py — offline, no network.

The gate's job is to fail on *evidence* and never on the absence of it, so most of these
tests are about the statuses that must NOT fail the build: a timeout, a rate limit, a
private-IP example, a lesson that cites nothing at all.
"""
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_provenance as cp  # noqa: E402


def lesson(tmp_path, body: str, name: str = "lesson.md") -> pathlib.Path:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


def frontmatter_lesson(source: str = "", level: str = "") -> str:
    lines = ['---', 'title: "t"', 'domain: devops']
    if level:
        lines.append(f'evidence_level: "{level}"')
    if source:
        lines += ["provenance:", f'  source: "{source}"']
    lines += ["---", "", "## Problem", "", "body text"]
    return "\n".join(lines) + "\n"


# ── citing nothing is not a crime ────────────────────────────────────────────
def test_a_lesson_without_citations_produces_no_failure(tmp_path):
    path = lesson(tmp_path, frontmatter_lesson())
    rows = cp.scan([path], fetcher=None)
    failures, advisories = cp.evaluate(rows, {"known_dead": [], "exempt_urls": []}, set())
    assert failures == [] and advisories == []
    assert rows[0]["status"] == "none"


# ── tier 1: placeholders and confirmed-dead links ────────────────────────────
def test_a_placeholder_source_fails_without_any_network_call(tmp_path):
    path = lesson(tmp_path, frontmatter_lesson(source="https://github.com/<owner>/<repo>/issues/1"))
    rows = cp.scan([path], fetcher=None)
    assert rows[0]["status"] == "placeholder"
    failures, _ = cp.evaluate(rows, {"known_dead": [], "exempt_urls": []}, set())
    assert any("placeholder" in f for f in failures)


def test_a_dead_source_fails(tmp_path):
    path = lesson(tmp_path, frontmatter_lesson(source="https://github.com/no/such-repo/issues/1"))
    rows = cp.scan([path], fetcher=lambda url, token="": (404, ""))
    failures, _ = cp.evaluate(rows, {"known_dead": [], "exempt_urls": []}, set())
    assert len(failures) == 1 and "does not resolve" in failures[0]


def test_a_baselined_dead_source_is_tolerated(tmp_path):
    """The exact failure this gate was written for must be recordable without disabling it."""
    url = "https://github.com/modelcontextprotocol/mcp-memory-service/issues/1652"
    path = lesson(tmp_path, frontmatter_lesson(source=url))
    rows = cp.scan([path], fetcher=lambda u, token="": (404, ""))
    failures, _ = cp.evaluate(rows, {"known_dead": [{"url": url}], "exempt_urls": []}, set())
    assert failures == []


def test_the_real_red_team_case_is_caught(tmp_path):
    """#1713: 24/24 CI green, source pointing at a repository that does not exist."""
    path = lesson(tmp_path, frontmatter_lesson(
        source="https://github.com/modelcontextprotocol/mcp-memory-service/issues/1652", level="E3"))
    rows = cp.scan([path], fetcher=lambda u, token="": (404, ""))
    failures, advisories = cp.evaluate(rows, {"known_dead": [], "exempt_urls": []}, {cp.rel_to_repo(path)})
    assert len(failures) == 1
    assert advisories == []          # the dead link is already the failure; do not double-report


# ── statuses that must never fail ────────────────────────────────────────────
@pytest.mark.parametrize("code", [403, 429, 500, 503, "error"])
def test_inconclusive_answers_are_unknown_not_failures(tmp_path, code):
    path = lesson(tmp_path, frontmatter_lesson(source="https://example-shop.test/issue"))
    rows = cp.scan([path], fetcher=lambda u, token="": (code, "transient"))
    assert rows[0]["status"] == "unknown"
    failures, _ = cp.evaluate(rows, {"known_dead": [], "exempt_urls": []}, set())
    assert failures == []


def test_offline_mode_reports_unknown_and_never_fails(tmp_path):
    path = lesson(tmp_path, frontmatter_lesson(source="https://github.com/Ikalus1988/MisakaNet/issues/1"))
    rows = cp.scan([path], fetcher=None)
    assert rows[0]["status"] == "unknown" and rows[0]["detail"] == "offline"
    assert cp.evaluate(rows, {"known_dead": [], "exempt_urls": []}, set())[0] == []


@pytest.mark.parametrize("url", [
    "http://172.19.128.1:7890",            # the corporate-proxy example already in the corpus
    "http://127.0.0.1:8080/health",
    "https://example.com/webhook",
    "http://my-box.local:3000/callback",
])
def test_illustrative_urls_are_exempt_by_construction(url):
    assert cp.classify(url) == "exempt"


# ── tier 2: high evidence level needs a verifiable source (new files only) ────
def test_high_evidence_level_without_a_source_is_advisory_for_new_files(tmp_path):
    path = lesson(tmp_path, frontmatter_lesson(level="E3"))
    rows = cp.scan([path], fetcher=None)
    failures, advisories = cp.evaluate(rows, {"known_dead": [], "exempt_urls": []}, {cp.rel_to_repo(path)})
    assert failures == []
    assert len(advisories) == 1 and "E3" in advisories[0]


def test_the_same_rule_does_not_touch_existing_files(tmp_path):
    """Legacy debt must not block unrelated PRs — the lesson gate's #1506 split."""
    path = lesson(tmp_path, frontmatter_lesson(level="E2"))
    rows = cp.scan([path], fetcher=None)
    failures, advisories = cp.evaluate(rows, {"known_dead": [], "exempt_urls": []}, set())
    assert failures == [] and advisories == []


def test_a_resolvable_source_satisfies_the_high_level_rule(tmp_path):
    path = lesson(tmp_path, frontmatter_lesson(source="https://github.com/Ikalus1988/MisakaNet/issues/1766",
                                               level="E3"))
    rows = cp.scan([path], fetcher=lambda u, token="": (200, ""))
    _, advisories = cp.evaluate(rows, {"known_dead": [], "exempt_urls": []}, {cp.rel_to_repo(path)})
    assert advisories == []


# ── parsing ──────────────────────────────────────────────────────────────────
def test_local_evidence_refs_are_not_urls_and_are_ignored():
    fm = 'title: "t"\nprovenance:\n  issue: "#1553"\nevidence_refs:\n  - "issue:#1553"\n  - bench:core\n'
    assert cp.citations(fm) == []


def test_citations_are_collected_from_every_citation_key():
    fm = ('source: "https://github.com/a/b/issues/1"\n'
          'evidence_refs:\n  - "https://github.com/c/d/issues/2"\n')
    assert cp.citations(fm) == ["https://github.com/a/b/issues/1", "https://github.com/c/d/issues/2"]


def test_github_urls_are_mapped_onto_the_api_resource():
    assert cp.github_api_url("https://github.com/a/b.git") == "https://api.github.com/repos/a/b"
    assert (cp.github_api_url("https://github.com/a/b/issues/7")
            == "https://api.github.com/repos/a/b/issues/7")
    assert cp.github_api_url("https://gitlab.com/a/b") is None


def test_evidence_level_is_read_with_or_without_quotes():
    assert cp.evidence_level('evidence_level: "E3"\n') == "E3"
    assert cp.evidence_level("evidence_level: E2\n") == "E2"
    assert cp.evidence_level('title: "t"\n') == ""


def test_a_file_without_frontmatter_is_skipped(tmp_path):
    path = lesson(tmp_path, "# just markdown\n")
    assert cp.scan([path], fetcher=None) == []


# ── baseline handling ────────────────────────────────────────────────────────
def test_update_baseline_records_only_confirmed_dead_urls(tmp_path, monkeypatch):
    target = tmp_path / "provenance-baseline.json"
    monkeypatch.setattr(cp, "BASELINE", target)
    path = lesson(tmp_path, frontmatter_lesson(source="https://github.com/gone/repo/issues/3"))

    def fake(url, token=""):
        return (404, "") if "gone" in url else ("error", "timeout")

    rows = cp.scan([path], fetcher=fake)
    dead = sorted({r["url"] for r in rows if r["status"] == "dead"})
    assert dead == ["https://github.com/gone/repo/issues/3"]
    target.write_text(json.dumps({"known_dead": [{"url": u} for u in dead], "exempt_urls": []}),
                      encoding="utf-8")
    baseline = cp.load_baseline()
    assert [e["url"] for e in baseline["known_dead"]] == dead


def test_a_malformed_baseline_does_not_crash_the_gate(tmp_path, monkeypatch):
    target = tmp_path / "provenance-baseline.json"
    target.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(cp, "BASELINE", target)
    assert cp.load_baseline() == {"known_dead": [], "exempt_urls": []}


# ── the corpus itself ────────────────────────────────────────────────────────
def test_the_shipped_baseline_is_valid_json_with_a_schema():
    data = json.loads((ROOT / "data" / "provenance-baseline.json").read_text(encoding="utf-8"))
    assert data["schema"] == "misakanet-provenance-baseline/1"
    assert isinstance(data["known_dead"], list)
    assert isinstance(data["exempt_urls"], list)


def test_placeholders_are_never_baselined():
    """A placeholder is always fixable, so it must never earn an exemption."""
    data = json.loads((ROOT / "data" / "provenance-baseline.json").read_text(encoding="utf-8"))
    for entry in data["known_dead"]:
        assert cp.classify(entry["url"]) == "check", entry


# ── CLI behaviour ────────────────────────────────────────────────────────────
def test_strict_new_alone_targets_only_those_files(tmp_path, capsys):
    """`--strict-new` uses nargs="*", which swallows positional args — CI calls it alone.

    Without this, `--strict-new <file>` scanned the entire corpus instead of the PR's files:
    slow, and it could fail a PR for a link nobody touched.
    """
    good = lesson(tmp_path, frontmatter_lesson(source="https://github.com/Ikalus1988/MisakaNet/issues/1"),
                  name="good.md")
    code = cp.main(["--check", "--offline", "--strict-new", str(good)])
    out = capsys.readouterr().out
    assert code == 0
    assert "检查 1 篇课程" in out, out


def test_cli_fails_on_a_placeholder_source(tmp_path, capsys):
    bad = lesson(tmp_path, frontmatter_lesson(source="https://github.com/OWNER/REPO/issues/1"),
                 name="bad.md")
    code = cp.main(["--check", "--offline", str(bad)])
    out = capsys.readouterr().out
    assert code == 1 and "placeholder" in out


# ── JSON-style frontmatter (64 lessons use it) ────────────────────────────────
JSON_LESSON = """---
{
  "title": "Probe",
  "domain": "devops",
  "status": "published",
  "evidence_level": "E3",
  "source": "https://github.com/modelcontextprotocol/mcp-memory-service/issues/1652"
}
---

## Problem

body
"""


def test_quoted_keys_in_json_frontmatter_are_read(tmp_path):
    """A fabricated source hidden in a JSON block must not be invisible to the gate.

    Sixty-four lessons use JSON-style frontmatter. The first regex only matched unquoted
    `key:` lines, so `"source": "https://…"` produced no citation at all — the gate reported
    nothing while the file cited whatever it liked. The red-team probe caught it.
    """
    path = lesson(tmp_path, JSON_LESSON, name="json-lesson.md")
    rows = cp.scan([path], fetcher=lambda u, token="": (404, ""))
    assert [r["url"] for r in rows] == ["https://github.com/modelcontextprotocol/mcp-memory-service/issues/1652"]
    assert rows[0]["status"] == "dead"
    failures, _ = cp.evaluate(rows, {"known_dead": [], "exempt_urls": []}, set())
    assert len(failures) == 1


def test_evidence_level_is_read_from_json_frontmatter():
    """JSON keys are indented, so the level regex has to tolerate leading whitespace."""
    assert cp.evidence_level('  "evidence_level": "E3",\n  "source": "x"\n') == "E3"
    assert cp.evidence_level('{"title": "t"}\n  "evidence_level": E2\n') == "E2"
