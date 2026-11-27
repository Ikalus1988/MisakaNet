#!/usr/bin/env python3
"""The README hero must be a recording, not a drawing (#5883).

The hero was `promotional/misaka-compare.jpg`, a hand-made bitmap whose alt text read
**"Before: 30+ min manual debugging vs After: 0.02s with MCP"**. Three things were wrong with it and
only the first is about taste:

1. **Two different measurements on one line.** 30 minutes was end-to-end debugging; 0.02 s was BM25
   alone. The repository's entire claim is that its numbers are checkable, so a comparison a reader can
   catch as apples-to-oranges costs more than the picture gains.
2. **A bitmap cannot be regenerated.** When the corpus moves, a JPEG keeps showing the old number and
   nothing notices — the defect `test_readme_benchmark_is_generated` exists to stop for the benchmark
   table, one asset over.
3. **It could not show the mechanism.** "0.02s" does not tell a reader what the agent *called* or what
   came back.

The replacement is two SVGs rendered from `docs/assets/hero.json`, which
`scripts/record_hero_snapshot.py` writes from a real call. These tests pin the properties that make it
different from the JPEG rather than pinning the artwork: the numbers come from the snapshot, the
snapshot is a recording, and the palette pair agrees about everything except colour.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import render_hero_svg as hero  # noqa: E402

ASSETS = REPO / "docs" / "assets"
SNAPSHOT = ASSETS / "hero.json"
README = REPO / "README.md"


def snapshot() -> dict:
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


# ── the recording ─────────────────────────────────────────────────────────────────────────────────
def test_the_snapshot_is_a_recording_and_says_so():
    """A snapshot with no provenance is indistinguishable from a number somebody typed."""
    data = snapshot()
    assert data.get("_comment", "").strip(), "the snapshot must say where it came from"
    assert "record_hero_snapshot.py" in data["_comment"], (
        "the comment must name the script, or the next person cannot re-record it")
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", data.get("recorded_at") or ""), (
        f"recorded_at must be an ISO-8601 UTC stamp, got {data.get('recorded_at')!r} — an undated "
        "recording is a claim about no particular day")
    assert data.get("query"), "the snapshot must carry the query that was actually sent"
    assert data.get("latency_ms_samples"), (
        "keep every sample, not only the median: a median hides whether one call took 40 s")


def test_the_snapshot_records_no_number_the_repository_cannot_measure():
    """No token counts, no turn counts, no "minutes saved" — nothing here measures them.

    `search_signals` carries `latency_ms`, `solved`, `query`, `top_id` and self-declared client fields.
    There is no token or turn telemetry anywhere in the repository, so a hero claiming "~38k tokens →
    ~1.9k" would be invented *and* read as measured. This test exists because that is exactly the shape
    an ad-copy edit takes.
    """
    # Field *names*, not the whole document: `_comment` is prose that explains these are absent, and a
    # scan of every byte would fail on its own documentation — measured, that is exactly what the first
    # version of this test did.
    banned = ("token", "turn", "minutes_saved", "saved_seconds", "cost_usd", "savings")

    def keys(node) -> set[str]:
        if isinstance(node, dict):
            found = {str(key).lower() for key in node if key != "_comment"}
            for value in node.values():
                found |= keys(value)
            return found
        if isinstance(node, list):
            return set().union(*(keys(item) for item in node)) if node else set()
        return set()

    present = keys(snapshot())
    offenders = sorted(name for name in present for bad in banned if bad in name)
    assert not offenders, (
        f"the snapshot has field(s) {offenders} naming something nothing in this repository measures. "
        "If a measurement is added, add its instrument first and cite it here.")


def test_every_latency_sample_is_a_positive_integer():
    data = snapshot()
    samples = data["latency_ms_samples"]
    assert all(isinstance(value, int) and value > 0 for value in samples), samples
    assert data["latency_ms_p50"] in samples or abs(
        data["latency_ms_p50"] - sorted(samples)[len(samples) // 2]) <= 1, (
        "the recorded p50 must be derivable from the recorded samples")


def test_the_top_hit_names_a_level_the_corpus_actually_uses():
    data = snapshot()
    level = data["top_hit"]["evidence_level"]
    assert level in data["corpus"]["evidence"], (
        f"the hero shows {level}, which no lesson in the corpus declares — "
        f"levels present: {sorted(data['corpus']['evidence'])}")


def test_the_snapshot_is_not_gated_on_the_corpus_count():
    """The corpus grows several times a day, so gating on its size is gating on the clock.

    This test replaces one that asserted `snapshot()["corpus"] == recorder.corpus_facts()`. That
    assertion was red within minutes of the PR merging — the intake batch converted a lesson — and it
    would have been red nearly always, for a number the picture had already stopped printing. A gate
    that can only be satisfied for an hour is a gate people learn to re-run until it passes.

    What replaced it: the recording is still dated and still names its instrument (asserted above),
    its grade is still real, and `--check` now compares structure rather than counts.
    """
    sys.path.insert(0, str(REPO / "scripts"))
    import record_hero_snapshot as recorder

    # The snapshot keeps a corpus block for the reader — "how big was it when this was measured".
    assert "corpus" in snapshot(), (
        "the recording should still say how big the corpus was, even though nothing gates on it")
    assert hasattr(recorder, "corpus_facts"), (
        "the recorder still needs to write the corpus block")

    # And the structure check must pass right now, whatever the corpus has grown to.
    assert recorder.check() == 0, (
        "--check must be green on a clean checkout regardless of the lesson count; it compares "
        "structure, not size")


# ── the two renders ───────────────────────────────────────────────────────────────────────────────
def test_both_files_are_exactly_what_the_renderer_produces():
    """Change a number without re-rendering and this fails; re-render and the diff is the change.

    That is the whole difference from the JPEG: the asset cannot drift from its input, because there is
    no step in which a human retypes it.
    """
    data = snapshot()
    for theme, path in (("dark", ASSETS / "hero-dark.svg"), ("light", ASSETS / "hero-light.svg")):
        assert path.exists(), f"{path.name} is missing — run scripts/render_hero_svg.py"
        committed = path.read_text(encoding="utf-8")
        assert committed == hero.render(data, theme), (
            f"{path.name} differs from what scripts/render_hero_svg.py produces now. "
            "Re-run it rather than editing the SVG by hand.")


def test_the_two_palettes_disagree_about_colour_and_nothing_else():
    """`<picture>` picks one file per colour scheme, so a number that differed between them would
    silently show one value in light mode and another in dark mode."""
    dark = snapshot()
    dark_svg = hero.render(dark, "dark")
    light_svg = hero.render(dark, "light")

    def numbers(svg: str) -> list[str]:
        return re.findall(r"(?<![\w-])(\d[\d,]{2,})(?![\w-])", re.sub(r"<[^>]+>", " ", svg))

    assert numbers(dark_svg) == numbers(light_svg), (
        "the two renders state different numbers — `prefers-color-scheme` would decide which a reader "
        "sees")
    assert dark_svg != light_svg, "the two renders are byte-identical, so the palette is not applied"
    assert hero.render(dark, "dark") == dark_svg, "rendering must be deterministic"


def test_the_hero_shows_the_call_the_grade_and_the_measured_latency():
    """What the JPEG could not do: a reader sees the tool, the grade, and the real latency."""
    data = snapshot()
    svg = hero.render(data, "dark")
    for required in (data["query"], data["top_hit"]["evidence_level"],
                     str(data["latency_ms_p50"])):
        assert required in svg, f"the hero does not show {required!r}"
    assert data["recorded_at"][:10] in svg, (
        "the latency is a measurement of one day, so the picture must date it")


def test_the_hero_does_not_print_a_corpus_count():
    """A count in a picture is wrong within hours, so the picture points at the badge instead.

    The corpus grows whenever the intake batch converts anything — several times a day. The first
    version of this hero printed "1,169 lessons · 347 at E0 · …" and was stale before the PR merged.
    The count already has a home that regenerates itself (`data/badges/lessons.json`, refreshed by
    `update-badges.yml`), and an asset nobody re-records must not compete with it.
    """
    data = snapshot()
    for theme in ("dark", "light"):
        svg = hero.render(data, theme)
        for count in (f"{data['corpus']['lessons']:,}", str(data["corpus"]["lessons"])):
            assert count not in svg, (
                f"the {theme} render prints the corpus size ({count}); it belongs in the badge")
        assert "Lessons badge" in svg, (
            "the picture should name where the count lives, not restate it")


def test_no_text_run_is_wide_enough_to_escape_its_panel():
    """Geometry, because a hex colour check cannot see an overlap.

    A first version placed the corpus strip after the *shorter* of the two panels and overlapped the
    taller one by 34 px. That was visible in a render and invisible in the source, which is the argument
    for asserting positions instead of eyeballing a screenshot.
    """
    data = snapshot()
    svg = hero.render(data, "dark")
    panels = [
        (float(m.group(1)), float(m.group(2)), float(m.group(3)), float(m.group(4)))
        for m in re.finditer(
            r'<rect x="([\d.]+)" y="([\d.]+)" width="([\d.]+)" height="([\d.]+)"', svg)
    ]
    assert len(panels) == 3, f"expected three panels (failure, call, corpus strip), got {len(panels)}"

    # No two panels may overlap.
    for index, (x, y, w, h) in enumerate(panels):
        for other_x, other_y, other_w, other_h in panels[index + 1:]:
            overlap = (x < other_x + other_w and other_x < x + w
                       and y < other_y + other_h and other_y < y + h)
            assert not overlap, (
                f"panels overlap: ({x},{y},{w},{h}) and ({other_x},{other_y},{other_w},{other_h})")

    # Every text baseline sits inside a panel, and every run fits the panel's inner width.
    for match in re.finditer(r'<text x="([\d.]+)" y="([\d.]+)"([^>]*)>(.*?)</text>', svg):
        x, y, _attributes, body = float(match.group(1)), float(match.group(2)), match.group(3), match.group(4)
        host = [panel for panel in panels
                if panel[0] <= x <= panel[0] + panel[2] and panel[1] <= y <= panel[1] + panel[3]]
        assert host, f"text at ({x}, {y}) sits outside every panel: {body[:40]!r}"
        plain = re.sub(r"<[^>]+>", "", body)
        size = float(re.search(r'font-size="([\d.]+)"', _attributes).group(1))
        # 0.62 em per character is generous for the monospace stacks GitHub resolves to.
        width = len(plain) * size * 0.62
        assert width <= host[0][2] - 8, (
            f"a {size:g}px run is ~{width:.0f}px wide but the panel is {host[0][2]:g}px: {plain[:50]!r}")


# ── the README points at it ──────────────────────────────────────────────────────────────────────
def test_the_readme_uses_picture_so_the_palette_follows_the_reader():
    text = README.read_text(encoding="utf-8")
    assert "<picture>" in text and "</picture>" in text, (
        "GitHub sanitises <style> out of Markdown SVG, so the theme must be chosen by <picture>")
    assert 'srcset="docs/assets/hero-dark.svg"' in text
    assert 'srcset="docs/assets/hero-light.svg"' in text
    assert "prefers-color-scheme: dark" in text, (
        "without the media query the dark render is the fallback and light mode gets dark text")
    assert "promotional/misaka-compare.jpg" not in text, (
        "the bitmap hero is still referenced — its alt text is the unverifiable 30 min / 0.02s pair")


def test_the_hero_alt_text_states_the_recording_not_a_savings_claim():
    text = README.read_text(encoding="utf-8")
    block = text[text.index("<picture>"):text.index("</picture>")]
    alt = re.search(r'alt="([^"]*)"', block)
    assert alt, "the <picture> has no alt text"
    value = alt.group(1)
    for banned in ("30+ min", "0.02s", "vs"):
        assert banned not in value, (
            f"the alt text still carries {banned!r} — a savings claim nothing here measures: {value}")
    assert value.strip(), "alt text must describe the recording for a screen reader"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
