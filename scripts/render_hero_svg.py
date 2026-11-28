#!/usr/bin/env python3
"""Render the README hero as two SVGs from `docs/assets/hero.json` (#5883).

Why SVG from a recording instead of a bitmap
--------------------------------------------
The hero was `promotional/misaka-compare.jpg` — a hand-made bitmap whose alt text said
**"30+ min manual debugging vs 0.02s with MCP"**. Both halves of that are defects:

* **They are different measurements.** 30 minutes was end-to-end debugging; 0.02 s was BM25 alone. A
  reader who works it out is right to stop trusting the rest of the page, and this repository's whole
  claim is that its numbers are checkable.
* **Neither number can be re-derived.** A JPEG cannot be regenerated when the corpus changes, so the
  figure drifts in silence — the exact failure `test_readme_benchmark_is_generated` exists to stop for
  the benchmark table.

So the hero is generated from one recorded search (`scripts/record_hero_snapshot.py`) and a corpus
count, and `tests/test_hero_svg.py` re-runs the renderer and compares bytes. Change a number without
re-rendering and a test fails; re-render and the diff is the change.

Two files, because GitHub cannot recolour an SVG
------------------------------------------------
`<picture>` with `prefers-color-scheme` picks between two complete renders rather than applying a CSS
variable — GitHub sanitises `<style>` out of inline SVG in Markdown. Both files are produced from the
same snapshot by the same function, so they cannot disagree about a number; only the palette differs.

What the picture deliberately does not contain
----------------------------------------------
No "before" column, no token count, no turn count, no seconds-saved. `hero.json` records none of them
— nothing in this repository measures them — so there is nothing to draw. The picture shows the one
thing that was observed: what a failure looks like, what one call returns, and how long that call took.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SNAPSHOT = REPO / "docs" / "assets" / "hero.json"
OUT_DARK = REPO / "docs" / "assets" / "hero-dark.svg"
OUT_LIGHT = REPO / "docs" / "assets" / "hero-light.svg"

PALETTES = {
    "dark": {
        "bg": "#0d1117", "panel": "#161b22", "border": "#30363d",
        "fg": "#e6edf3", "muted": "#8b949e", "dim": "#6e7681",
        "accent": "#58a6ff", "ok": "#3fb950", "warn": "#d29922", "mono_bg": "#010409",
    },
    "light": {
        "bg": "#ffffff", "panel": "#f6f8fa", "border": "#d0d7de",
        "fg": "#1f2328", "muted": "#59636e", "dim": "#818b98",
        "accent": "#0969da", "ok": "#1a7f37", "warn": "#9a6700", "mono_bg": "#f6f8fa",
    },
}

#: Width in user units. GitHub scales the SVG to the container, so this only sets the aspect ratio.
W = 880
PAD = 22

EVIDENCE_NOTE = {
    "E0": "intake only",
    "E1": "reviewed",
    "E2": "reproduced",
    "E3": "CI verified",
    "E4": "observed reuse",
}


def _esc(text: object) -> str:
    return (str(text or "")
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def _truncate(text: object, limit: int) -> str:
    value = " ".join(str(text or "").split())
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "…"


#: How wide one character is, in multiples of the font size, for the two scripts this corpus writes in.
#: Latin in a monospace stack is ~0.60em; a CJK glyph is ~1.00em (full-width by definition). Counting
#: characters instead of ems is what let a Chinese lesson title print 458px wide inside a 352px panel
#: — measured 2026-11-27 on the first hero that used a CJK title, where every earlier title had been
#: Latin and 54 characters happened to fit.
_LATIN_EM = 0.60
_CJK_EM = 1.0


def _ems(text: str) -> float:
    return sum(_CJK_EM if ord(ch) > 0x2E80 else _LATIN_EM for ch in text)


def _fits(text: str, size: float, inner_px: float) -> bool:
    return _ems(text) * size <= inner_px


def _wrap_for_px(text: object, size: float, inner_px: float, max_lines: int) -> list[str]:
    """Break a title into at most `max_lines` lines that each fit `inner_px` at `size` px.

    Breaks Latin on spaces and CJK anywhere (it has no spaces to break on). The last line is
    ellipsised rather than allowed to overflow, because an <svg> has no overflow handling that keeps
    the text readable.
    """
    value = " ".join(str(text or "").split())
    if not value:
        return []

    def pieces(word: str) -> list[str]:
        # Split a Latin word that is itself too wide; keep CJK runs intact as long as they fit.
        out, buffer = [], ""
        for ch in word:
            candidate = buffer + ch
            if _fits(candidate, size, inner_px) or not buffer:
                buffer = candidate
            else:
                out.append(buffer)
                buffer = ch
        if buffer:
            out.append(buffer)
        return out

    tokens: list[str] = []
    for word in value.split(" "):
        if _fits(word, size, inner_px):
            tokens.append(word)
        else:
            tokens.extend(pieces(word))

    lines: list[str] = []
    current = ""
    for token in tokens:
        separator = " " if current and not (ord(current[-1]) > 0x2E80 or ord(token[0]) > 0x2E80) else ""
        candidate = f"{current}{separator}{token}".strip()
        if _fits(candidate, size, inner_px):
            current = candidate
            continue
        if current:
            lines.append(current)
        current = token
        if len(lines) == max_lines:
            break

    if current and len(lines) < max_lines:
        lines.append(current)

    if len(lines) == max_lines:
        consumed = " ".join(lines)
        if len(consumed) < len(value):
            tail = lines[-1]
            while tail and not _fits(tail + "…", size, inner_px):
                tail = tail[:-1]
            lines[-1] = tail.rstrip() + "…"
    return lines


def render(snapshot: dict, theme: str) -> str:
    p = PALETTES[theme]
    query = _esc(snapshot["query"])
    hit = snapshot["top_hit"]
    # The two panel columns must be known before anything is wrapped against their width.
    left_x, right_x, col_w = PAD, 470, 388
    hit_title_lines = _wrap_for_px(hit.get("title"), 12.5, col_w - 36, 2)
    level = str(hit.get("evidence_level") or "?")
    note = EVIDENCE_NOTE.get(level, "")
    p50 = snapshot.get("latency_ms_p50")
    samples = snapshot.get("latency_ms_samples") or []
    spread = f"{min(samples)}–{max(samples)} ms over {len(samples)} calls" if samples else ""
    recorded = str(snapshot.get("recorded_at") or "").replace("T", " ").rstrip("Z") + " UTC"

    # ── vertical rhythm ────────────────────────────────────────────────────────────────────────
    y = PAD

    L: list[str] = []
    add = L.append

    # Left panel: the failure, as it arrives.
    query_lines = _wrap_for_px(snapshot["query"], 13, col_w - 36, 3)
    # `label + code + N lines + footnote` with real padding, not a constant. A flat `96 + 20*N` was
    # 18 px too short for a one-line query: the footnote baseline landed on the last code line.
    lh = 82 + 20 * max(1, len(query_lines)) + 26
    add(f'<rect x="{left_x}" y="{y}" width="{col_w}" height="{lh}" rx="10" '
        f'fill="{p["panel"]}" stroke="{p["border"]}"/>')
    add(f'<text x="{left_x + 18}" y="{y + 28}" font-family="ui-monospace, SFMono-Regular, Menlo, monospace" '
        f'font-size="12" fill="{p["muted"]}">the failure</text>')
    add(f'<text x="{left_x + 18}" y="{y + 56}" font-family="ui-monospace, SFMono-Regular, Menlo, monospace" '
        f'font-size="14" fill="{p["warn"]}">$ error</text>')
    for index, line in enumerate(query_lines):
        add(f'<text x="{left_x + 18}" y="{y + 82 + index * 20}" '
            f'font-family="ui-monospace, SFMono-Regular, Menlo, monospace" font-size="13" '
            f'fill="{p["fg"]}">{_esc(line)}</text>')
    add(f'<text x="{left_x + 18}" y="{y + lh - 16}" font-size="12" fill="{p["dim"]}">'
        f'the agent is about to guess</text>')

    # Arrow between panels.
    arrow_y = y + lh // 2
    add(f'<path d="M{left_x + col_w + 8} {arrow_y} h44" stroke="{p["border"]}" stroke-width="2"/>')
    add(f'<path d="M{left_x + col_w + 46} {arrow_y - 5} l8 5 l-8 5" fill="{p["border"]}"/>')

    # Right panel: the recorded answer.
    rh = 224
    add(f'<rect x="{right_x}" y="{y}" width="{col_w}" height="{rh}" rx="10" '
        f'fill="{p["mono_bg"]}" stroke="{p["accent"]}"/>')
    add(f'<text x="{right_x + 18}" y="{y + 28}" font-family="ui-monospace, SFMono-Regular, Menlo, monospace" '
        f'font-size="12" fill="{p["muted"]}">one call</text>')
    add(f'<text x="{right_x + 18}" y="{y + 54}" font-family="ui-monospace, SFMono-Regular, Menlo, monospace" '
        f'font-size="14" fill="{p["accent"]}">misakanet_search(</text>')
    add(f'<text x="{right_x + 18}" y="{y + 74}" font-family="ui-monospace, SFMono-Regular, Menlo, monospace" '
        f'font-size="13" fill="{p["fg"]}">  "{query}"</text>')
    add(f'<text x="{right_x + 18}" y="{y + 94}" font-family="ui-monospace, SFMono-Regular, Menlo, monospace" '
        f'font-size="14" fill="{p["accent"]}">)</text>')
    # The hit, with its real grade.
    add(f'<text x="{right_x + 18}" y="{y + 124}" font-family="ui-monospace, SFMono-Regular, Menlo, monospace" '
        f'font-size="13" fill="{p["ok"]}">✓ {level} · {_esc(note)}</text>')
    for index, line in enumerate(hit_title_lines):
        add(f'<text x="{right_x + 18}" y="{y + 148 + index * 19}" '
            f'font-family="ui-monospace, SFMono-Regular, Menlo, monospace" font-size="12.5" '
            f'fill="{p["fg"]}">{_esc(line)}</text>')
    # The unit is spelled out because the bare number was read as "the service is slow". It is a
    # round trip from one machine, and the sentence says so rather than leaving the reader to guess.
    add(f'<text x="{right_x + 18}" y="{y + rh - 16}" font-size="12" fill="{p["dim"]}">'
        f'p50 {p50} ms · {_esc(spread)}</text>')
    # `round trip` on its own line: the sentence that stops "2.4 s" from reading as "the service is
    # slow", and it does not fit beside the spread above (measured: 367 px in a 352 px panel).
    add(f'<text x="{right_x + 18}" y="{y + rh - 3}" font-size="11" fill="{p["dim"]}">'
        f'round trip from one machine, network included</text>')

    # `max`, not `lh`: the right panel is taller, and a strip placed after the *shorter* one
    # overlapped it by 34 px — visible at once in the render, invisible in the source.
    y += max(lh, rh) + 26

    # ── the footer strip: what is stable, and when this was measured ───────────────────────────
    #
    # **No corpus counts here.** A first version printed "1,169 lessons · 347 at E0 · …", and that
    # number moves every time the intake batch converts anything — several times a day. A picture
    # that is wrong within hours teaches readers to distrust the picture, and the count already
    # lives in a badge that regenerates itself (`data/badges/lessons.json`, `update-badges.yml`).
    # The rule this strip now follows: print what a recording can still be true about.
    #
    # So: the grade ladder the picture is *about* (a fixed vocabulary, not a count), and the date
    # the latency was measured. The ladder is described, not counted.
    strip_h = 74
    add(f'<rect x="{left_x}" y="{y}" width="{W - 2 * PAD}" height="{strip_h}" rx="10" '
        f'fill="{p["panel"]}" stroke="{p["border"]}"/>')
    add(f'<text x="{left_x + 18}" y="{y + 26}" font-size="12" fill="{p["muted"]}">'
        f'what the grade means</text>')
    ladder = (f'<tspan fill="{p["fg"]}" font-weight="600">{_esc(level)}</tspan>'
              f' = {_esc(note)} · E0 intake → E1 reviewed → E2 reproduced → E3 CI-verified')
    add(f'<text x="{left_x + 18}" y="{y + 52}" font-size="13" fill="{p["muted"]}">{ladder}</text>')
    add(f'<text x="{W - PAD - 18}" y="{y + 26}" font-size="11" fill="{p["dim"]}" text-anchor="end">'
        f'latency measured {_esc(recorded)}</text>')
    add(f'<text x="{W - PAD - 18}" y="{y + 52}" font-size="11" fill="{p["dim"]}" text-anchor="end">'
        f'corpus size: see the Lessons badge</text>')

    y += strip_h + PAD
    height = y

    head = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{height}" '
        f'viewBox="0 0 {W} {height}" role="img" '
        f'aria-label="{_esc(aria_label(snapshot))}">'
    )
    body = (
        f'<rect width="{W}" height="{height}" rx="12" fill="{p["bg"]}"/>'
        + "".join(L)
    )
    return head + body + "</svg>\n"


def aria_label(snapshot: dict) -> str:
    hit = snapshot["top_hit"]
    return (f"One recorded misakanet_search for {snapshot['query']!r} returned an "
            f"{hit.get('evidence_level')} lesson ({hit.get('id')}) in a median of "
            f"{snapshot.get('latency_ms_p50')} ms, measured {snapshot.get('recorded_at')}. "
            f"The corpus size is in the Lessons badge, not here.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--snapshot", type=Path, default=SNAPSHOT)
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args(argv)

    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    out_dir = args.out_dir or args.snapshot.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    for theme, path in (("dark", out_dir / OUT_DARK.name), ("light", out_dir / OUT_LIGHT.name)):
        path.write_text(render(snapshot, theme), encoding="utf-8", newline="\n")
        print(f"wrote {path} ({len(render(snapshot, theme))} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
