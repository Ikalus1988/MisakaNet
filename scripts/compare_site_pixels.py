#!/usr/bin/env python3
"""Pixel comparison for the static site — the gate issue #3541 asks for.

    python3 scripts/compare_site_pixels.py capture --out .cache/pixel-baseline
    python3 scripts/compare_site_pixels.py compare --before A --after B [--json OUT.json]

**Why this file exists.** #3541's own acceptance is "only numeric gates and pixel comparison,
not subjective scoring", and `docs/maintainer/handoff-2026-10-20.md` §121.5 says a visual change
is accepted when the pixels say so: for every page, how many pixels moved and whether the change
was a *recolour* (the intended work) or a *layout shift* (text reflowing, elements displaced —
the thing a reviewer has to catch by eye before this file existed).

**Why it is not a screenshot archive.** Comparing PNGs by hand does not scale to 14 pages × 3
viewports, so this file does the comparing: it captures the tree twice, then diffs the two runs
and prints, per page and viewport, the differing pixel count, the ratio, the bounding boxes of
where the differences are, and a separate verdict for each region — *recolour* or *layout shift*.

**How the two verdicts are told apart.** A recolour changes what a pixel *is* without moving it:
the element is still there, it is a different colour. A layout shift moves the element, so the
pixels where it used to be are now background and the pixels where it is now were background
before. That gives one clean signal, and this file uses it three ways:

  * *Per pixel.* Every differing pixel is classified against each image's **own** background
    colour (the modal colour of that image): background→foreground is *content appeared*,
    foreground→background is *content vanished*, anything else is a *recolour*. Because each side
    is measured against its own background, a page-wide background recolour stays a recolour:
    the background is background in both images.
  * *Per region.* The differing pixels are grouped into regions (the bounding boxes a reviewer
    needs) and each region reports its own mix of appeared / vanished / recoloured pixels. A
    moved element produces a region that is part of each — it is reported as *content-moved*.
  * *Per page.* A page is flagged as a layout shift when the foreground/background membership of
    its differing pixels flips, or when a band of rows or columns loses its content while another
    band gains it — which is what a reflow looks like from above.

**The capture is deterministic on purpose.** Animations, transitions and the caret are disabled
through an injected stylesheet, the viewport and device scale factor are pinned, the fonts are
awaited, the network is allowed to go quiet, and then the page is given a fixed settle delay.
Without those five things the same tree renders differently twice and every diff is noise. A
sixth thing is not a setting but a check: the page is shot again after a pause, and if the two
shots are not byte-identical the page was still changing, so the shot is repeated. A page that
never stops changing is reported as such rather than quietly written down as a baseline.

**The site is served over HTTP, not `file://`.** The pages fetch `locales/*.json` and
`community/voices.json`, and they link `/favicon.ico` and `/assets/...` absolutely; under
`file://` those resolve to the filesystem and the page renders something the site never serves.

**The default tolerance is a measured number, not a guess.** `--tolerance` used to default to `0`,
which means "a page fails if a single pixel differs at all" — and Chromium's text antialiasing is
not bit-identical between runs, so the gate could go red on a tree nobody had touched. The
measurement below is what the default is built on.

*What was measured* (commit `e799d0c2`, 2026-10-22): the page `insights/reputation-leaderboard`
at viewport 1280×800, captured four times in a row from the same tree with `--proxy direct`, then
compared pairwise at tolerance 0:

| pair | differing pixels | max channel delta |
|---|---|---|
| run1 vs run2 | 20 | 1 |
| run2 vs run3 | 20 | 1 |
| run3 vs run4 | 0 | 0 |
| run1 vs run4 | 0 | 0 |

20 pixels out of 1,024,000 (0.0020%), classified *recolour*, in 8×8 patches, with **one-level**
channel differences (`[30,35,43]` → `[31,36,44]`).

*Two explanations were tested and both were wrong*, so the next reader does not have to test them
again: the page does not fetch live data (the local server answers the API URL with 404,
`response.json()` throws, the catch branch renders one fixed sentence and `render(data)` never
runs), and the webfont is not the cause (with `--proxy direct` no external asset is fetched at
all, and the same 20 pixels still move). What is left is Chromium's own text antialiasing: the
two crops are identical to the eye, and the difference is a one-step channel shift on glyph edges.

*So the floor on that page is one channel step*, and the default tolerance is **3**. The whole
default page set, captured four times (six pairs per page/viewport), measures it higher: the
largest *rendering-noise* step anywhere in the set is **3** — two pixels of the homepage's
`768x1024` view — and at tolerance 3 every one of the 51 page/viewport combinations comes back
with **0 differing pixels**. So the default sits exactly on the measured floor, not above it; a
run that renders one step noisier would measure 4.

*And the noise is orders of magnitude below a real change.* Recolouring one heading on
`insights/reputation-leaderboard` moves **3,490** pixels — 174× the noise, and a ratio of 0.34%
against a threshold of 0. The tolerance decides which pixels count as different; the threshold
decides how many may, and that stays at 0.

*The whole default page set, captured twice* (same commit, same tree, 17 pages × 3 viewports):
15 of the 17 pages came back byte-identical, `insights/reputation-leaderboard` differed by the
20 noise pixels above, and the **homepage** differed by 75–79 pixels with a channel step of up
to *150*. That third one is not antialiasing. The crop shows `快照生成于52分钟前` in one capture
and `快照生成于53分钟前` in the next: the homepage prints the age of `data/feed.json` against the
wall clock (`getTimeAgo()` in `docs/index.html`), so the rendered text changes every minute for
the first hour after the feed is rebuilt — and a full capture takes 1m42s, so a before/after
pair is always more than a minute apart. Outside that hour the homepage is stable again, which is
why the four-capture run above finds nothing there.

**A tolerance cannot fix that, and must not be raised to cover it.** A 150-step difference is
content, not noise; silencing it would silence every real change with it. It is a
capture-determinism defect — the same class as the animation freeze above — and it is why
`noise-floor` tells the two kinds of difference apart instead of reporting one number.

*How to re-measure it* — one command, no browser change:

    python3 scripts/compare_site_pixels.py noise-floor --docs-root docs --runs 4

`noise-floor` captures the page set N times, compares every pair, and reports the worst pairwise
difference, the largest single-channel step it saw, and — through the same foreground/background
test the layout-shift verdict uses — whether that difference is *rendering noise* (the tolerance
is the lever) or a *content change* (a tolerance must not touch it). It exits `1` when the default
tolerance does not reproduce the page set, and the report says which of the two is at fault. Its
`--pages` filter is hidden from `--help`, exactly as it is on `capture`.

Exit codes: `0` pass, `1` the gate failed (a page over `--threshold`, or a layout shift), `2` a
usage or environment error. `noise-floor` exits `0` when the default tolerance reproduces every
page of the set, and `1` when it does not.
"""
from __future__ import annotations

import argparse
import contextlib
import functools
import http.server
import importlib
import json
import os
import re
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

# The three viewports the previous batch shipped: a phone, a tablet and a laptop. Same numbers as
# the screenshots in `docs/maintainer/handoff-2026-10-20.md` §121.5, so a review can compare this
# harness's output against the batch it is meant to replace.
VIEWPORTS: tuple[tuple[str, int, int], ...] = (
    ("390x844", 390, 844),
    ("768x1024", 768, 1024),
    ("1280x800", 1280, 800),
)

# The freeze stylesheet. `animations="disabled"` in the screenshot call fast-forwards finite
# animations, but it cannot stop an animation that restarts on its own; `animation:none` can.
# The pseudo-element half is not decoration: the homepage's `cornerPulse` and `energyFlow` run
# on `.content-glass::before` / `::after`, and the universal selector alone does not match a
# pseudo-element — so without it the corner of the hero keeps glowing a different shade on
# every screenshot and the page never settles.
FREEZE_CSS = (
    "*,*::before,*::after{animation:none!important;transition:none!important;"
    "caret-color:transparent!important}"
)

SETTLE_MS = 600
# How long to wait between two shots of the same page while looking for a page that has stopped
# changing, and how many shots to take before giving up on it.
STABILITY_WAIT_MS = 400
STABILITY_ATTEMPTS = 4
PAGE_TIMEOUT_MS = 60_000
NETWORK_IDLE_TIMEOUT_MS = 8_000
# A colour is "the background" if it is within this much of the image's modal colour. Loose enough
# for anti-aliasing on large text, tight enough to tell a card from the page behind it.
BG_TOLERANCE = 12
# The share of the differing pixels whose foreground/background membership has to flip before the
# page is called a layout shift rather than a recolour.
LAYOUT_STRUCT_RATIO = 0.25

# The per-channel difference the gate ignores by default.
#
# The number is measured, not chosen: capturing the same page four times in a row moves a handful
# of pixels by **one** channel step (Chromium's text antialiasing is not bit-identical between
# runs), and over the whole default page set the largest such step is **3**. The module docstring
# carries the capture tables, the two wrong explanations that were ruled out, and the one
# difference a tolerance must *not* cover. `3` reproduces every page of the set; the threshold
# (the differing-pixel *ratio* a page may have) is untouched at 0, so a real edit still fails.
#
# Re-measure it with `compare_site_pixels.py noise-floor`, which prints the floor it observes.
DEFAULT_TOLERANCE = 3


# ── the page set ──────────────────────────────────────────────────────────────────────────────
def hand_written_pages(docs_root: Path) -> list[Path]:
    """The hand-written pages, partitioned by the one rule in `scripts/site_page_scope.py`.

    The partition is imported rather than re-implemented, and this file used to carry a fourth
    copy of the rule as its fallback — "every `docs/**/*.html` except `_partials/`, `lessons/` or
    `topics/`" — which is the same bug class the shared module exists to kill (handoff §122.3:
    "都是同一种病：两个作者各写一份"). The fallback is gone with it: the rule now has one home.

    The generated pages are *not* in this set, and that is deliberate: capturing all 585 pages at
    three viewports is tens of minutes and hundreds of megabytes. `--pages` reaches them — see
    `selectable_pages` — so the generated tree is verifiable on demand instead of invisible.
    """
    if docs_root.name == "docs":
        try:
            from site_page_scope import scoped_pages as _partition

            return _partition(docs_root.parent)
        except Exception:  # pragma: no cover - the shared partition is the only rule
            pass
    return sorted(docs_root.rglob("*.html"))


def selectable_pages(docs_root: Path) -> list[Path]:
    """Every page a reviewer may name with `--pages`: the hand-written ones and the generated ones.

    The generated tree used to be unreachable from here: `--pages` filtered the hand-written
    partition, so no lesson or topic page could ever be compared, even though the design gate
    now reads all 585 of them (§122.6 item 2).
    """
    if docs_root.name == "docs":
        try:
            from site_page_scope import gated_pages as _partition

            return _partition(docs_root.parent)
        except Exception:  # pragma: no cover - the shared partition is the only rule
            pass
    return sorted(docs_root.rglob("*.html"))


def generated_representatives(docs_root: Path) -> list[Path]:
    """One page per **generator template** — the unit of change in the generated tree.

    All 516 lesson pages come from one template (`HTML_TEMPLATE`), all 54 topic pages from
    another (`TOPIC_TEMPLATE`), and the topic index from a third (`TOPICS_INDEX_TEMPLATE`). A
    structural change to a template therefore lands on every page that template produces, so one
    page per template is the whole tree's worth of coverage for a *rendering* comparison.

    This set is what makes the generated tree visible to the tool at all: the default capture set
    used to be the 14 hand-written pages, so a change to `scripts/build_lesson_pages.py` could not
    be compared with it — the pages it writes were not in the set, and the 571 pages that the
    design gate now reads (§122.6 item 2) had no rendering check behind them at all.

    Capturing all 571 would be tens of minutes and hundreds of megabytes, so the default set stays
    small: the hand-written pages plus these three representatives.
    """
    if docs_root.name != "docs":
        return []
    try:
        from site_page_scope import generated_pages as _generated
    except Exception:  # pragma: no cover - the shared partition is the only rule
        return []

    pages = _generated(docs_root.parent)
    rel = lambda p: p.relative_to(docs_root).parts  # noqa: E731
    lessons = sorted(p for p in pages if "lessons" in rel(p))
    topics = sorted(p for p in pages if "topics" in rel(p))
    index = docs_root / "topics" / "index.html"

    representatives: list[Path] = []
    if lessons:
        representatives.append(lessons[0])
    topic_pages = [p for p in topics if p != index]
    if topic_pages:
        representatives.append(topic_pages[0])
    if index.exists():
        representatives.append(index)
    return representatives


def default_pages(docs_root: Path) -> list[Path]:
    """The pages a capture takes when nobody names any: the hand-written ones and the
    generated tree's per-template representatives."""
    return hand_written_pages(docs_root) + generated_representatives(docs_root)


def capture_pages(docs_root: Path, only: list[str] | None) -> list[Path]:
    """The pages a capture takes: the default set, or the named subset of it.

    One rule, one home. `capture` and `noise-floor` both go through here, so the measurement the
    noise floor is based on is taken over exactly the pages the gate checks — a noise floor
    measured on a different page set is not the gate's noise floor.
    """
    pages = selectable_pages(docs_root) if only else default_pages(docs_root)
    if only:
        wanted = set(only)
        pages = [p for p in pages if page_id(p.relative_to(docs_root)) in wanted]
    return pages


def page_id(rel: Path) -> str:
    """A filesystem-safe name for a page, used in the PNG file names."""
    stem = rel.with_suffix("").as_posix()
    return re.sub(r"[^A-Za-z0-9._-]+", "__", stem)


def image_name(pid: str, viewport: str) -> str:
    return f"{pid}__{viewport}.png"


def parse_image_name(name: str) -> tuple[str, str] | None:
    """`insights__pr-genius__390x844.png` → `("insights__pr-genius", "390x844")`."""
    if not name.endswith(".png"):
        return None
    stem = name[:-4]
    for key, _w, _h in VIEWPORTS:
        suffix = f"__{key}"
        if stem.endswith(suffix):
            return stem[: -len(suffix)], key
    return None


# ── the optional heavy dependencies ───────────────────────────────────────────────────────────
_NUMPY: Any = None
_PIL: Any = None


def _np() -> Any:
    """numpy, imported once. It is only needed to compare two images."""
    global _NUMPY
    if _NUMPY is None:
        try:
            _NUMPY = importlib.import_module("numpy")
        except ImportError as exc:
            raise SystemExit(
                "the `numpy` package is missing; install it into the repo venv with "
                "`uv pip install numpy`"
            ) from exc
    return _NUMPY


def _pil() -> Any:
    """PIL.Image, imported once. It is only needed to read a PNG."""
    global _PIL
    if _PIL is None:
        try:
            _PIL = importlib.import_module("PIL.Image")
        except ImportError as exc:
            raise SystemExit(
                "the `pillow` package is missing; install it into the repo venv with "
                "`uv pip install pillow`"
            ) from exc
    return _PIL


# ── the local server ───────────────────────────────────────────────────────────────────────────
class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args: Any) -> None:  # noqa: D102 - silence the access log
        pass


@contextlib.contextmanager
def serve(docs_root: Path):
    """Serve `docs_root` on 127.0.0.1 for the length of the block, and shut it down after."""
    handler = functools.partial(_QuietHandler, directory=str(docs_root))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    httpd.daemon_threads = True
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}"
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def _no_proxy_env() -> None:
    """Make sure the loopback server is reached directly, never through the HTTP proxy.

    The machine sits behind a proxy, and the proxy is not on this machine's loopback interface —
    a request for `http://127.0.0.1:PORT` that goes through it comes back as a failure from the
    proxy's own point of view. Chromium honours `no_proxy` for that, and so does anything else
    this process starts.
    """
    existing = os.environ.get("no_proxy") or os.environ.get("NO_PROXY") or ""
    hosts = [h for h in existing.split(",") if h]
    for host in ("127.0.0.1", "localhost"):
        if host not in hosts:
            hosts.insert(0, host)
    value = ",".join(hosts)
    os.environ["no_proxy"] = value
    os.environ["NO_PROXY"] = value


def _proxy_settings() -> dict[str, str] | None:
    """The upstream proxy, with loopback excluded.

    The site loads its web fonts from `fonts.googleapis.com`. Without the proxy they fall back to
    whatever the machine has locally, which renders differently from production — so the proxy is
    used for the outside world and bypassed for the local server.
    """
    server = (
        os.environ.get("https_proxy")
        or os.environ.get("HTTPS_PROXY")
        or os.environ.get("http_proxy")
        or os.environ.get("HTTP_PROXY")
    )
    if not server:
        return None
    return {"server": server, "bypass": "127.0.0.1,localhost,127.0.0.1:*"}


def chromium_executable() -> str | None:
    """A cached Chromium to drive, if the one Playwright wants is not installed.

    The Python package and the browser build move independently, and a machine that has
    `chromium-1243` cached but a Playwright that expects `chromium-1248` will not launch. The
    cached build is close enough to drive, and using it avoids a 150 MB download mid-review.
    `PLAYWRIGHT_CHROMIUM_EXECUTABLE` overrides the search.
    """
    override = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE")
    if override:
        return override
    cache = Path(
        os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
        or (Path.home() / ".cache" / "ms-playwright")
    )
    if not cache.is_dir():
        return None
    patterns = (
        "chromium-*/chrome-linux*/chrome",
        "chromium-*/chrome-linux/chrome",
        "chromium_headless_shell-*/chrome-headless-shell-linux*/chrome-headless-shell",
        "chromium_headless_shell-*/chrome-linux/chrome-headless-shell",
    )
    for pattern in patterns:
        found = sorted(cache.glob(pattern), reverse=True)
        if found:
            return str(found[0])
    return None


# ── capture ────────────────────────────────────────────────────────────────────────────────────
@dataclass
class CaptureRecord:
    page: str
    viewport: str
    image: str
    width: int = 0
    height: int = 0
    scroll_width: int = 0
    scroll_height: int = 0
    fonts_loaded: bool = False
    stable: bool = True
    error: str = ""


# Installed before the document exists, so an animation that starts on load never gets a frame
# in; the same stylesheet is installed again after load, for the same reason. The `install()`
# function has to tolerate being called before there is a `<head>` to append to: at document-start
# `document.documentElement` is still null, and a stylesheet that is never installed is a page
# that animates through the whole capture.
INIT_SCRIPT = """
(() => {
  const css = __FREEZE_CSS__;
  const install = () => {
    if (document.getElementById('__pixel_freeze__')) return;
    const target = document.head || document.documentElement || document.body;
    if (!target) return;
    const style = document.createElement('style');
    style.id = '__pixel_freeze__';
    style.textContent = css;
    target.appendChild(style);
  };
  install();
  document.addEventListener('DOMContentLoaded', install);
  new MutationObserver(install).observe(document, { childList: true, subtree: true });
})();
"""


# Every image is forced to load, including the lazy ones below the fold, and the page waits for
# them. A badge that arrives after the screenshot was taken is a badge that is in one capture and
# not in the next — on the homepage that is a 0.2% difference that nobody changed.
IMAGE_WAIT_JS = """
async () => {
  const images = Array.from(document.images);
  for (const image of images) { image.loading = 'eager'; }
  await Promise.all(images.map((image) => (
    image.complete
      ? Promise.resolve()
      : new Promise((resolve) => {
          image.addEventListener('load', resolve, { once: true });
          image.addEventListener('error', resolve, { once: true });
          setTimeout(resolve, 5000);
        })
  )));
  return images.length;
}
"""


def _capture_one(
    browser,
    url: str,
    out_path: Path,
    viewport: tuple[str, int, int],
    settle_ms: int,
    stability_attempts: int,
    stability_wait_ms: int,
) -> dict[str, Any]:
    _key, width, height = viewport
    context = browser.new_context(
        viewport={"width": width, "height": height},
        device_scale_factor=1,
        locale="zh-CN",
        timezone_id="UTC",
        color_scheme="light",
        reduced_motion="reduce",
        forced_colors="none",
    )
    try:
        context.add_init_script(INIT_SCRIPT.replace("__FREEZE_CSS__", json.dumps(FREEZE_CSS)))
        page = context.new_page()
        response = page.goto(url, wait_until="load", timeout=PAGE_TIMEOUT_MS)
        if response is not None and not response.ok:
            raise RuntimeError(f"HTTP {response.status} for {url}")
        page.evaluate("() => document.fonts.ready.then(() => true)")
        page.add_style_tag(content=FREEZE_CSS)
        try:
            page.evaluate(IMAGE_WAIT_JS, timeout=PAGE_TIMEOUT_MS)
        except Exception:
            # A page whose images never resolve is a page whose images never resolve; the
            # stability check below is the second line of defence.
            pass
        try:
            page.wait_for_load_state("networkidle", timeout=NETWORK_IDLE_TIMEOUT_MS)
        except Exception:
            # A page that keeps a connection open never goes idle. That is a warning, not a
            # failure: the fonts have settled and the settle delay below still applies.
            pass
        page.wait_for_timeout(settle_ms)
        metrics = page.evaluate(
            """() => ({
                scrollWidth: document.documentElement.scrollWidth,
                scrollHeight: document.documentElement.scrollHeight,
                fonts: document.fonts.status,
            })"""
        )
        # A page that draws its content late — a chart that arrives on a timer, a list fetched
        # after `load` — is otherwise captured mid-render, and the *next* run captures the
        # finished page. That reads as a 48% change when nothing changed at all. So the page is
        # shot repeatedly until two consecutive shots are byte-identical; a page that never
        # settles is reported, not quietly accepted.
        shot = b""
        previous: bytes | None = None
        stable = False
        for _attempt in range(stability_attempts):
            shot = page.screenshot(
                full_page=True,
                animations="disabled",
                caret="hide",
                scale="css",
            )
            if previous is not None and shot == previous:
                stable = True
                break
            previous = shot
            page.wait_for_timeout(stability_wait_ms)
        out_path.write_bytes(shot)
        return {
            "width": width,
            "height": height,
            "scroll_width": int(metrics.get("scrollWidth") or 0),
            "scroll_height": int(metrics.get("scrollHeight") or 0),
            "fonts_loaded": metrics.get("fonts") == "loaded",
            "stable": stable,
        }
    finally:
        context.close()


def capture(
    docs_root: Path,
    out_dir: Path,
    settle_ms: int = SETTLE_MS,
    proxy: str = "env",
    only: list[str] | None = None,
    stability_attempts: int = STABILITY_ATTEMPTS,
    stability_wait_ms: int = STABILITY_WAIT_MS,
) -> tuple[list[CaptureRecord], list[str]]:
    """Screenshot every page at every viewport. Returns (records, warnings)."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise SystemExit(
            "the `playwright` package is missing; install it into the repo venv with "
            "`uv pip install playwright`"
        ) from exc

    _no_proxy_env()
    docs_root = docs_root.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    pages = capture_pages(docs_root, only)
    if not pages:
        raise SystemExit(f"no pages found under {docs_root}")

    records: list[CaptureRecord] = []
    warnings: list[str] = []
    executable = chromium_executable()
    proxy_settings = _proxy_settings() if proxy == "env" else None

    with serve(docs_root) as base_url:
        with sync_playwright() as pw:
            launch_kwargs: dict[str, Any] = {"headless": True}
            if executable:
                launch_kwargs["executable_path"] = executable
            if proxy_settings:
                launch_kwargs["proxy"] = proxy_settings
            launch_kwargs["args"] = [
                # Scrollbars take layout space in some Chromium builds; pinning them off keeps the
                # layout width exactly the viewport width on every machine.
                "--hide-scrollbars",
                # A display profile other than sRGB shifts every colour in the image.
                "--force-color-profile=srgb",
            ]
            browser = pw.chromium.launch(**launch_kwargs)
            try:
                for page_path in pages:
                    rel = page_path.relative_to(docs_root)
                    pid = page_id(rel)
                    url = f"{base_url}/{rel.as_posix()}"
                    for viewport in VIEWPORTS:
                        key = viewport[0]
                        out_path = out_dir / image_name(pid, key)
                        record = CaptureRecord(page=pid, viewport=key, image=out_path.name)
                        try:
                            metrics = _capture_one(
                                browser,
                                url,
                                out_path,
                                viewport,
                                settle_ms,
                                stability_attempts,
                                stability_wait_ms,
                            )
                            record.width = metrics["width"]
                            record.height = metrics["height"]
                            record.scroll_width = metrics["scroll_width"]
                            record.scroll_height = metrics["scroll_height"]
                            record.fonts_loaded = metrics["fonts_loaded"]
                            record.stable = metrics["stable"]
                            if not metrics["fonts_loaded"]:
                                warnings.append(f"{pid} @{key}: fonts did not report 'loaded'")
                            if not metrics["stable"]:
                                warnings.append(
                                    f"{pid} @{key}: page did not stop changing after "
                                    f"{stability_attempts} shots — the image may be mid-render"
                                )
                        except Exception as exc:
                            record.error = f"{type(exc).__name__}: {exc}"
                        records.append(record)
            finally:
                browser.close()
    return records, warnings


# ── compare ────────────────────────────────────────────────────────────────────────────────────
def _load_rgb(path: Path) -> Any:
    """A PNG as an int16 RGB array."""
    np = _np()
    pil = _pil()
    with pil.open(path) as handle:
        return np.asarray(handle.convert("RGB"), dtype=np.int16)


def _modal_color(rgb: Any) -> Any:
    """The image's background colour: the mean colour of its most common colour bucket."""
    np = _np()
    height, width = rgb.shape[0], rgb.shape[1]
    step = max(1, (height * width) // 200_000)
    sample = rgb[::step, ::step].reshape(-1, 3)
    quantised = (sample >> 4).astype(np.int32)
    key = quantised[:, 0] * 256 + quantised[:, 1] * 16 + quantised[:, 2]
    values, counts = np.unique(key, return_counts=True)
    winner = values[int(counts.argmax())]
    return sample[key == winner].mean(axis=0)


def _content_mask(rgb: Any, bg: Any) -> Any:
    """Everything that is not the background — the page's foreground, whatever colour it is."""
    np = _np()
    distance = np.abs(rgb - bg.astype(np.int16)).max(axis=2)
    return distance > BG_TOLERANCE


def _block_components(occupied: Any) -> Any:
    """Label the occupied cells of a grid, 4-connected. Returns an int32 label array."""
    np = _np()
    height, width = occupied.shape
    labels = np.full((height, width), -1, dtype=np.int32)
    current = 0
    for sy, sx in np.argwhere(occupied):
        sy, sx = int(sy), int(sx)
        if labels[sy, sx] != -1:
            continue
        stack = [(sy, sx)]
        labels[sy, sx] = current
        while stack:
            y, x = stack.pop()
            for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                if 0 <= ny < height and 0 <= nx < width:
                    if occupied[ny, nx] and labels[ny, nx] == -1:
                        labels[ny, nx] = current
                        stack.append((ny, nx))
        current += 1
    return labels


def _regions(mask: Any, block: int) -> list[dict[str, Any]]:
    """Group differing pixels into regions.

    The mask is first reduced to a grid of `block`×`block` cells — a cell counts as different if
    any of its pixels differs — and the connected cells are grouped. Grouping at cell level keeps
    the scan linear in the number of cells rather than in the number of pixels, which is what makes
    a 1280×8000 full-page capture tractable. The pixel count of a region is the sum of its cells,
    so the regions add up to the whole difference without double counting.
    """
    np = _np()
    height, width = mask.shape
    bh = (height + block - 1) // block
    bw = (width + block - 1) // block
    padded = np.zeros((bh * block, bw * block), dtype=bool)
    padded[:height, :width] = mask
    counts = padded.reshape(bh, block, bw, block).sum(axis=(1, 3))
    occupied = counts > 0
    if not occupied.any():
        return []
    labels = _block_components(occupied)
    # One pass over the cells, not one pass per region: a page with a thousand small differences
    # must not cost a thousand scans of the whole grid.
    flat_labels = labels.ravel()
    filled = flat_labels >= 0
    cell_labels = flat_labels[filled]
    cell_counts = counts.ravel()[filled]
    cells_y, cells_x = np.nonzero(filled.reshape(labels.shape))
    number = int(cell_labels.max()) + 1
    y_min = np.full(number, height, dtype=np.int64)
    y_max = np.full(number, -1, dtype=np.int64)
    x_min = np.full(number, width, dtype=np.int64)
    x_max = np.full(number, -1, dtype=np.int64)
    np.minimum.at(y_min, cell_labels, cells_y)
    np.maximum.at(y_max, cell_labels, cells_y)
    np.minimum.at(x_min, cell_labels, cells_x)
    np.maximum.at(x_max, cell_labels, cells_x)
    pixel_totals = np.bincount(cell_labels, weights=cell_counts, minlength=number)
    regions: list[dict[str, Any]] = []
    for label in range(number):
        if y_max[label] < 0:
            continue
        y0 = int(y_min[label]) * block
        y1 = min(height, (int(y_max[label]) + 1) * block)
        x0 = int(x_min[label]) * block
        x1 = min(width, (int(x_max[label]) + 1) * block)
        regions.append(
            {
                "label": label,
                "bbox": [x0, y0, x1, y1],
                "diff_pixels": int(pixel_totals[label]),
            }
        )
    regions.sort(key=lambda r: r["diff_pixels"], reverse=True)
    return regions


def _band_displacement(mask_before: Any, mask_after: Any) -> tuple[bool, bool]:
    """Did a band of rows (or columns) lose its content while another band gained it?

    That is what a displaced element looks like from above: the rows it used to occupy go quiet
    and the rows it now occupies wake up. A recolour leaves every row exactly as busy as it was.
    """
    np = _np()
    vertical = False
    horizontal = False
    rows_before = mask_before.any(axis=1)
    rows_after = mask_after.any(axis=1)
    lost_rows = np.nonzero(rows_before & ~rows_after)[0]
    gained_rows = np.nonzero(rows_after & ~rows_before)[0]
    if lost_rows.size and gained_rows.size:
        if int(gained_rows.min()) > int(lost_rows.max()):
            vertical = True
        if int(lost_rows.min()) > int(gained_rows.max()):
            vertical = True
    cols_before = mask_before.any(axis=0)
    cols_after = mask_after.any(axis=0)
    lost_cols = np.nonzero(cols_before & ~cols_after)[0]
    gained_cols = np.nonzero(cols_after & ~cols_before)[0]
    if lost_cols.size and gained_cols.size:
        if int(gained_cols.min()) > int(lost_cols.max()):
            horizontal = True
        if int(lost_cols.min()) > int(gained_cols.max()):
            horizontal = True
    return vertical, horizontal


def _region_verdict(
    before: Any, after: Any, mask: Any, bg_before: Any, bg_after: Any
) -> tuple[dict[str, float], str]:
    """Split a region's differing pixels into appeared / vanished / recoloured.

    Each side is measured against its own image's background, so a region that is background in
    both images is a recolour of the background, not content that appeared.
    """
    np = _np()
    before_bg = np.abs(before - bg_before.astype(np.int16)).max(axis=2) <= BG_TOLERANCE
    after_bg = np.abs(after - bg_after.astype(np.int16)).max(axis=2) <= BG_TOLERANCE
    count = int(mask.sum())
    if count == 0:
        return ({"appeared": 0.0, "vanished": 0.0, "recoloured": 0.0}, "recolour")
    appeared = int(np.logical_and(mask, np.logical_and(before_bg, ~after_bg)).sum())
    vanished = int(np.logical_and(mask, np.logical_and(~before_bg, after_bg)).sum())
    recoloured = count - appeared - vanished
    fractions = {
        "appeared": appeared / count,
        "vanished": vanished / count,
        "recoloured": recoloured / count,
    }
    if fractions["appeared"] >= 0.2 and fractions["vanished"] >= 0.2:
        verdict = "content-moved"
    elif fractions["appeared"] >= 0.5:
        verdict = "content-appeared"
    elif fractions["vanished"] >= 0.5:
        verdict = "content-vanished"
    else:
        verdict = "recolour"
    return fractions, verdict


def compare_arrays(
    before: Any,
    after: Any,
    block: int = 8,
    tolerance: int = DEFAULT_TOLERANCE,
    max_regions: int = 12,
    layout_struct_ratio: float = LAYOUT_STRUCT_RATIO,
    before_image: str = "",
    after_image: str = "",
) -> dict[str, Any]:
    """Diff two images and say what moved.

    This is the whole comparison, over image arrays: no file, no browser, no state. The file
    based `compare_pair` is a thin wrapper around it, which is what lets the gate's verdict be
    tested with fabricated pixel data.
    """
    np = _np()
    result: dict[str, Any] = {
        "before_image": before_image,
        "after_image": after_image,
        "before_size": [int(before.shape[1]), int(before.shape[0])],
        "after_size": [int(after.shape[1]), int(after.shape[0])],
        "size_changed": False,
        "total_pixels": 0,
        "diff_pixels": 0,
        "diff_ratio": 0.0,
        "tolerance": tolerance,
        "layout_shift": False,
        "layout_reasons": [],
        "regions": [],
        "region_count": 0,
    }

    size_changed = before.shape != after.shape
    result["size_changed"] = size_changed
    if size_changed:
        # The page grew or shrank: compare the overlapping area for the detail and let the size
        # change itself count as a layout shift, because it can only come from a reflow.
        height = min(before.shape[0], after.shape[0])
        width = min(before.shape[1], after.shape[1])
        before = before[:height, :width]
        after = after[:height, :width]

    height, width = before.shape[0], before.shape[1]
    total = height * width
    result["total_pixels"] = total
    if total == 0:
        return result

    difference = np.abs(before - after).max(axis=2)
    mask = difference > tolerance
    diff_pixels = int(mask.sum())
    result["diff_pixels"] = diff_pixels
    result["diff_ratio"] = diff_pixels / total
    if diff_pixels == 0:
        return result

    bg_before = _modal_color(before)
    bg_after = _modal_color(after)
    content_before = _content_mask(before, bg_before)
    content_after = _content_mask(after, bg_after)

    regions = _regions(mask, block)
    result["region_count"] = len(regions)
    for region in regions:
        x0, y0, x1, y1 = region["bbox"]
        sub_before = before[y0:y1, x0:x1]
        sub_after = after[y0:y1, x0:x1]
        sub_mask = mask[y0:y1, x0:x1]
        fractions, verdict = _region_verdict(
            sub_before, sub_after, sub_mask, bg_before, bg_after
        )
        count = int(sub_mask.sum())
        if count:
            mean_before = sub_before[sub_mask].mean(axis=0).round().astype(int)
            mean_after = sub_after[sub_mask].mean(axis=0).round().astype(int)
        else:
            mean_before = mean_after = np.zeros(3, dtype=int)
        region["verdict"] = verdict
        region["appeared"] = round(fractions["appeared"], 4)
        region["vanished"] = round(fractions["vanished"], 4)
        region["recoloured"] = round(fractions["recoloured"], 4)
        region["mean_before_rgb"] = [int(v) for v in mean_before]
        region["mean_after_rgb"] = [int(v) for v in mean_after]
        region["diff_ratio"] = region["diff_pixels"] / total
    result["regions"] = regions[:max_regions]
    result["regions_truncated"] = max(0, len(regions) - max_regions)

    # The page-level version of the same question: over every differing pixel of the page, how
    # many changed their foreground/background membership?
    before_bg, after_bg = content_membership(before, after)
    appeared = int(np.logical_and(mask, np.logical_and(before_bg, ~after_bg)).sum())
    vanished = int(np.logical_and(mask, np.logical_and(~before_bg, after_bg)).sum())
    recoloured = diff_pixels - appeared - vanished
    struct_ratio = (appeared + vanished) / diff_pixels

    reasons: list[str] = []
    if size_changed:
        reasons.append(
            f"page size changed: {result['before_size'][0]}×{result['before_size'][1]}"
            f" → {result['after_size'][0]}×{result['after_size'][1]}"
        )
    if appeared / diff_pixels >= 0.5:
        reasons.append(
            f"content appeared over {appeared / diff_pixels:.0%} of the differing pixels"
        )
    if vanished / diff_pixels >= 0.5:
        reasons.append(
            f"content vanished over {vanished / diff_pixels:.0%} of the differing pixels"
        )
    if struct_ratio >= layout_struct_ratio:
        reasons.append(
            f"foreground/background membership flipped on {struct_ratio:.1%}"
            " of the differing pixels"
        )
    vertical, horizontal = _band_displacement(content_before, content_after)
    if vertical:
        reasons.append("a band of rows lost its content while another band gained it")
    if horizontal:
        reasons.append("a band of columns lost its content while another band gained it")
    result["layout_shift"] = bool(reasons)
    result["layout_reasons"] = reasons
    result["struct_ratio"] = round(struct_ratio, 6)
    result["appeared_pixels"] = appeared
    result["vanished_pixels"] = vanished
    result["recoloured_pixels"] = recoloured
    result["background_before_rgb"] = [int(v) for v in bg_before.round()]
    result["background_after_rgb"] = [int(v) for v in bg_after.round()]
    return result


def compare_pair(
    before_path: Path,
    after_path: Path,
    block: int = 8,
    tolerance: int = DEFAULT_TOLERANCE,
    max_regions: int = 12,
    layout_struct_ratio: float = LAYOUT_STRUCT_RATIO,
) -> dict[str, Any]:
    """Diff two PNGs and say what moved."""
    return compare_arrays(
        _load_rgb(before_path),
        _load_rgb(after_path),
        block=block,
        tolerance=tolerance,
        max_regions=max_regions,
        layout_struct_ratio=layout_struct_ratio,
        before_image=before_path.name,
        after_image=after_path.name,
    )


def compare(
    before_dir: Path,
    after_dir: Path,
    block: int = 8,
    tolerance: int = DEFAULT_TOLERANCE,
    max_regions: int = 12,
    only: list[str] | None = None,
) -> dict[str, Any]:
    """Compare two capture directories, page by page and viewport by viewport."""
    before_files = {p.name: p for p in before_dir.glob("*.png")}
    after_files = {p.name: p for p in after_dir.glob("*.png")}
    pages: dict[str, dict[str, Any]] = {}
    missing: list[dict[str, str]] = []

    for name in sorted(set(before_files) | set(after_files)):
        parsed = parse_image_name(name)
        if parsed is None:
            continue
        pid, viewport = parsed
        if only and pid not in set(only):
            continue
        if name not in before_files:
            missing.append({"page": pid, "viewport": viewport, "problem": "missing in before"})
            continue
        if name not in after_files:
            missing.append({"page": pid, "viewport": viewport, "problem": "missing in after"})
            continue
        pair = compare_pair(
            before_files[name],
            after_files[name],
            block=block,
            tolerance=tolerance,
            max_regions=max_regions,
        )
        pages.setdefault(pid, {})[viewport] = pair

    # The tolerance travels with the report: a diff count without the tolerance that produced it
    # is ambiguous, and the noise floor is the reason the tolerance exists.
    return {"pages": pages, "missing": missing, "tolerance": tolerance}


# ── the noise floor ───────────────────────────────────────────────────────────────────────────
def channel_delta(before: Any, after: Any) -> Any:
    """The largest absolute difference between two images, pixel by pixel.

    The gate compares images channel by channel: a pixel counts as different when one of its
    three channels moved by more than the tolerance. This array is that per-pixel number.
    """
    np = _np()
    return np.abs(before - after).max(axis=2)


def content_membership(before: Any, after: Any) -> tuple[Any, Any]:
    """Which pixels are background on each side: (before_is_background, after_is_background).

    Each side is measured against its own image's background, so a page-wide background recolour
    stays a recolour: the background is background in both images.
    """
    np = _np()
    bg_before = _modal_color(before)
    bg_after = _modal_color(after)
    before_bg = np.abs(before - bg_before.astype(np.int16)).max(axis=2) <= BG_TOLERANCE
    after_bg = np.abs(after - bg_after.astype(np.int16)).max(axis=2) <= BG_TOLERANCE
    return before_bg, after_bg


def pairwise_noise(images: list[Any], tolerance: int = DEFAULT_TOLERANCE) -> dict[str, Any]:
    """How much two captures of the same page differ from each other.

    `images` are N RGB arrays of the same page, captured from the same tree. Every pair is
    compared, because the gate has to survive the *worst* pair and not the average one.

    The result answers four questions at once:

      * `max_diff_pixels` — how many pixels move between two runs at tolerance 0, i.e. the raw
        capture noise;
      * `max_channel_delta` — the largest single-channel step anywhere in the runs, which is the
        smallest tolerance that would silence all of it;
      * `diff_pixels` — how many pixels still differ once `tolerance` is applied, which is what
        the gate would actually see;
      * `content_share` — the share of the differing pixels whose foreground/background
        membership *flipped*.

    That last number is what separates the two kinds of difference. A pixel that stayed the same
    content in a slightly different shade is rendering noise, and the tolerance is the lever. A
    pixel that was content and is now background — or the other way round — is the content itself
    changing, and no tolerance may paper over it. The tool already draws that line for the
    layout-shift verdict (`LAYOUT_STRUCT_RATIO`); here it is used to keep the noise floor honest.

    This is a pure function over image arrays: no browser, no files, no state.
    """
    np = _np()
    runs = len(images)
    result: dict[str, Any] = {
        "runs": runs,
        "pairs": runs * (runs - 1) // 2,
        "max_diff_pixels": 0,
        "max_channel_delta": 0,
        "diff_pixels": 0,
        "content_share": 0.0,
        "min_tolerance_to_silence": 0,
        "verdict": "stable",
    }
    if runs < 2:
        return result
    for first in range(runs):
        for second in range(first + 1, runs):
            before = images[first]
            after = images[second]
            delta = channel_delta(before, after)
            raw = int((delta > 0).sum())
            tolerated = int((delta > tolerance).sum())
            if raw > result["max_diff_pixels"]:
                result["max_diff_pixels"] = raw
            if tolerated > result["diff_pixels"]:
                result["diff_pixels"] = tolerated
            result["max_channel_delta"] = max(result["max_channel_delta"], int(delta.max()))
            if not raw:
                continue
            before_bg, after_bg = content_membership(before, after)
            differing = delta > 0
            appeared = int(np.logical_and(differing, np.logical_and(before_bg, ~after_bg)).sum())
            vanished = int(np.logical_and(differing, np.logical_and(~before_bg, after_bg)).sum())
            share = (appeared + vanished) / raw
            result["content_share"] = max(result["content_share"], share)
    # A pixel differs when its channel step is *greater* than the tolerance, so the tolerance
    # that silences the worst step is exactly that step.
    result["min_tolerance_to_silence"] = result["max_channel_delta"]
    if result["diff_pixels"] == 0:
        result["verdict"] = "stable"
    elif result["content_share"] >= LAYOUT_STRUCT_RATIO:
        # The content itself moved: the difference is not rendering noise and must not be
        # silenced by a tolerance.
        result["verdict"] = "content change"
    else:
        result["verdict"] = "rendering noise"
    return result


def measure_noise_floor(
    docs_root: Path,
    runs: int = 4,
    only: list[str] | None = None,
    proxy: str = "env",
    out_dir: Path | None = None,
    tolerance: int = DEFAULT_TOLERANCE,
) -> dict[str, Any]:
    """Capture the page set `runs` times and report how much the captures differ from each other.

    This is the measurement `DEFAULT_TOLERANCE` is built on, and the way to re-check it: it uses
    the same `capture` the gate uses, over the same page set, so what it measures is what the gate
    has to survive.
    """
    if runs < 2:
        raise SystemExit("--runs must be at least 2: one capture has no pair to compare against")

    temporary: tempfile.TemporaryDirectory[str] | None = None
    if out_dir is None:
        temporary = tempfile.TemporaryDirectory(prefix="misakanet-pixel-noise-")
        root = Path(temporary.name)
    else:
        root = out_dir
        root.mkdir(parents=True, exist_ok=True)

    try:
        run_dirs: list[Path] = []
        for index in range(1, runs + 1):
            run_dir = root / f"run{index}"
            records, _warnings = capture(docs_root, run_dir, proxy=proxy, only=only)
            failures = [r for r in records if r.error]
            if failures:
                detail = "; ".join(f"{r.page} @{r.viewport}: {r.error}" for r in failures[:3])
                raise SystemExit(
                    f"capture {index} of {runs} failed, the noise floor cannot be measured: "
                    f"{detail}"
                )
            run_dirs.append(run_dir)

        pages: dict[str, dict[str, Any]] = {}
        for name in sorted({p.name for p in run_dirs[0].glob("*.png")}):
            parsed = parse_image_name(name)
            if parsed is None:
                continue
            pid, viewport = parsed
            missing = [str(run_dir) for run_dir in run_dirs if not (run_dir / name).exists()]
            if missing:
                raise SystemExit(
                    f"capture is missing {name} in {', '.join(missing)} — "
                    "the runs are not comparable"
                )
            images = [_load_rgb(run_dir / name) for run_dir in run_dirs]
            pages.setdefault(pid, {})[viewport] = pairwise_noise(images, tolerance=tolerance)

        measured = [noise for viewports in pages.values() for noise in viewports.values()]
        # The noise floor is the largest channel step among the differences that are *rendering
        # noise*. A page whose content changes between captures contributes a huge step, and
        # folding that into the floor would tell the reader to raise the tolerance high enough
        # to hide real changes — the one thing this mode must never recommend.
        noise_floor = max(
            (
                n["max_channel_delta"]
                for n in measured
                if n["verdict"] in ("stable", "rendering noise")
            ),
            default=0,
        )
        unstable = [
            {"page": pid, "viewport": viewport, **noise}
            for pid, viewports in pages.items()
            for viewport, noise in viewports.items()
            if noise["verdict"] != "stable"
        ]
        content_changes = [item for item in unstable if item["verdict"] == "content change"]
        max_channel_delta = max((n["max_channel_delta"] for n in measured), default=0)
        max_diff_pixels = max((n["max_diff_pixels"] for n in measured), default=0)
        diff_pixels = max((n["diff_pixels"] for n in measured), default=0)
        return {
            "runs": runs,
            "tolerance": tolerance,
            "pages": pages,
            "noise_floor": noise_floor,
            "unstable": unstable,
            "content_changes": content_changes,
            "max_channel_delta": max_channel_delta,
            "max_diff_pixels": max_diff_pixels,
            "diff_pixels": diff_pixels,
            "min_tolerance_to_silence": max_channel_delta,
            "silent": diff_pixels == 0,
        }
    finally:
        if temporary is not None:
            temporary.cleanup()


# ── reporting ──────────────────────────────────────────────────────────────────────────────────
def _fmt_ratio(ratio: float) -> str:
    return f"{ratio * 100:.4f}%"


def failed_pages(
    report: dict[str, Any], threshold: float, ignore_layout_shift: bool = False
) -> list[str]:
    """The pages the gate fails on: over the threshold, or moved (unless that is ignored).

    The threshold is the *ratio* a page may differ by, and it stays at 0: the tolerance decides
    which pixels count as different, never how many may differ.
    """
    failed: list[str] = []
    for pid, viewports in report["pages"].items():
        worst = max((p["diff_ratio"] for p in viewports.values()), default=0.0)
        shifted = any(p["layout_shift"] for p in viewports.values())
        if worst > threshold or (shifted and not ignore_layout_shift):
            failed.append(pid)
    failed.extend(sorted({m["page"] for m in report["missing"]}))
    return sorted(set(failed))


def print_report(report: dict[str, Any], verbose: bool = False) -> None:
    pages = report["pages"]
    print(f"{'page':<34} {'viewport':<10} {'total px':>12} {'diff px':>10} {'ratio':>11}  verdict")
    print("-" * 92)
    for pid in sorted(pages):
        for viewport in [v[0] for v in VIEWPORTS]:
            pair = pages[pid].get(viewport)
            if pair is None:
                continue
            if pair["layout_shift"]:
                flag = "SHIFT"
            elif pair["diff_pixels"]:
                flag = "recolour"
            else:
                flag = "same"
            print(
                f"{pid:<34} {viewport:<10} {pair['total_pixels']:>12,} "
                f"{pair['diff_pixels']:>10,} {_fmt_ratio(pair['diff_ratio']):>11}  {flag}"
            )
            for reason in pair["layout_reasons"]:
                print(f"{'':<34} └─ layout shift: {reason}")
            if verbose:
                for region in pair["regions"]:
                    x0, y0, x1, y1 = region["bbox"]
                    print(
                        f"{'':<34}    region {region['bbox']} ({x1 - x0}×{y1 - y0}) "
                        f"{region['diff_pixels']:,} px {_fmt_ratio(region['diff_ratio'])} — "
                        f"{region['verdict']} "
                        f"{region['mean_before_rgb']}→{region['mean_after_rgb']}"
                    )
    if report["missing"]:
        print("\nmissing captures:")
        for item in report["missing"]:
            print(f"  {item['page']} @{item['viewport']}: {item['problem']}")


def print_noise_floor(report: dict[str, Any]) -> None:
    """Print the measured noise floor and whether the default tolerance covers it."""
    pages = report["pages"]
    print(f"{'page':<34} {'viewport':<10} {'pairs':>6} {'diff px @0':>12} {'max Δch':>8} "
          f"{'content':>8} {'diff px @tol':>13}  verdict")
    print("-" * 112)
    for pid in sorted(pages):
        for viewport in [v[0] for v in VIEWPORTS]:
            noise = pages[pid].get(viewport)
            if noise is None:
                continue
            print(
                f"{pid:<34} {viewport:<10} {noise['pairs']:>6} {noise['max_diff_pixels']:>12,} "
                f"{noise['max_channel_delta']:>8} {noise['content_share'] * 100:>7.1f}% "
                f"{noise['diff_pixels']:>13,}  {noise['verdict']}"
            )
    tolerance = report["tolerance"]
    floor = report["noise_floor"]
    print(f"\nmeasured noise floor: {floor} channel step(s) — the largest step among the "
          "differences that are rendering noise")
    print(f"default tolerance: {tolerance} (headroom {tolerance - floor} step(s))")
    if report["content_changes"]:
        print("\npages that are not reproducible because their *content* changes between captures:")
        for item in report["content_changes"]:
            print(
                f"  {item['page']} @{item['viewport']}: {item['max_diff_pixels']:,} px differ, "
                f"{item['content_share'] * 100:.0f}% of them changed their foreground/background "
                f"membership, largest step {item['max_channel_delta']}"
            )
        print("  A tolerance must not be raised to cover this: the page renders different content.")
    if report["silent"]:
        print(f"\nPASS: the default tolerance {tolerance} reproduces every page of the set")
    elif report["content_changes"]:
        print(
            f"\nFAIL: the default tolerance {tolerance} reproduces the rendering noise, but "
            f"{len(report['content_changes'])} page(s) render content that changes between "
            "captures — that is a capture-determinism defect, not a tolerance problem"
        )
    else:
        print(
            f"\nFAIL: {report['diff_pixels']:,} px still differ at tolerance {tolerance} and the "
            f"difference is rendering noise — the default has to rise to at least {floor}"
        )


def build_parser() -> argparse.ArgumentParser:
    """The command line, built separately from `main` so the defaults can be pinned by a test."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    cap = sub.add_parser("capture", help="screenshot every page at every viewport")
    cap.add_argument("--out", type=Path, required=True, help="directory to write the PNGs into")
    cap.add_argument(
        "--docs-root",
        type=Path,
        default=REPO / "docs",
        help="the site root to serve (default: the repo's docs/)",
    )
    cap.add_argument("--settle-ms", type=int, default=SETTLE_MS, help=argparse.SUPPRESS)
    cap.add_argument(
        "--stability-attempts",
        type=int,
        default=STABILITY_ATTEMPTS,
        help=argparse.SUPPRESS,
    )
    cap.add_argument(
        "--stability-wait-ms",
        type=int,
        default=STABILITY_WAIT_MS,
        help=argparse.SUPPRESS,
    )
    cap.add_argument(
        "--proxy",
        choices=("env", "direct"),
        default="env",
        help="use the environment's upstream proxy for external assets (default) or not",
    )
    cap.add_argument("--pages", nargs="*", default=None, help=argparse.SUPPRESS)
    cap.add_argument("--json", type=Path, default=None, help="write the capture manifest here")

    cmp_ = sub.add_parser("compare", help="diff two capture directories")
    cmp_.add_argument("--before", type=Path, required=True)
    cmp_.add_argument("--after", type=Path, required=True)
    cmp_.add_argument("--json", type=Path, default=None, help="write the full report here")
    cmp_.add_argument(
        "--threshold",
        type=float,
        default=0.0,
        help="maximum differing-pixel ratio a page may have (default 0, so any difference fails)",
    )
    cmp_.add_argument("--block", type=int, default=8, help=argparse.SUPPRESS)
    cmp_.add_argument(
        "--tolerance",
        type=int,
        default=DEFAULT_TOLERANCE,
        help=(
            "ignore channel differences of this many steps or fewer "
            f"(default {DEFAULT_TOLERANCE}). "
            "Chromium's text antialiasing is not bit-identical between runs: four captures of "
            "the same page differ by ~20 pixels of one channel step. The default leaves that "
            "noise out of the verdict; `noise-floor` re-measures it"
        ),
    )
    cmp_.add_argument("--max-regions", type=int, default=12, help=argparse.SUPPRESS)
    cmp_.add_argument("--pages", nargs="*", default=None, help=argparse.SUPPRESS)
    cmp_.add_argument(
        "--ignore-layout-shift",
        action="store_true",
        help="do not fail the gate on a layout shift, only on the ratio",
    )
    cmp_.add_argument("--verbose", "-v", action="store_true", help="print every region")

    floor = sub.add_parser(
        "noise-floor",
        help="capture the page set N times and measure the capture-to-capture noise floor",
    )
    floor.add_argument(
        "--docs-root",
        type=Path,
        default=REPO / "docs",
        help="the site root to serve (default: the repo's docs/)",
    )
    floor.add_argument(
        "--runs",
        type=int,
        default=4,
        help="how many times to capture the page set (default 4, so every pair is compared)",
    )
    floor.add_argument(
        "--out",
        type=Path,
        default=None,
        help="keep the captures in this directory (default: a temporary directory that is removed)",
    )
    floor.add_argument(
        "--proxy",
        choices=("env", "direct"),
        default="env",
        help="use the environment's upstream proxy for external assets (default) or not",
    )
    floor.add_argument("--pages", nargs="*", default=None, help=argparse.SUPPRESS)
    floor.add_argument("--json", type=Path, default=None, help="write the measurement here")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "capture":
        records, warnings = capture(
            args.docs_root,
            args.out,
            settle_ms=args.settle_ms,
            proxy=args.proxy,
            only=args.pages,
            stability_attempts=args.stability_attempts,
            stability_wait_ms=args.stability_wait_ms,
        )
        failures = [r for r in records if r.error]
        manifest = {
            "docs_root": str(args.docs_root.resolve()),
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "viewports": [{"name": n, "width": w, "height": h} for n, w, h in VIEWPORTS],
            "captures": [
                {
                    "page": r.page,
                    "viewport": r.viewport,
                    "image": r.image,
                    "viewport_width": r.width,
                    "viewport_height": r.height,
                    "scroll_width": r.scroll_width,
                    "scroll_height": r.scroll_height,
                    "fonts_loaded": r.fonts_loaded,
                    "stable": r.stable,
                    "error": r.error,
                }
                for r in records
            ],
        }
        manifest_path = args.json or (args.out / "manifest.json")
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"captured {len(records) - len(failures)}/{len(records)} into {args.out}")
        print(f"manifest: {manifest_path}")
        for record in records:
            status = "FAIL" if record.error else "ok"
            extra = record.error or (
                f"{record.scroll_width}×{record.scroll_height} scroll"
                + ("" if record.fonts_loaded else "  (fonts not 'loaded')")
            )
            print(f"  {status:>4}  {record.page} @ {record.viewport}: {extra}")
        for warning in warnings:
            print(f"  warn  {warning}")
        return 1 if failures else 0

    if args.command == "noise-floor":
        measurement = measure_noise_floor(
            args.docs_root,
            runs=args.runs,
            only=args.pages,
            proxy=args.proxy,
            out_dir=args.out,
        )
        print_noise_floor(measurement)
        if args.json:
            args.json.write_text(
                json.dumps(measurement, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            print(f"\njson: {args.json}")
        return 0 if measurement["silent"] else 1

    report = compare(
        args.before,
        args.after,
        block=args.block,
        tolerance=args.tolerance,
        max_regions=args.max_regions,
        only=args.pages,
    )
    print_report(report, verbose=args.verbose)

    if args.json:
        args.json.write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"\njson: {args.json}")

    failed = failed_pages(report, args.threshold, args.ignore_layout_shift)
    if failed:
        print(
            f"\nFAIL: {len(failed)} page(s) over threshold {args.threshold}: "
            f"{', '.join(failed)}"
        )
        return 1
    print(f"\nPASS: every page is within threshold {args.threshold}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
