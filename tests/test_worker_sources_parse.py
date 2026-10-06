#!/usr/bin/env python3
"""Every `.js`/`.mjs` source under `workers/` must parse. Python cannot see that.

#2920 added a comment to `register-proxy-sw.js` explaining the #2918 fix. The file
builds its HTML inside a **template literal**, and the comment contained backticks
around a filename — which closed the literal early. The result was a `TypeError`
at request time, not a load error:

    TypeError: Cannot read properties of undefined (reading 'mp3')
      at Object.fetch (workers/register-proxy-sw.js:7832:27)

`tests/test_check_documented_gates.py` already applies `node --check` to workflow
scripts, and documents the same family of failure — a value spliced into a quote
that then runs unterminated. It does not cover worker sources, so the 3372-test
Python suite was fully green with a worker that could not serve a single request.

That is the shape worth closing: the suite that everyone runs is blind to a whole
language. Checking the four shipping sources is a few hundred milliseconds, and the
failure it prevents is a production 500 that no local Python test would ever see.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
WORKERS = REPO / "workers"

# Sources that are actually shipped or executed, as opposed to test files and
# fixtures. A syntax error in a `.test.mjs` is caught by running the tests; an error
# in a shipped source is not caught by anything until a request hits it.
SHIPPED = [
    WORKERS / "register-proxy-sw.js",
]
SHIPPED += sorted(WORKERS.glob("*.mjs"))
SHIPPED = [p for p in SHIPPED if not p.name.endswith(".test.mjs")]

node = shutil.which("node")
requires_node = pytest.mark.skipif(node is None, reason="node is not on PATH")


@requires_node
@pytest.mark.parametrize("path", SHIPPED, ids=lambda p: p.name)
def test_the_source_parses(path: Path) -> None:
    """`node --check` parses without executing, so nothing here needs a binding or a D1 handle."""
    if not path.exists():
        pytest.skip(f"{path.name} is listed but absent; the glob and this list disagree")
    proc = subprocess.run(
        [node, "--check", str(path)], capture_output=True, text=True, timeout=60
    )
    assert proc.returncode == 0, (
        f"{path.name} does not parse:\n{proc.stderr.strip()}\n\n"
        "If the file builds HTML inside a template literal, remember that a backtick in "
        "a comment closes the literal — this is what #2920 did to register-proxy-sw.js."
    )


@requires_node
def test_the_shipped_list_is_not_empty() -> None:
    """Otherwise the parameterised test above is a green no-op on a renamed directory."""
    present = [p for p in SHIPPED if p.exists()]
    assert present, (
        "no shipped worker source was found; if workers/ moved or was renamed, this file "
        "is no longer checking anything and must be updated with it"
    )


@requires_node
def test_register_proxy_serves_a_request_after_the_edit() -> None:
    """The check that would have caught #2920 on its own terms.

    `node --check` proves the file parses. It does not prove the module still
    *runs*: the backtick bug parsed cleanly enough for the interpreter to load it and
    only failed when `fetch` was called. Driving one request through the real handler
    closes that gap, and it costs nothing — the handler needs no network for `/start`.
    """
    import json

    env = {
        "MISAKANET_KV": None,
        "MISAKANET_D1": None,
        "MISAKANET_RATE_LIMITER": None,
    }
    proc = subprocess.run(
        [node, "--input-type=module", "-e", """
import worker from './workers/register-proxy-sw.js';
const env = new Proxy({}, { get: () => undefined });
const resp = await worker.fetch(new Request('https://misakanet.org/start'), env);
console.log(JSON.stringify({ status: resp.status, body: (await resp.text()).length }));
"""],
        cwd=REPO, capture_output=True, text=True, timeout=60,
        env={**__import__("os").environ},
    )
    assert proc.returncode == 0, (
        "register-proxy-sw.js threw when actually serving a request:\n"
        f"{proc.stderr.strip()}\n"
        f"(env placeholder: {json.dumps(env)})"
    )
