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
import json
import os
import re
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
_CONFIG_NAMES = {"wrangler.toml", "wrangler.jsonc", "wrangler.json"}


# ── parsing ──────────────────────────────────────────────────────────────────────────────────────

def wrangler_configs(root: Path = REPO) -> list[Path]:
    """Every wrangler config in the repository, vendored trees excluded."""
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _VENDORED]
        found.extend(Path(dirpath) / name for name in filenames if name in _CONFIG_NAMES)
    return sorted(found)


def load_config(path: Path) -> dict:
    """Parse a wrangler config. JSONC is JSON with comments; tomllib handles TOML."""
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".toml":
        return tomllib.loads(text)
    # Line-based comment strip: a naive regex would also eat the `//` inside `"$schema": "https://…"`.
    stripped = "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("//")
    )
    stripped = re.sub(r",(\s*[}\]])", r"\1", stripped)  # trailing commas are legal in JSONC
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
        return re.fullmatch(pattern.replace("**", "\0").replace("*", "[^/]*").replace("\0", ".*"),
                            want) is not None

    problems = []
    for want in needed:
        if not any(covers(p, want) for p in paths):
            problems.append(
                f"{DEPLOY_WORKFLOW.name} does not watch `{want}`, so a change to it merged to main "
                f"deploys nothing (found 2026-09-24: the compatibility date could be fixed on main "
                f"and production would keep the old one)")
    return problems


# ── rule 3: the schedule has one source of truth — the config ─────────────────────────────────────

# Five space-separated whitespace-free fields on one line, quoted: a cron expression. `[^\s'"]`
# rather than `\S` so a match cannot run across the JSON quoting and swallow the whole document.
_CRON_LITERAL = re.compile(r"""['"]([^\s'"]+(?:\s+[^\s'"]+){4})['"]""")


def cron_literal_problems(text: str) -> list[str]:
    """The deploy must read the schedule from the config, not restate it."""
    problems = []
    for match in _CRON_LITERAL.finditer(text):
        if re.fullmatch(r"[\d*/,\- ]+", match.group(1)):
            problems.append(
                f"deploy workflow hardcodes the schedule {match.group(1)!r}; the keepalive cadence "
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


def test_a_hardcoded_schedule_is_flagged():
    problems = cron_literal_problems('--data \'[{"cron":"*/5 * * * *"}]\'')
    assert problems and "*/5 * * * *" in problems[0], problems
    assert not cron_literal_problems(
        "--data @/tmp/schedules.json  # from workers/wrangler.toml\nschedules")
    # A quoted version string with spaces is not a schedule.
    assert not cron_literal_problems("ACCOUNT='6b92 325b'\nschedules wrangler.toml")
