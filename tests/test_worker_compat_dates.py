"""Worker config gates: the compatibility date, and the deploy that has to carry it.

Two production decisions lived in files no test looked at, and both had rotted silently by
2026-09-24:

1. ``workers/wrangler.toml`` still pinned ``compatibility_date = "2024-01-01"`` — the runtime
   semantics the Worker is compiled against, 997 days (~33 months) stale, while the other three
   configs in this repository were current. Nothing failed: production simply kept running by rules
   nobody had chosen any more, and what surfaced it was a Cloudflare zone audit, not this
   repository.
2. ``deploy-worker.yml`` triggered only on ``workers/register-proxy-sw.js``, and then PUT a
   hardcoded ``*/5 * * * *`` schedule after every deploy. So (a) a config-only fix deployed
   nothing, and (b) the config's own ``*/15`` — changed precisely to cut the 522 noise the loopback
   keepalive probe generates — was overwritten back to ``*/5`` on every deploy. Live schedule was
   ``*/5`` while ``main`` said ``*/15``.

Both rules are pure functions over parsed input so the fixtures below can prove they fire. A rule
that cannot go red is not a rule.
"""

from __future__ import annotations

import datetime as dt
import fnmatch
import json
import os
import tomllib
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
DEPLOY_WORKFLOW = REPO / ".github" / "workflows" / "deploy-worker.yml"

# Cloudflare recommends keeping the compatibility date current; a year is the point where "pinned
# deliberately" stops being distinguishable from "forgotten".
MAX_AGE_DAYS = 365

_VENDORED = {
    "node_modules", ".pnpm-store", ".tools", ".git", "dist", "build",
    ".venv", "site-packages", ".wrangler", "__pycache__",
}
# By prefix, not by exact name: `wrangler.api.jsonc` existed once (it is what `deploy:api` pointed at
# until 2026-09-24), and an exact-name list would have missed it — a config can be deployed and
# ungated at the same time, which is how its compatibility date stayed at 2024-01-01 unnoticed.
_CONFIG_SUFFIXES = (".toml", ".jsonc", ".json")


def is_wrangler_config(name: str) -> bool:
    return name.startswith("wrangler") and name.endswith(_CONFIG_SUFFIXES)


# ── parsing ──────────────────────────────────────────────────────────────────────────────────────

def wrangler_configs(root: Path = REPO) -> list[Path]:
    """Every wrangler config in the repository, vendored trees excluded."""
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _VENDORED]
        found.extend(Path(dirpath) / name for name in filenames if is_wrangler_config(name))
    return sorted(found)


def strip_trailing_commas(text: str) -> str:
    """JSONC allows a comma before a closing brace; `json.loads` does not.

    Scanned rather than substituted: the regex version was `,(\\s*[}\\]])` — exactly the
    unbounded-quantifier-then-literal shape CodeQL reported twice (alert #281).
    """
    out = []
    index = 0
    while index < len(text):
        if text[index] == ",":
            look = index + 1
            while look < len(text) and text[look] in " \t\r\n":
                look += 1
            if look < len(text) and text[look] in "}]":
                index += 1
                continue
        out.append(text[index])
        index += 1
    return "".join(out)


def load_config(path: Path) -> dict:
    """Parse a wrangler config. JSONC is JSON with comments; tomllib handles TOML."""
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".toml":
        return tomllib.loads(text)
    # Line-based comment strip: a naive regex would also eat the `//` inside `"$schema": "https://…"`.
    stripped = "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("//")
    )
    stripped = strip_trailing_commas(
        "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("//"))
    )
    return json.loads(stripped)


def real_configs() -> list[tuple[str, dict]]:
    return [(str(p.relative_to(REPO)), load_config(p)) for p in wrangler_configs()]


# ── rule 1: the compatibility date is a decision, and a stale one is a silent one ────────────────

def config_problems(configs: list[tuple[str, dict]], today: dt.date) -> list[str]:
    problems: list[str] = []
    for name, config in configs:
        if not isinstance(config.get("name"), str) or not config["name"].strip():
            problems.append(f"{name}: no `name` — a deploy would have no Worker to target")
        if "main" not in config and "assets" not in config:
            problems.append(f"{name}: neither `main` nor `assets` — there is nothing to deploy")
        raw = config.get("compatibility_date")
        if not isinstance(raw, str):
            problems.append(
                f"{name}: `compatibility_date` is {raw!r}; expected a YYYY-MM-DD string. Without "
                f"one the Worker tracks the account default, which is not a decision anyone made")
            continue
        try:
            date = dt.date.fromisoformat(raw)
        except ValueError:
            problems.append(f"{name}: `compatibility_date = {raw!r}` is not a YYYY-MM-DD date")
            continue
        age = (today - date).days
        if age < 0:
            problems.append(
                f"{name}: compatibility_date {date} is {abs(age)} days in the future (today {today}); "
                f"Cloudflare rejects a date it has not shipped, so the deploy fails at the last step")
        elif age > MAX_AGE_DAYS:
            problems.append(
                f"{name}: compatibility_date {date} is {age} days old (limit {MAX_AGE_DAYS} days). "
                f"Bump it deliberately, then verify the deploy: runtime semantics change with it "
                f"(found 2026-09-24 at 2024-01-01, ~21 months stale)")
    return problems


# ── rule 2: a config the deploy does not watch is a config that never ships ───────────────────────

def deploy_watch_problems(paths: list[str], needed: list[str]) -> list[str]:
    """`paths:` entries must cover every file the deploy consumes."""
    def covers(pattern: str, want: str) -> bool:
        if pattern == want:
            return True
        if pattern.endswith("/**"):  # `workers/**` covers everything under workers/
            return want.startswith(pattern[:-3].rstrip("/") + "/")
        # `*` does not cross a separator, matching GitHub's own path-filter behaviour.
        if "**" in pattern:
            return False
        # `*` does not cross a separator, matching GitHub's own path-filter behaviour — one segment at
        # a time, so no pattern is ever compiled from repository text (alert #281's lesson).
        pattern_parts, want_parts = pattern.split("/"), want.split("/")
        return len(pattern_parts) == len(want_parts) and all(
            fnmatch.fnmatchcase(segment, piece) for piece, segment in zip(pattern_parts, want_parts)
        )

    problems = []
    for want in needed:
        if not any(covers(p, want) for p in paths):
            problems.append(
                f"{DEPLOY_WORKFLOW.name} does not watch `{want}`, so a change to it merged to main "
                f"deploys nothing (found 2026-09-24: the compatibility date could be fixed on main "
                f"and production would keep the old one)")
    return problems


# ── rule 3: the schedule has one source of truth — the config ─────────────────────────────────────

# Five whitespace-separated fields inside quotes: a cron expression. Found by scanning quoted spans
# rather than by regex — the pattern this replaced nested an unbounded quantifier inside a counted
# repetition, which is the shape `py/polynomial-redos` exists to catch.
_CRON_CHARS = set("0123456789*/,- ")


def cron_literals(text: str) -> list[str]:
    found = []
    for quote in ('"', "'"):
        # Odd indices of a split on a quote character are the quoted contents.
        for value in text.split(quote)[1::2]:
            fields = value.split()
            if len(fields) == 5 and value.strip() and set(value) <= _CRON_CHARS:
                found.append(value)
    return found


def cron_literal_problems(text: str) -> list[str]:
    """The deploy must read the schedule from the config, not restate it."""
    problems = []
    for literal in cron_literals(text):
        problems.append(
            f"deploy workflow hardcodes the schedule {literal!r}; the keepalive cadence "
                f"lives in workers/wrangler.toml under [triggers] crons and must be read from there "
                f"(a hardcoded */5 silently undid the config's */15 on every deploy)")
    if "schedules" in text and "wrangler.toml" not in text:
        problems.append("deploy workflow calls the schedules API without reading workers/wrangler.toml")
    return problems


# ── the repository's own configs ─────────────────────────────────────────────────────────────────

def test_every_wrangler_config_pins_a_current_compatibility_date():
    configs = real_configs()
    assert configs, "no wrangler config found — this gate would pass vacuously"
    problems = config_problems(configs, dt.date.today())
    assert not problems, "\n  ".join(problems)


def test_deploy_workflow_watches_the_config_and_the_entry_point():
    config_path = "workers/wrangler.toml"
    config = load_config(REPO / config_path)
    entry = str(Path(config_path).parent / config["main"])
    workflow = yaml.safe_load(DEPLOY_WORKFLOW.read_text(encoding="utf-8"))
    triggers = workflow.get("on") or workflow.get(True) or {}
    paths = triggers["push"]["paths"]
    problems = deploy_watch_problems(paths, [config_path, entry])
    assert not problems, "\n  ".join(problems)


def test_deploy_workflow_derives_the_schedule_from_the_config():
    problems = cron_literal_problems(DEPLOY_WORKFLOW.read_text(encoding="utf-8"))
    assert not problems, "\n  ".join(problems)


# ── fixtures: proof that each rule can go red ────────────────────────────────────────────────────

TODAY = dt.date(2026, 9, 24)


def test_a_stale_date_is_flagged():
    problems = config_problems([("workers/wrangler.toml", {
        "name": "w", "main": "w.js", "compatibility_date": "2024-01-01"})], TODAY)
    assert len(problems) == 1, problems
    assert "997 days old" in problems[0], problems[0]


def test_a_date_exactly_at_the_limit_is_allowed():
    at_limit = TODAY - dt.timedelta(days=MAX_AGE_DAYS)
    assert not config_problems([("w.toml", {
        "name": "w", "main": "w.js", "compatibility_date": at_limit.isoformat()})], TODAY)


def test_a_future_date_is_flagged():
    problems = config_problems([("w.toml", {
        "name": "w", "main": "w.js", "compatibility_date": "2027-01-01"})], TODAY)
    assert len(problems) == 1 and "in the future" in problems[0], problems


def test_a_missing_or_unparseable_date_is_flagged():
    for value in (None, 20240101, "yesterday"):
        problems = config_problems([("w.toml", {"name": "w", "main": "w.js",
                                                "compatibility_date": value})], TODAY)
        assert len(problems) == 1, (value, problems)


def test_a_deploy_that_ignores_its_config_is_flagged():
    problems = deploy_watch_problems(["workers/register-proxy-sw.js"], ["workers/wrangler.toml"])
    assert len(problems) == 1 and "deploys nothing" in problems[0], problems
    # A directory entry covers what is under it — but only spelled as a glob: GitHub's path filters
    # are patterns, so a bare `workers/` matches no file at all.
    assert deploy_watch_problems(["workers/"], ["workers/wrangler.toml"]), "a bare directory covers nothing"
    assert not deploy_watch_problems(["workers/**"], ["workers/register-proxy-sw.js"])
    assert not deploy_watch_problems(["workers/*.toml"], ["workers/wrangler.toml"])
    assert deploy_watch_problems(["workers/*.toml"], ["workers/nested/wrangler.toml"]), "`*` must not cross `/`"


def test_the_discovery_rule_finds_configs_by_prefix_not_by_exact_name():
    """The blind spot that made this note necessary: `wrangler.api.jsonc` was deployed, not gated."""
    assert is_wrangler_config("wrangler.toml")
    assert is_wrangler_config("wrangler.api.jsonc")
    assert is_wrangler_config("wrangler.prod.toml")
    assert not is_wrangler_config(".pr-agent.toml")
    assert not is_wrangler_config("wrangler.toml.bak")
    assert not is_wrangler_config("mswrangler.toml")


def test_a_hardcoded_schedule_is_flagged():
    problems = cron_literal_problems('--data \'[{"cron":"*/5 * * * *"}]\'')
    assert problems and "*/5 * * * *" in problems[0], problems
    assert not cron_literal_problems(
        "--data @/tmp/schedules.json  # from workers/wrangler.toml\nschedules")
    # A quoted version string with spaces is not a schedule.
    assert not cron_literal_problems("ACCOUNT='6b92 325b'\nschedules wrangler.toml")
