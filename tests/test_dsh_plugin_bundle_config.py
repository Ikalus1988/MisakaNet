#!/usr/bin/env python3
"""The row's `Config` schema is what the host validates the patch against, so it must not drift from it.

`index.js` exports a schemastery `Config` built from `DEFAULT_MCP_CONFIG`'s keys — the same object the
plugin falls back to when the row declares no config. Two things can go wrong silently: a field added to
one and not the other (the host then rejects a config the plugin would have accepted), and a default that
disagrees (the resolved value stops describing what the plugin actually does).

The schema is built at module scope with a **top-level `await` inside a `try`**, so in a checkout without
`node_modules` it degrades to `undefined` rather than failing the import — which is also why this test
skips when schemastery is not resolvable instead of going red.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
NODE = "node"


def _defaults_from_schema() -> tuple[dict, dict] | None:
    """(schema defaults, DEFAULT_MCP_CONFIG) resolved in node, or None when schemastery is unreachable.

    Both objects come out of the module itself: reading `DEFAULT_MCP_CONFIG` out of the source with a regex
    was the first version of this test, and it ate the `//` in the endpoint URL as a comment — the kind of
    parser that fails the moment a value looks like syntax.
    """
    # Point the resolver at the `dsh` entry point when this machine has one: that is exactly how the host
    # reaches schemastery for a **linked** install, so the comparison runs on a developer machine and skips
    # on a bare checkout instead of pretending to have checked anything.
    dsh = shutil.which("dsh") or "/nonexistent/dsh"
    script = f"""
import {{ pathToFileURL }} from 'node:url';
// A bare absolute path is a valid specifier on POSIX and **not** on Windows, where `C:` reads as a URL
// scheme and the import dies with ERR_UNSUPPORTED_ESM_URL_SCHEME. This gate went red on the windows legs
// from the moment it was added, and nothing on Linux could see it.
const entry = pathToFileURL({str(REPO / 'index.js')!r}).href;
process.argv[1] = {dsh!r};
const mod = await import(entry);
if (mod.Config === undefined) {{ console.log('NO_SCHEMA'); process.exit(0); }}
console.log(JSON.stringify({{ schema: mod.Config({{}}), entry: mod.DEFAULT_MCP_CONFIG }}));
"""
    done = subprocess.run([NODE, "--input-type=module", "-e", script],
                          capture_output=True, text=True, timeout=120, cwd=str(REPO))
    assert done.returncode == 0, done.stderr[-400:]
    out = done.stdout.strip().splitlines()[-1]
    if out == "NO_SCHEMA":
        return None
    parsed = json.loads(out)
    return parsed["schema"], parsed["entry"]


def test_the_config_schema_is_declared_for_the_host():
    """Without a schema the host cannot document the row at all — it is what `describe()` reads."""
    text = (REPO / "index.js").read_text(encoding="utf-8")
    assert re.search(r"^export \{ Config \};", text, re.M), "index.js must export the row's Config schema"
    assert "z.object({" in text, "the schema must be a schemastery object"


def test_schema_defaults_match_the_entry_defaults(tmp_path):
    """The two must agree field for field; `dsh-bundle`'s patch test already pins patch ↔ defaults."""
    if shutil.which(NODE) is None:
        pytest.skip("node builds and resolves the schema")
    resolved = _defaults_from_schema()
    if resolved is None:
        pytest.skip("schemastery is not resolvable from this checkout (a dsh install provides it)")
    schema_defaults, entry_defaults = resolved
    assert schema_defaults == entry_defaults, (
        "the schema and DEFAULT_MCP_CONFIG disagree; one of them is now lying about the row")


def test_module_imports_go_through_file_urls():
    """`await import("C:\\path")` is not a path, it is a scheme — and only Windows says so.

    This gate ran red on both windows legs from the moment it was added (#2599) and stayed red through every
    PR stacked on it, because a POSIX absolute path happens to be a valid specifier while a Windows one is
    rejected with ERR_UNSUPPORTED_ESM_URL_SCHEME. The same trap sat in `index.js`'s linked-install fallback,
    where it degraded silently to "no schema" instead of failing.
    """
    test_source = Path(__file__).read_text(encoding="utf-8")
    index_source = (REPO / "index.js").read_text(encoding="utf-8")
    assert "pathToFileURL" in test_source, "the harness must import the module through a file URL"
    assert "pathToFileURL" in index_source, "the runtime fallback must wrap resolved paths as file URLs"
