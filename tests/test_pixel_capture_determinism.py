#!/usr/bin/env python3
"""两棵**不同的树**必须渲染成一样的——这是像素门禁能不能用的前提。

`noise-floor` 量的是**同一棵树**重复采集的噪声。它的结论对门禁有用，但只覆盖了一半：
门禁真正比的是**基线树**和**分支树**，两棵树的内容不同，而这一点在"同一棵树"的测量里
**完全看不见**。

症状（首页，390×844 视口，实测）：

| 比较 | 有差像素 | 超过容差 3 的 | 最大通道差 |
|---|---|---|---|
| 同一棵树，两次采集 | 0 | 0 | 0 |
| 两棵内容相同的树 | 0 | 0 | 0 |
| 两棵差**一个字符**的树 | **36** | **4** | **5** |

改的是 HTML 注释还是可见文本都一样，所以那 36 个像素与改动内容无关。
它们落在搜索输入框的四个圆角上——页面在 `settle` 结束时还停在**中间态**：
两次连续截图逐字节相同（稳定性检查因此说 `stable=True`），但那个中间态不是终态，
而它有多长取决于这一棵树的内容。

**页面到达终态需要 2000 ms**（实测：settle 600 ms → 36 像素差；settle 2000 ms → 0）。
这条测试把这件事钉住：settle 退回去，它就会红。

**需要浏览器。** 没有 Playwright 或没有 Chromium 时大声跳过——这个仓库对可选依赖的
规矩是"缺失时大声跳过，不要静默通过"（`tests/test_pixel_noise_floor.py` 同一套）。
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import compare_site_pixels as cpx  # noqa: E402

DOCS = REPO / "docs"


def _copy_docs(destination: Path) -> Path:
    """把站点树复制一份。复制本身不改内容——两棵内容相同的树必须渲染一致。"""
    shutil.copytree(DOCS, destination)
    return destination


def _edit_one_byte(index_html: Path) -> None:
    """在 HTML 注释里加一个空格：内容变了，可见内容没变。"""
    text = index_html.read_text(encoding="utf-8")
    start = text.index("<!--")
    end = text.index("-->", start)
    index_html.write_text(text[:end] + " " + text[end:], encoding="utf-8")


def _capture_homepage(docs_root: Path, out_dir: Path):
    """采首页的三个视口，返回 {viewport: 截图路径}。"""
    records, _warnings = cpx.capture(docs_root, out_dir, only=["index"])
    return {r.viewport: out_dir / r.image for r in records}


def test_two_trees_one_byte_apart_render_identically(tmp_path):
    """差一个字符的两棵树，必须渲染成一样的——否则门禁会报一个没人改过的改动。"""
    pytest.importorskip("playwright.sync_api", reason="the capture needs a browser")

    tree_a = _copy_docs(tmp_path / "tree-a")
    tree_b = _copy_docs(tmp_path / "tree-b")
    _edit_one_byte(tree_b / "index.html")

    try:
        shots_a = _capture_homepage(tree_a, tmp_path / "shots-a")
        shots_b = _capture_homepage(tree_b, tmp_path / "shots-b")
    except Exception as exc:  # pragma: no cover — depends on the machine's browser
        pytest.skip(f"the browser is not usable here: {exc}")

    np = pytest.importorskip("numpy", reason="comparing two images is array arithmetic")
    compared = 0
    for viewport, path_a in shots_a.items():
        path_b = shots_b.get(viewport)
        assert path_b is not None, f"the second tree produced no {viewport} capture"
        before = cpx._load_rgb(path_a).astype(int)
        after = cpx._load_rgb(path_b).astype(int)
        if before.shape != after.shape:
            pytest.fail(f"the two trees rendered at different sizes on {viewport}")
        difference = np.abs(before - after).max(axis=2)
        over = int((difference > cpx.DEFAULT_TOLERANCE).sum())
        assert over == 0, (
            f"{viewport}: {over} pixel(s) differ by more than the tolerance "
            f"{cpx.DEFAULT_TOLERANCE} between two trees that differ by one character "
            f"(max step {int(difference.max())})"
        )
        compared += 1
    assert compared == len(cpx.VIEWPORTS), "not every viewport was compared"


def test_the_stability_rule_needs_three_identical_shots():
    """两张相同**不够**——页面可能还在路上，而采集已经收工了。

    这条规则是纯逻辑，所以这里不需要浏览器：喂进假的截图字节就行。
    """
    run = cpx._IdenticalRun()

    assert run.feed(b"A") is False, "one shot cannot be a run"
    assert run.feed(b"A") is False, "two identical shots were accepted as stable"
    assert run.feed(b"A") is True, "three identical shots were not accepted as stable"


def test_a_single_different_shot_restarts_the_run():
    """中间出现一张不一样的，计数要重来——它是"还在动"的证据。"""
    run = cpx._IdenticalRun()

    run.feed(b"A")
    run.feed(b"A")
    assert run.feed(b"B") is False, "a different shot was not noticed"
    assert run.feed(b"B") is False, "the run did not restart"
    assert run.feed(b"B") is True, "three identical shots after the change were not accepted"


def test_the_required_run_is_three():
    """数字只有一处。改它之前要重新量——见 `STABILITY_IDENTICAL_SHOTS` 的注释。"""
    assert cpx.STABILITY_IDENTICAL_SHOTS == 3
