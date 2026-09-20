#!/usr/bin/env python3
"""Two installers, one contract — and nobody was checking they agreed.

`npx @misaka-net/misakanet-setup` (packages/misakanet-setup/bin/misakanet-setup.mjs) and the
bootstrap route (integrations/agent-autostart/install_misakanet_agent.py) write the same agent
configs, and they are maintained separately. Adding Cursor to the npm installer alone was the
obvious way to do it, and it would have left the offline/bootstrap user — the one whose network is
hostile enough to need a bootstrap script — without the target the README advertises.

The one intentional difference is `dsh`: the Python installer also drops a `SKILL.md` for the
DeepSeek Harness plugin channel, which is not an MCP config file and has no npm counterpart. So the
invariant is: the npm targets must all exist in the Python installer, and the only target the Python
installer may have beyond them is `dsh`.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
NPM = REPO / "packages" / "misakanet-setup" / "bin" / "misakanet-setup.mjs"
PY = REPO / "integrations" / "agent-autostart" / "install_misakanet_agent.py"

ALLOWED_PY_ONLY = {"dsh"}


def npm_targets() -> list[str]:
    match = re.search(r"^const AGENTS = \[([^\]]+)\]", NPM.read_text(encoding="utf-8"), re.M)
    assert match, "the npm installer's AGENTS array moved; fix this gate rather than deleting it"
    return re.findall(r"'([^']+)'", match.group(1))


def python_targets() -> list[str]:
    match = re.search(r"^AGENTS = \(([^)]+)\)", PY.read_text(encoding="utf-8"), re.M)
    assert match, "the python installer's AGENTS tuple moved; fix this gate rather than deleting it"
    return re.findall(r'"([^"]+)"', match.group(1))


def test_the_two_installers_declare_the_same_targets():
    npm, py = set(npm_targets()), set(python_targets())
    missing = sorted(npm - py)
    extra = sorted(py - npm - ALLOWED_PY_ONLY)
    assert not missing, (
        f"the npm installer targets {missing} but the bootstrap installer does not: an offline "
        f"user would silently get fewer agents than the README advertises"
    )
    assert not extra, (
        f"the bootstrap installer targets {extra} with no npm counterpart. If that is intentional, "
        f"add it to ALLOWED_PY_ONLY with the reason; otherwise the two are drifting"
    )


def test_every_declared_target_is_actually_implemented_in_both():
    """A name in the list with no writer is worse than a missing name: it looks supported."""
    npm_src = NPM.read_text(encoding="utf-8")
    py_src = PY.read_text(encoding="utf-8")
    problems = []
    for target in npm_targets():
        camel = "".join(part.title() for part in target.split("-"))
        if f"async function install{camel}(" not in npm_src:
            problems.append(f"npm: install{camel}() is missing")
        if f"def install_{target}(" not in py_src:
            problems.append(f"python: install_{target}() is missing")
        if f"'{target}': install_" not in py_src and f'"{target}": install_' not in py_src:
            problems.append(f"python: INSTALLERS has no {target} entry")
    assert not problems, "; ".join(problems)


def test_cursor_is_written_in_the_documented_shape_in_both(tmp_path=None):
    """The shape is Cursor's, not Claude Code's: `url` + `headers`, and no `type`/`transport` key.

    Copying the Claude Code entry (which carries `type: "http"`) into `~/.cursor/mcp.json` is the
    kind of mistake that fails silently, so both writers are checked for it here.
    """
    npm_src = NPM.read_text(encoding="utf-8")
    py_src = PY.read_text(encoding="utf-8")
    assert "cursor: (home) => [join(home, '.cursor', 'mcp.json')]" in npm_src, (
        "the npm installer must declare Cursor's write path, or --dry-run/--list-writes cannot "
        "report it and unwritableTargets() cannot refuse it"
    )
    assert '"cursor": [home / ".cursor"]' in py_src
    for name, src in (("npm", npm_src), ("python", py_src)):
        block = src[src.index("installCursor") if name == "npm" else src.index("def install_cursor"):]
        block = block[: block.index("\n}\n") if name == "npm" else block.index("\ndef ")]
        assert '"url"' in block or "'url'" in block or "url" in block, f"{name}: no url field"
        assert '"type"' not in block and "'type'" not in block, (
            f"{name}: Cursor's entry must not carry a `type` key — that is the Claude Code shape, "
            f"and Cursor documents none"
        )
