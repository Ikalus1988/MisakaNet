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


def _wrap(text: object, width: int, max_lines: int) -> list[str]:
    words = " ".join(str(text or "").split()).split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= width:
            current = candidate
            continue
        if current:
            lines.append(current)
        current = word
        if len(lines) == max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    if len(lines) == max_lines and (len(" ".join(lines)) < len(" ".join(words))):
        lines[-1] = _truncate(lines[-1] + " " + " ".join(words[len(" ".join(lines).split()):]), width)
    return lines


def render(snapshot: dict, theme: str) -> str:
    p = PALETTES[theme]
    query = _esc(snapshot["query"])
    hit = snapshot["top_hit"]
    hit_title_lines = _wrap(hit.get("title"), 45, 2)
    level = str(hit.get("evidence_level") or "?")
    note = EVIDENCE_NOTE.get(level, "")
    corpus = snapshot.get("corpus", {})
    lessons = corpus.get("lessons")
    evidence = corpus.get("evidence") or {}
    p50 = snapshot.get("latency_ms_p50")
    samples = snapshot.get("latency_ms_samples") or []
    spread = f"{min(samples)}–{max(samples)} ms over {len(samples)} calls" if samples else ""
    recorded = str(snapshot.get("recorded_at") or "").replace("T", " ").rstrip("Z") + " UTC"

    # ── vertical rhythm ────────────────────────────────────────────────────────────────────────
    y = PAD
    left_x, right_x = PAD, 470
    col_w = 388

    L: list[str] = []
    add = L.append

    # Left panel: the failure, as it arrives.
    lh = 96 + 20 * max(1, len(_wrap(query, 40, 3)))
    add(f'<rect x="{left_x}" y="{y}" width="{col_w}" height="{lh}" rx="10" '
        f'fill="{p["panel"]}" stroke="{p["border"]}"/>')
    add(f'<text x="{left_x + 18}" y="{y + 28}" font-family="ui-monospace, SFMono-Regular, Menlo, monospace" '
        f'font-size="12" fill="{p["muted"]}">the failure</text>')
    add(f'<text x="{left_x + 18}" y="{y + 56}" font-family="ui-monospace, SFMono-Regular, Menlo, monospace" '
        f'font-size="14" fill="{p["warn"]}">$ error</text>')
    for index, line in enumerate(_wrap(query, 40, 3)):
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
    rh = 210
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
    add(f'<text x="{right_x + 18}" y="{y + rh - 16}" font-size="12" fill="{p["dim"]}">'
        f'p50 {p50} ms · {_esc(spread)}</text>')

    # `max`, not `lh`: the right panel is taller, and a strip placed after the *shorter* one
    # overlapped it by 34 px — visible at once in the render, invisible in the source.
    y += max(lh, rh) + 26

    # ── the corpus strip: counts, not adjectives ───────────────────────────────────────────────
    strip_h = 74
    add(f'<rect x="{left_x}" y="{y}" width="{W - 2 * PAD}" height="{strip_h}" rx="10" '
        f'fill="{p["panel"]}" stroke="{p["border"]}"/>')
    add(f'<text x="{left_x + 18}" y="{y + 26}" font-size="12" fill="{p["muted"]}">'
        f'the corpus behind that call</text>')
    bits = [f'<tspan fill="{p["fg"]}" font-weight="600">{lessons:,}</tspan> lessons'] if lessons else []
    for lvl in ("E0", "E1", "E2", "E3"):
        if lvl in evidence:
            bits.append(f'<tspan fill="{p["fg"]}" font-weight="600">{evidence[lvl]:,}</tspan> at {lvl}')
    add(f'<text x="{left_x + 18}" y="{y + 52}" font-size="13" fill="{p["muted"]}">'
        f'{" · ".join(bits)}</text>')
    add(f'<text x="{W - PAD - 18}" y="{y + 26}" font-size="11" fill="{p["dim"]}" text-anchor="end">'
        f'recorded {_esc(recorded)}</text>')

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
            f"{snapshot.get('latency_ms_p50')} ms, from a corpus of "
            f"{(snapshot.get('corpus') or {}).get('lessons')} lessons.")


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
