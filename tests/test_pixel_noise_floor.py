#!/usr/bin/env python3
"""The pixel gate's tolerance must match the renderer's noise floor — and must not hide a change.

`scripts/compare_site_pixels.py` compares two captures of the site. Its `--tolerance` used to
default to `0`, which means "a page fails if a single pixel differs at all" — and Chromium's text
antialiasing is not bit-identical between runs, so the gate could go red on a tree nobody had
touched. The measurement behind the new default is in the script's module docstring; the number
itself is `DEFAULT_TOLERANCE = 3`.

**These tests are the other half of that number.** A measured constant that nobody checks drifts
back to whatever it was, and the failure it is meant to prevent comes back with it. So the tests
here pin three things:

  * the default *is* the measured tolerance, in the constant, in the command line and in the
    comparison helpers;
  * the noise-floor computation reads N captures of the same page and reports the worst pair —
    not the average, because the gate has to survive the worst one;
  * the tolerance silences the noise and *only* the noise: a real visual change still fails the
    gate at the default, because a gate that cannot fail is worse than no gate.

**No browser is needed.** The comparison helpers are pure functions over image arrays, so every
assertion below is driven with fabricated pixel data. `numpy` is needed for the array arithmetic
and is optional in CI — where it is missing, the array-level tests skip loudly and the
default-pinning tests still run.
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import compare_site_pixels as cpx  # noqa: E402

# The measured noise floor: four captures of the same page differ by ~20 pixels of exactly one
# channel step (Chromium's text antialiasing). Two steps of headroom over that floor is the
# default. The full measurement is in the module docstring of `compare_site_pixels.py`.
EXPECTED_TOLERANCE = 3


def _numpy():
    """numpy, or a loud skip: the comparison helpers do their arithmetic on image arrays."""
    return pytest.importorskip("numpy", reason="the comparison helpers compare image arrays")


def _solid(np, height: int, width: int, colour: tuple[int, int, int]):
    """A uniform image — the background of a synthetic page."""
    image = np.zeros((height, width, 3), dtype=np.int16)
    image[:, :] = colour
    return image


# ── the default is the measured number ─────────────────────────────────────────────────────────
def test_the_default_tolerance_is_the_measured_noise_floor():
    """The constant the whole tool reads."""
    assert cpx.DEFAULT_TOLERANCE == EXPECTED_TOLERANCE, (
        f"the default tolerance is {cpx.DEFAULT_TOLERANCE}, not the measured "
        f"{EXPECTED_TOLERANCE} — re-measure it with `compare_site_pixels.py noise-floor`"
    )


def test_the_compare_command_defaults_to_the_measured_tolerance():
    """The command line a reviewer actually types."""
    args = cpx.build_parser().parse_args(["compare", "--before", "a", "--after", "b"])
    assert args.tolerance == EXPECTED_TOLERANCE


def test_the_comparison_helpers_default_to_the_measured_tolerance():
    """A caller that leaves the tolerance out gets the measured one, not 0."""
    for helper in (cpx.compare_pair, cpx.compare, cpx.compare_arrays):
        default = inspect.signature(helper).parameters["tolerance"].default
        assert default == EXPECTED_TOLERANCE, f"{helper.__name__} defaults to {default}"


def test_the_threshold_is_still_zero():
    """The tolerance is not the threshold.

    The tolerance decides *which* pixels count as different; the threshold is the differing-pixel
    *ratio* a page may have, and it stays at 0 — a page with any difference at all fails.
    """
    args = cpx.build_parser().parse_args(["compare", "--before", "a", "--after", "b"])
    assert args.threshold == 0.0


def test_the_gate_still_fails_a_page_over_the_threshold():
    """A difference of any ratio is still a failure — the tolerance did not soften the gate."""
    report = {
        "pages": {
            "insights__pr-genius": {"1280x800": {"diff_ratio": 0.002, "layout_shift": False}}
        },
        "missing": [],
    }
    assert cpx.failed_pages(report, 0.0) == ["insights__pr-genius"]


def test_the_gate_still_fails_a_moved_page_even_with_no_ratio_difference():
    """The layout-shift verdict is a second way to fail, and it is untouched."""
    report = {
        "pages": {"index": {"1280x800": {"diff_ratio": 0.0, "layout_shift": True}}},
        "missing": [],
    }
    assert cpx.failed_pages(report, 0.0) == ["index"]
    assert cpx.failed_pages(report, 0.0, ignore_layout_shift=True) == []


# ── the tolerance silences the noise ──────────────────────────────────────────────────────────
def test_a_one_step_shift_is_inside_the_default_tolerance():
    """The measured noise: a single channel step, on a handful of glyph pixels."""
    np = _numpy()
    before = _solid(np, 60, 60, (30, 35, 43))
    after = before.copy()
    after[10, 10] = (31, 36, 44)

    result = cpx.compare_arrays(before, after)
    assert result["diff_pixels"] == 0, "the one-step noise is not inside the default tolerance"


def test_a_one_step_shift_is_a_difference_at_tolerance_zero():
    """The same shift at tolerance 0 — which is what the gate used to run with."""
    np = _numpy()
    before = _solid(np, 60, 60, (30, 35, 43))
    after = before.copy()
    after[10, 10] = (31, 36, 44)

    result = cpx.compare_arrays(before, after, tolerance=0)
    assert result["diff_pixels"] == 1


def test_a_real_change_still_fails_at_the_default_tolerance():
    """The other side of the noise floor: a real visual change is not swallowed.

    A 20×20 block of a different colour is what the smallest real edit on this site looks like.
    It has to stay a difference at the default tolerance, or the gate cannot fail and is worse
    than no gate at all.
    """
    np = _numpy()
    before = _solid(np, 200, 200, (30, 35, 43))
    after = before.copy()
    after[40:60, 40:60] = (200, 60, 60)

    result = cpx.compare_arrays(before, after)
    assert result["diff_pixels"] == 400
    assert result["diff_ratio"] > 0
    report = {"pages": {"page": {"1280x800": result}}, "missing": []}
    assert cpx.failed_pages(report, 0.0) == ["page"]


def test_a_moved_element_still_fails_at_the_default_tolerance():
    """Not only a colour: a displaced element is a layout shift, and it still fails."""
    np = _numpy()
    before = _solid(np, 200, 200, (30, 35, 43))
    after = before.copy()
    after[40:60, 40:60] = (200, 60, 60)
    after[80:100, 80:100] = (200, 60, 60)  # the same block, somewhere else

    result = cpx.compare_arrays(before, after)
    assert result["diff_pixels"] == 800
    assert result["layout_shift"] is True
    report = {"pages": {"page": {"1280x800": result}}, "missing": []}
    assert cpx.failed_pages(report, 0.0) == ["page"]
    # With the threshold raised above the difference, the layout-shift verdict is what still
    # fails the page — that is the second way the gate catches a moved element, and it is not
    # something the tolerance can take away.
    assert cpx.failed_pages(report, 0.05) == ["page"]


# ── the noise floor itself ───────────────────────────────────────────────────────────────────
def test_identical_captures_have_a_zero_noise_floor():
    """Four captures of a page that did not move: nothing differs, nothing to tolerate."""
    np = _numpy()
    image = _solid(np, 40, 40, (30, 35, 43))
    noise = cpx.pairwise_noise([image, image.copy(), image.copy(), image.copy()])

    assert noise["max_diff_pixels"] == 0
    assert noise["max_channel_delta"] == 0
    assert noise["diff_pixels"] == 0
    assert noise["verdict"] == "stable"


def test_the_noise_floor_reports_the_worst_pair_not_the_average():
    """The gate has to survive the worst pair of captures, so the worst pair is what counts.

    Three captures, three pairs, three different answers: one pair differs by a single pixel,
    one by a 5×5 block, and the third by both. The measurement has to report the largest one —
    a floor computed from the average would let the worst pair through.
    """
    np = _numpy()
    clean = _solid(np, 40, 40, (30, 35, 43))
    slight = clean.copy()
    slight[0, 0] = (31, 36, 44)
    blocky = clean.copy()
    blocky[10:15, 10:15] = (31, 36, 44)

    noise = cpx.pairwise_noise([clean, slight, blocky])
    assert noise["pairs"] == 3
    assert noise["max_diff_pixels"] == 26, "the worst pair was not reported"


def test_the_noise_floor_names_the_smallest_tolerance_that_silences_it():
    """One channel step of noise is silenced by tolerance 1, not by tolerance 0."""
    np = _numpy()
    clean = _solid(np, 40, 40, (30, 35, 43))
    noisy = clean.copy()
    noisy[5, 5] = (31, 36, 44)

    noise = cpx.pairwise_noise([clean, noisy])
    assert noise["max_channel_delta"] == 1
    assert noise["min_tolerance_to_silence"] == 1
    assert noise["diff_pixels"] == 0, "tolerance 3 must silence a one-step difference"


def test_the_noise_floor_tells_rendering_noise_from_a_content_change():
    """The two kinds of difference need different answers.

    A glyph edge that moved by one step is rendering noise: the tolerance is the lever. A glyph
    that was replaced by another one is a content change: no tolerance may hide it, and the
    noise floor must not be derived from it either — otherwise the floor would be dragged up to
    the size of the change and every real change would be silenced with it.
    """
    np = _numpy()
    clean = _solid(np, 40, 40, (30, 35, 43))
    edge = clean.copy()
    edge[5, 5] = (31, 36, 44)
    content = clean.copy()
    content[10:20, 10:20] = (200, 60, 60)

    assert cpx.pairwise_noise([clean, edge])["verdict"] == "stable"
    assert cpx.pairwise_noise([clean, content])["verdict"] == "content change"
    assert cpx.pairwise_noise([clean, content])["content_share"] > 0.5


def test_a_single_capture_has_no_pair_to_compare():
    """One capture is not a measurement — the mode refuses it rather than reporting a zero."""
    np = _numpy()
    noise = cpx.pairwise_noise([_solid(np, 10, 10, (30, 35, 43))])
    assert noise["pairs"] == 0
    assert noise["max_diff_pixels"] == 0
