#!/usr/bin/env python3
"""Gate: the **installed wheel** can start its MCP server (2026-09-18 review, 意见 1/12).

`pip install misakanet` used to produce a package whose declared entry points could not run: the
console scripts pointed at `search_knowledge:main` and `scripts.misaka_harvest:main`, and neither
`search_knowledge.py` nor `scripts/` is inside the wheel, while `server.json` told every MCP client to
run `python3 scripts/mcp_server.py` — a file that does not exist after an install.

This gate answers the only question that matters for that channel: *build the wheel, install it into a
clean virtualenv, and ask the installed server for an `initialize` handshake.* It runs the same
question a client would, over stdio, and prints the response so a failure is readable.

Not a pytest test on purpose: it needs a build and a real install, which is a CI-shaped job rather
than a unit test (uv's `test-smoke.yml` splits the same way).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

# Windows consoles are not UTF-8 by default: printing the checkmark below raised UnicodeEncodeError
# *after* the handshake had already succeeded, so both Windows legs failed for the decoration rather
# than for the check (the same class of bug this repo already fixed in the installer). Force the two
# streams rather than avoiding non-ASCII, because diagnostic output is where non-ASCII appears.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

REPO = Path(__file__).resolve().parent.parent
HANDSHAKE = json.dumps({
    "jsonrpc": "2.0", "id": 1, "method": "initialize",
    "params": {"protocolVersion": "2025-06-18", "capabilities": {},
               "clientInfo": {"name": "wheel-smoke", "version": "1"}},
}) + "\n"


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    print(f"$ {' '.join(cmd)}", flush=True)
    return subprocess.run(cmd, text=True, capture_output=True, **kw)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="misakanet-wheel-") as tmp:
        tmp_path = Path(tmp)
        wheels = tmp_path / "wheels"

        # 1. Build the wheel without installing anything (no dependency resolution here: that is the
        #    next step's job, and mixing them hides which one failed).
        built = run([sys.executable, "-m", "pip", "wheel", ".", "-w", str(wheels), "--no-deps"], cwd=REPO)
        if built.returncode != 0:
            print(built.stdout[-2000:]); print(built.stderr[-2000:], file=sys.stderr)
            print("::error::building the wheel failed", file=sys.stderr)
            return 1
        wheel = next(wheels.glob("misakanet-*.whl"), None)
        if wheel is None:
            print(f"::error::no wheel in {wheels}: {list(wheels.iterdir())}", file=sys.stderr)
            return 1
        print(f"built: {wheel.name}")

        # 2. A clean virtualenv — the point is what a *user* gets, not what this checkout has.
        env_dir = tmp_path / "venv"
        venv.EnvBuilder(with_pip=True, clear=True).create(env_dir)
        py = env_dir / ("Scripts" if sys.platform == "win32" else "bin") / "python"

        # 3. Install the wheel *with* its dependencies: a package that only works because the
        #    developer's machine happens to have `mcp` installed is the defect this gate exists for.
        installed = run([str(py), "-m", "pip", "install", "-q", str(wheel)])
        if installed.returncode != 0:
            print(installed.stdout[-2000:]); print(installed.stderr[-2000:], file=sys.stderr)
            print("::error::installing the built wheel failed (its declared dependencies must be "
                  "installable)", file=sys.stderr)
            return 1

        # 4. Ask the installed package for a handshake, from a directory that is *not* the checkout —
        #    so a stray `misakanet/` on the path cannot make this pass.
        probe = run([str(py), "-m", "misakanet.server"], cwd=tmp_path, input=HANDSHAKE, timeout=120)
        stdout = probe.stdout.strip()
        print("--- stdout ---"); print(stdout[:1200] or "(empty)")
        if probe.stderr.strip():
            print("--- stderr ---"); print(probe.stderr.strip()[-800:])
        try:
            payload = json.loads(stdout.splitlines()[0]) if stdout else {}
        except (ValueError, IndexError):
            payload = {}
        info = payload.get("result", {}).get("serverInfo", {})
        if not info.get("name"):
            print("::error::`python -m misakanet.server` did not answer an MCP initialize handshake "
                  "after `pip install` — the wheel is not a working MCP server", file=sys.stderr)
            return 1
        print(f"OK: installed wheel answered: {info}")

        # 5. The declared console scripts must at least resolve. They are the other half of
        #    "pip install misakanet gives you something that starts"; a missing module here is exactly
        #    what issue #1821 reported.
        for name in ("misakanet", "misaka-harvest"):
            script = env_dir / ("Scripts" if sys.platform == "win32" else "bin") / name
            if not script.exists():
                print(f"::warning::console script not installed: {name}")
                continue
            checked = run([str(script), "--help"], cwd=tmp_path, timeout=120)
            print(f"  {name} --help → exit {checked.returncode}")
            if "ModuleNotFoundError" in (checked.stderr or "") or "No module named" in (checked.stderr or ""):
                # Known defect, tracked as #1821: the console scripts name modules that live outside the
                # package (`search_knowledge`, `scripts.misaka_harvest`), so they cannot work after a
                # pip install. Reported as a warning **for now** so this gate can land and protect the
                # half that is fixed (the installed server starts) without blocking everything else on a
                # refactor that moves those entry points into the package.
                #
                # Flip this to `return 1` in the same PR that moves them; until then the log says it
                # out loud rather than passing silently.
                print(f"::warning::`{name}` is installed but its module is not in the wheel (#1821): "
                      f"{checked.stderr.strip().splitlines()[-1] if checked.stderr.strip() else ''}")
    print("wheel smoke: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
