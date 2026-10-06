#!/usr/bin/env python3
"""Drive the MisakaNet client half in a real DSH host and assert its three load-bearing interactions.

The source-level gates pin *registrations*: a seat is declared, a dictionary key exists, a schema matches its
defaults, no registration bypasses `slots.inject`. They cannot see whether anything actually happens. This
script pins **behaviour**, in a real host, in a real browser:

1. `slash-overlay`   — `/misakanet <query>` answers inside the composer with rows from the library;
2. `frame-wide-toast` — that result raises the frame-wide toast, and its own dismiss control removes it;
3. `settings-to-panel` — the General-section row's voice switch moves the panel's switch with it.

It boots a **disposable** host: `DSH_HOME` in a temp directory, `env -i`, a fixed port, this working tree
installed into a profile. The lesson library is **intercepted**, so the suite is hermetic — it asserts the
request the page makes (endpoint, `q`, `limit`) and answers with a fixture instead of depending on the public
site being reachable, which a CI gate must not do.

Run it exactly as CI does:

    python3 tests/e2e/run_client_e2e.py --out /tmp/e2e-shots --keep

Exit code 0 means every scenario passed; the JSON summary says what each one saw.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DEFAULT_PORT = 52399
BOOT_TIMEOUT_S = 150
#: What the intercepted library answers with. Titles come from real lessons so the screenshots read true.
FIXTURE = {
    "query": "pip install timeout",
    "results": [
        {"id": "pip-install-timeout-ssl", "title": "pip install Network Timeout / SSL ErrorFix",
         "domain": "python", "path": "lessons/python/pip-install-timeout-ssl.md", "tags": ["pip", "ssl"],
         "description": "## Problem\n`pip install` fails with ReadTimeoutError behind a slow mirror.",
         "updated": "2026-01-02", "created": "2026-01-01", "rank": 1},
        {"id": "pip-proxy-corporate", "title": "pip install ReadTimeoutError Behind Corporate Proxy",
         "domain": "python", "path": "lessons/python/pip-proxy-corporate.md", "tags": ["pip", "proxy"],
         "description": "## Problem\nA corporate proxy needs the index and the trusted host set together.",
         "updated": "2026-01-02", "created": "2026-01-01", "rank": 2},
        {"id": "pip-cache-stale-wheel", "title": "pip keeps installing a stale wheel from the cache",
         "domain": "python", "path": "lessons/python/pip-cache-stale-wheel.md", "tags": ["pip", "cache"],
         "description": "## Problem\nA cached wheel hides a rebuilt dependency.",
         "updated": "2026-01-02", "created": "2026-01-01", "rank": 3},
        {"id": "venv-pip-missing-ssl", "title": "venv pip cannot find ssl module",
         "domain": "python", "path": "lessons/python/venv-pip-missing-ssl.md", "tags": ["python", "ssl"],
         "description": "## Problem\nA python built without the ssl module cannot install from PyPI.",
         "updated": "2026-01-02", "created": "2026-01-01", "rank": 4},
        {"id": "pip-index-url-precedence", "title": "extra-index-url silently wins over index-url",
         "domain": "python", "path": "lessons/python/pip-index-url-precedence.md", "tags": ["pip"],
         "description": "## Problem\nTwo indexes are not a merge; the newest version wins across both.",
         "updated": "2026-01-02", "created": "2026-01-01", "rank": 5},
    ],
}


def log(message: str) -> None:
    print(f"[e2e] {message}", flush=True)


def kill_port(port: int) -> None:
    """Kill whatever listens on `port`.

    Deliberately by port, not by a pattern-matching killer: this repository has killed its own shell twice
    because the pattern matched the invoking command line itself. The gate for this file asserts the same
    thing, so the wording here stays free of the token it forbids.
    """
    out = subprocess.run(["lsof", "-ti", f"tcp:{port}"], capture_output=True, text=True)
    for pid in out.stdout.split():
        subprocess.run(["kill", pid], capture_output=True)


def clean_env(home: Path) -> dict:
    """A host should not inherit this shell's DSH_* or npm config: the point is a disposable one."""
    # Keep the caller's PATH: `dsh plugin add` shells out to pnpm, and narrowing PATH to the dsh directory
    # (the first version of this) lost it. What must not leak is the caller's DSH_* and npm config, because
    # the whole point is a disposable host.
    return {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", "/root"),
        "DSH_HOME": str(home),
        "npm_config_cache": os.environ.get("npm_config_cache", str(home / "npm-cache")),
    }


def seed_workspace(home: Path) -> None:
    """Give the disposable profile one **schema-valid** workspace.

    Without a workspace the composer mounts as its chooser (`aria-label="Choose workspace"` /
    `"Choose a workspace to start"`) and no scenario can type into it — a fresh `DSH_HOME` has no workspaces,
    and the real UI adds them through a native directory picker a headless browser cannot drive.

    `createdAt` / `updatedAt` are not decoration: they are **required** by the workspace domain's schema, and
    the first version of this function omitted them. The failure mode carried no error message — the domain
    dropped the record, the profile came up with no usable workspace, and the suite timed out looking for a
    composer that was never going to mount. That is why this read as "a fresh profile cannot create a first
    session" for a day. Measured 2026-10-02 against `dsh 0.2.0-rc.2`, A/B with exactly these two fields as
    the only difference:

    * record without them → `[role=textbox]` label `Choose workspace`, body says `No sessions yet`;
    * record with them    → the host **creates the first session itself** (a `session-…` directory appears
      under `$DSH_HOME/sessions/<cwd-slug>/`) and the composer is live.

    So the first session is created the way the host supports — by the host — and nothing here fabricates
    session storage. The live record shape is `path`, `title`, `sessionIds`, `createdAt`, `updatedAt`, read
    off a real profile's `storages/workspace.json`; `tests/test_dsh_client_e2e.py` pins the two fields.
    """
    import uuid
    from datetime import datetime, timezone
    path = home / "storages" / "workspace.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    workspace_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"misakanet-e2e:{REPO}"))
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    path.write_text(json.dumps({
        "unit": {"name": "workspace", "version": 2},
        "global": {"initialized": True, "workspaceIds": [workspace_id],
                   "archivedSessionIds": [], "pinnedSessionIds": []},
        "tables": {"workspaces": {workspace_id: {
            "path": str(REPO), "title": REPO.name, "sessionIds": [],
            "createdAt": now, "updatedAt": now}}},
    }), encoding="utf-8")


def boot(dsh: str, home: Path, port: int, log_path: Path) -> subprocess.Popen:
    env = clean_env(home)
    with log_path.open("wb") as sink:
        process = subprocess.Popen(
            [dsh, "--profile", "web", "--no-open", "--port", str(port)],
            env=env, stdout=sink, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    return process


def wait_for_url(log_path: Path, port: int) -> str:
    pattern = re.compile(rf"http://127\.0\.0\.1:{port}/\?token=[A-Za-z0-9_-]+")
    deadline = time.time() + BOOT_TIMEOUT_S
    while time.time() < deadline:
        if log_path.exists():
            found = pattern.search(log_path.read_text(encoding="utf-8", errors="replace"))
            if found:
                return found.group(0)
        if time.time() > deadline:
            break
        time.sleep(2)
    tail = log_path.read_text(encoding="utf-8", errors="replace")[-1200:] if log_path.exists() else "(no log)"
    raise RuntimeError(f"the host never printed its URL within {BOOT_TIMEOUT_S}s; log tail:\n{tail}")


#: Dismiss controls a fresh profile offers, in the order a person would take them. `Configure later` is the
#: API-key dialog's own wording for "not now": the suite must not need credentials to run.
DISMISSALS = ("Continue", "Configure later", "Get started", "Close", "Skip", "Done", "OK")


def open_modal(page) -> dict:
    """The modal currently covering the app, if any: a `[role=dialog]` or a masked presentation root."""
    return page.evaluate(r"""() => {
        const dialog = document.querySelector('[role=dialog]');
        const masked = document.querySelector('div[class*=mask]');
        const root = dialog || (masked && masked.closest('[role=presentation]')) || null;
        if (!root) return null;
        return {
            heading: (root.innerText || '').trim().split('\n')[0].slice(0, 60),
            buttons: Array.from(root.querySelectorAll('button'))
                .map(e => (e.getAttribute('aria-label') || e.innerText || '').trim()).filter(Boolean),
        };
    }""")


def dismiss_modals(page) -> bool:
    """A fresh profile opens two blockers: the 'Preview Notice' and the API-key prompt.

    Both swallow every click until acknowledged, and neither needs anything from us to go away — one says
    `Continue`, the other `Configure later`.

    #2916 adds a third state that has to count as success. On a host with no LLM
    credentials, the notice's `Continue` renders **disabled** and then detaches itself
    inside the retry window — the page advances the notice by itself. `Locator.count()`
    only reports that the element exists, so the old code called `.click()` on a
    disabled button and burned the full timeout:

        TimeoutError: Locator.click: Timeout 8000ms exceeded
          locator resolved to <button disabled ...>Continue</button>
          element is not enabled / element was detached from the DOM

    That made this gate red on every machine unable to supply credentials, for a reason
    unrelated to the plugin it exists to check. Hand-verified counter-evidence: with the
    `Configure later` step added by hand, all three scenarios pass on that same host.

    The rule now is: click only what is actually clickable, and treat a control that
    disables or removes itself as dismissed. A dialog that resolves on its own is the
    outcome this function wanted anyway.
    """
    from playwright.sync_api import TimeoutError as PlaywrightTimeout

    for _ in range(5):
        modal = open_modal(page)
        if modal is None:
            return True
        log(f"modal: {modal['heading']!r} offers {modal['buttons']}")
        clicked = False
        vanished = False
        for want in DISMISSALS:
            button = page.get_by_role("button", name=re.compile(rf"^{want}$", re.I))
            if not button.count():
                continue
            candidate = button.first
            try:
                candidate.click(timeout=4000)
                clicked = True
                log(f"  dismissed it with {want!r}")
            except PlaywrightTimeout:
                # #2916: the control is disabled, or the page detached it mid-click. Wait for
                # the modal to resolve itself rather than reporting the fixture as broken.
                log(f"  {want!r} is not clickable (disabled or detached); letting it resolve")
                try:
                    page.wait_for_function(
                        "() => !document.querySelector('[role=dialog]')", timeout=8000
                    )
                    vanished = True
                    log("  the modal went away on its own — treating that as dismissed")
                except PlaywrightTimeout:
                    log(f"  {want!r} still present and still not clickable")
            break
        if not clicked and not vanished:
            log("  no control this suite knows; leaving it alone")
            return False
        page.wait_for_timeout(1500)
    return open_modal(page) is None


def intercept_library(page, seen: list) -> None:
    """Answer `/api/lessons` from the fixture and remember what the page asked for."""
    def handler(route):
        seen.append(route.request.url)
        route.fulfill(status=200, content_type="application/json", body=json.dumps(FIXTURE))
    page.route("**/api/lessons*", handler)


def wait_for_text(page, needle: str, timeout_s: int = 20) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if needle in page.inner_text("body"):
            return True
        page.wait_for_timeout(500)
    return False


def toast_node(page) -> str:
    """The frame-wide toast's own text, or an empty string."""
    return page.evaluate(r"""() => {
        const fixed = Array.from(document.querySelectorAll('div')).filter(n =>
            getComputedStyle(n).position === 'fixed' && /MisakaNet/.test(n.innerText || '') &&
            /lesson/.test(n.innerText || ''));
        return fixed.length ? fixed[fixed.length - 1].innerText.replace(/\\n/g, ' | ') : '';
    }""")


def composer(page):
    """The message composer, not the workspace chooser.

    Both carry `role=textbox` in a fresh profile, so `.first` picked the chooser and every click and keystroke
    went to an element that ignores them — while the diagnostics said the composer was right there. Picking by
    "a textbox whose label is not the chooser's" is what the page actually means.
    """
    boxes = page.locator('[role="textbox"]')
    for index in range(boxes.count()):
        label = boxes.nth(index).get_attribute("aria-label") or ""
        if label and "choose" not in label.lower():
            return boxes.nth(index)
    return boxes.first


def composer_label(page) -> str:
    return page.evaluate(r"""() => {
        const box = document.querySelector('[role=textbox]');
        return box ? (box.getAttribute('aria-label') || '') : '';
    }""")


def wait_for_live_composer(page, timeout_s: int = 45) -> dict:
    """Wait for a composer that is a composer, and report what the page showed if it never is.

    A profile whose workspace record is **schema-valid** needs no help here: measured 2026-10-02 on
    `dsh 0.2.0-rc.2`, the host creates the first session by itself while the page loads, and the composer
    comes up live with no workspace to choose and no session to start. The stub — `Choose workspace` on the
    control, `Choose a workspace to start` on the composer — means the workspace record was rejected, which is
    a defect in `seed_workspace`, not a step for the browser to perform.

    So this no longer drives the chooser. It polls, and a stub is reported as a failure carrying the evidence:
    the suite's job is to notice that regression, not to paper over it. (The first version *did* drive the
    chooser, which is exactly how a rejected workspace record stayed invisible.)
    """
    def is_stub(text: str) -> bool:
        # The stub says "Choose workspace" on the control and "Choose a workspace to start" on the composer,
        # so match the word rather than either whole sentence.
        return "choose" in text.lower()

    deadline = time.time() + timeout_s
    label = composer_label(page)
    while time.time() < deadline and is_stub(label):
        page.wait_for_timeout(800)
        label = composer_label(page)
    return {
        "live": bool(label) and not is_stub(label),
        "label": label,
        "textboxes": page.evaluate("""() => Array.from(document.querySelectorAll('[role=textbox]'))
            .map(b => b.getAttribute('aria-label') || '(none)')"""),
        "body": page.inner_text("body")[:300].replace("\n", " | "),
    }


def composer_text(page) -> str:
    return page.evaluate("""() => {
        const box = document.querySelector('[role=textbox]');
        return box ? (box.innerText || '').trim() : '';
    }""")


def pick_candidate(page, needle: str = "MisakaNet") -> dict:
    """Choose the `/misakanet` row from the trigger menu.

    The menu is a portal; its rows are the trigger candidates. Matching by *role* rather than by a literal
    label keeps this working when a label is translated, and the diagnostics it returns are what a failing CI
    run needs to say why it could not find one.

    Click the **matched row**, not `get_by_text(needle).first`. The shell has other elements that say
    "MisakaNet" — the left sidebar lists the plugin by that name — and `.first` in DOM order is that sidebar
    row, not the portal. Measured 2026-10-02: clicking the sidebar row leaves the composer unclaimed
    (`data-phase="plain"`), so the query is never sent and the overlay never opens; clicking the menu row
    moves the composer to `data-phase="claimed"` and the request goes out.
    """
    deadline = time.time() + 12
    while time.time() < deadline:
        rows = page.locator("[role=option],[role=menuitem],li").filter(
            has_text=re.compile(re.escape(needle), re.I))
        candidates = page.evaluate(r"""(needle) => Array.from(
                document.querySelectorAll('[role=option],[role=menuitem],li'))
            .map(e => (e.innerText || '').replace(/\s+/g, ' ').trim())
            .filter(text => text && text.toLowerCase().includes(needle.toLowerCase()))""", needle)
        if rows.count():
            rows.first.click(timeout=8000)
            return {"candidates": candidates[:3], "picked": candidates[0] if candidates else ""}
        page.wait_for_timeout(600)
    return {"candidates": [], "picked": ""}


def scenario_slash_overlay(page, seen: list) -> dict:
    """`/misakanet <query>` answers in the composer, and the page asked the library correctly."""
    box = composer(page)
    box.click(timeout=15000)
    page.wait_for_timeout(400)
    focused = page.evaluate("""() => {
        const a = document.activeElement;
        return a ? ((a.getAttribute('role') || a.tagName) + ':' +
            (a.getAttribute('data-placeholder') || a.getAttribute('aria-label') || '').slice(0, 40)) : null;
    }""")
    # `locator.type` focuses the element itself before typing; `keyboard.type` only types into whatever
    # already has focus, which in a just-booted profile is not the composer and silently goes nowhere.
    box.type("/misakanet", delay=60)
    page.wait_for_timeout(2000)
    after_typing = composer_text(page)
    picked = pick_candidate(page)
    claimed = composer_text(page).startswith("/misakanet")
    page.wait_for_timeout(1000)
    page.keyboard.type("pip install timeout", delay=40)
    page.keyboard.press("Enter")
    appeared = wait_for_text(page, "Reads are anonymous", timeout_s=25)
    # Poll for the row instead of reading the body once. The overlay's footer and its rows are painted by the
    # same render, but the frame-wide toast fires on the same result, and a single read can land between
    # "the overlay is up" and "the row is painted" — measured 2026-10-02, where the toast named the row while
    # the immediate body read did not.
    row_shown = wait_for_text(page, "pip install Network Timeout", timeout_s=15)
    detail = {
        "focused after click": focused,
        "composer after typing": after_typing[:40],
        "menu": picked,
        "composer claimed the command": claimed,
        "query sent": composer_text(page)[:60],
        "overlay appeared": appeared,
        "row rendered": row_shown,
        "requests": seen[-1:] or [],
        "asked the endpoint with q and limit": bool(
            seen and "/api/lessons" in seen[-1] and "q=pip" in seen[-1] and "limit=" in seen[-1]),
    }
    ok = bool(appeared and row_shown and detail["asked the endpoint with q and limit"])
    return {"name": "slash-overlay", "ok": ok, "detail": detail}


def scenario_frame_wide_toast(page) -> dict:
    """The result raises the frame-wide toast, and its own control removes it."""
    text = ""
    deadline = time.time() + 20
    while time.time() < deadline and not text:
        text = toast_node(page)
        if not text:
            page.wait_for_timeout(500)
    before = bool(text)
    removed = False
    if before:
        clicked = page.evaluate(r"""() => {
            const fixed = Array.from(document.querySelectorAll('div')).filter(n =>
                getComputedStyle(n).position === 'fixed' && /MisakaNet/.test(n.innerText || '') &&
                /lesson/.test(n.innerText || ''));
            const node = fixed[fixed.length - 1];
            const button = node && node.querySelector('button');
            if (!button) return false;
            button.click();
            return true;
        }""")
        page.wait_for_timeout(1800)
        removed = not toast_node(page)
    else:
        clicked = False
    return {"name": "frame-wide-toast", "ok": bool(before and clicked and removed),
            "detail": {"toast": text, "dismissed": removed}}


def scenario_settings_to_panel(page) -> dict:
    """The General-section row's voice switch is the same switch the panel shows."""
    page.get_by_role("button", name=re.compile("^Settings$", re.I)).first.click(timeout=15000)
    page.wait_for_timeout(3500)
    box = page.locator("label", has_text="Play voice cues in this browser").locator("input[type=checkbox]")
    row_present = box.count() > 0
    stored = None
    if row_present and not box.first.is_checked():
        box.first.check()
        page.wait_for_timeout(900)
    if row_present:
        stored = page.evaluate("() => localStorage.getItem('misakanet.panel.voice.v1')")
    page.keyboard.press("Escape")
    page.wait_for_timeout(1200)
    # The panel lives in the **right sidebar**, as a tab titled `MisakaNet`. Two things had to be measured
    # here (2026-10-02): the right sidebar starts closed, and `get_by_text("MisakaNet").first` is the *left*
    # sidebar's plugin row — that page carries its own voice chip, so the old assertion read a control that
    # was never wired to the panel. The panel's tab is found by its own description text, which is unique.
    chip, panel_opened = "", False
    try:
        opener = page.get_by_role("button", name=re.compile("^Open right sidebar$", re.I))
        if opener.count():
            opener.first.click(timeout=8000)
            page.wait_for_timeout(1800)
        panel_tab = page.get_by_text(re.compile("What this session asked", re.I))
        if panel_tab.count():
            panel_tab.first.click(timeout=8000)
            page.wait_for_timeout(2500)
        panel_opened = bool(re.search(r"Voice cues: (on|off)", page.inner_text("body")))
        found = re.search(r"Voice cues: (on|off)", page.inner_text("body"))
        chip = found.group(1) if found else ""
    except Exception as error:                     # the panel is the assertion, not the navigation
        log(f"panel step: {type(error).__name__}: {error}")
    return {"name": "settings-to-panel", "ok": bool(row_present and stored == "1" and chip == "on"),
            "detail": {"row present": row_present, "stored": stored,
                       "panel opened": panel_opened, "panel chip": chip}}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="e2e-shots", help="where the screenshots go")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--dsh", default=shutil.which("dsh") or "dsh")
    parser.add_argument("--home", default=None, help="reuse this DSH_HOME instead of a temp one")
    parser.add_argument("--keep", action="store_true", help="keep the host and the home for inspection")
    args = parser.parse_args()

    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    home = Path(args.home).resolve() if args.home else Path(tempfile.mkdtemp(prefix="dsh-e2e-"))
    home.mkdir(parents=True, exist_ok=True)
    shipped_home = Path(os.environ.get("DSH_HOME", ""))
    if args.home is None and shipped_home and shipped_home.resolve() == home:
        log("refusing to run against the caller's own DSH_HOME")
        return 2

    log(f"DSH_HOME={home}  dsh={args.dsh}  port={args.port}")
    kill_port(args.port)
    env = clean_env(home)
    install = subprocess.run([args.dsh, "plugin", "--profile", "web", "add", str(REPO)],
                             env=env, capture_output=True, text=True, timeout=600)
    if install.returncode != 0:
        log(install.stdout[-1500:])
        log(install.stderr[-1500:])
        return 2
    log("installed this working tree into the profile")
    seed_workspace(home)
    log("seeded one workspace (a fresh composer is inert without one)")

    log_path = home / "host.log"
    process = boot(args.dsh, home, args.port, log_path)
    results: list[dict] = []
    try:
        url = wait_for_url(log_path, args.port)
        log(f"host up: {url.split('?')[0]}")

        from playwright.sync_api import sync_playwright

        with sync_playwright() as play:
            browser = play.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
            context = browser.new_context(viewport={"width": 1400, "height": 1000})
            # bound every action: a suite that can hang is a suite CI cannot trust
            context.set_default_timeout(20000)
            page = context.new_page()
            console: list[str] = []
            page.on("pageerror", lambda error: console.append(f"pageerror: {error}"))
            seen: list[str] = []
            intercept_library(page, seen)
            page.goto(url, wait_until="domcontentloaded", timeout=120000)
            page.wait_for_timeout(9000)
            if not dismiss_modals(page):
                log("a dialog is still open; the scenarios cannot click through it")

            composer_state = wait_for_live_composer(page)
            log(f"composer: {json.dumps(composer_state)[:240]}")
            if not composer_state["live"]:
                # A stub composer means the seeded workspace record was rejected. Report that one fact with
                # its evidence instead of letting three scenarios time out one after another on the same
                # unhelpful symptom — this is the regression `seed_workspace`'s timestamps exist to prevent.
                results.append({"name": "composer-live", "ok": False, "detail": composer_state})
                page.screenshot(path=str(out / "composer-live.png"))
            else:
                for scenario in (lambda: scenario_slash_overlay(page, seen),
                                 lambda: scenario_frame_wide_toast(page),
                                 lambda: scenario_settings_to_panel(page)):
                    try:
                        result = scenario()
                    except Exception as error:
                        result = {"name": "scenario", "ok": False,
                                  "detail": f"{type(error).__name__}: {error}"}
                    results.append(result)
                    log(f"{result['name']}: {'PASS' if result['ok'] else 'FAIL'} — "
                        f"{json.dumps(result['detail'])[:300]}")
                    page.screenshot(path=str(out / f"{result['name']}.png"))
            browser.close()
        if console:
            log(f"page errors: {console[:3]}")
    finally:
        if not args.keep:
            kill_port(args.port)
            try:
                process.terminate()
            except Exception:
                pass

    summary = {"scenarios": results,
               "passed": sum(1 for r in results if r["ok"]), "total": len(results),
               "dsh_home": str(home) if args.keep else "(removed)"}
    print(json.dumps(summary, indent=2), flush=True)

    if not args.keep:
        # Last, and after the verdict: a profile's node_modules tree takes a while to unlink, and a slow
        # cleanup must not look like a hung suite.
        log(f"removing {home}")
        shutil.rmtree(home, ignore_errors=True)
    return 0 if results and all(r["ok"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
