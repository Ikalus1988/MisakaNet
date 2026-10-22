#!/usr/bin/env python3
"""布局改动也要有门禁：只改了要改的（issue #3639 / #3640 / #3641 的前置）。

`scripts/compare_site_pixels.py compare` 问的是**改了多少**。这个问题对"本来就不该动布局"的
改动是对的，对**故意**重排的改动是错的：把一整页挪个位置，差多少都不是重点，重点是**挪了哪里**。

所以有了 `scoped` 口径：作者声明"允许变的区块"，门禁断言**框外一个像素都没变**。
- 声明的区块里改多少都行——单位是区块，不是像素；
- 声明之外改一个像素就红——那多半是没人想动的顺手改。

**这些测试是这个口径的全部理由。** 一个只会绿的判据等于没有判据，所以这里既有
"该绿的时候绿"，也有"该红的时候红"，还有"红色的地方说得清是哪儿"。

**不需要浏览器。** 判定函数是纯函数（图像数组进，结果出），所以每一条断言都由造出来的像素驱动；
`main()` 那一条用真的 PNG 文件走一遍进程。numpy / PIL 缺失时，数组级的断言大声跳过，
纯解析的断言照跑。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import compare_site_pixels as cpx  # noqa: E402

np = pytest.importorskip("numpy", reason="the scoped criterion is array arithmetic")


def _canvas(height: int = 100, width: int = 100, colour: int = 255):
    """一张纯色画布。"""
    return np.full((height, width, 3), colour, dtype=np.uint8)


def _with_block(image, x0: int, y0: int, x1: int, y1: int, colour: int = 0):
    """在图上涂一块颜色不同的方块，返回新图（不改原图）。"""
    out = image.copy()
    out[y0:y1, x0:x1] = colour
    return out


# ── 判据本身 ──────────────────────────────────────────────────────────

def test_a_change_inside_a_declared_region_is_allowed():
    """声明了的那块随便改——单位是区块。"""
    before = _canvas()
    after = _with_block(before, 50, 50, 70, 70)

    result = cpx.scoped_check(before, after, [(40, 40, 80, 80)])

    assert result["ok"] is True, "a change inside the declared region was refused"
    assert result["changed_pixels"] == 400
    assert result["outside_pixels"] == 0


def test_a_change_outside_the_declared_region_fails():
    """声明之外改一个像素也不行。"""
    before = _canvas()
    after = _with_block(before, 50, 50, 70, 70)

    result = cpx.scoped_check(before, after, [(0, 0, 10, 10)])

    assert result["ok"] is False, "a change outside the declared region was allowed"
    assert result["outside_pixels"] == 400


def test_a_page_with_no_declared_region_may_not_change_at_all():
    """没人给这一页发许可，那它就不许变。"""
    before = _canvas()
    after = _with_block(before, 10, 10, 20, 20)

    result = cpx.scoped_check(before, after, [])

    assert result["ok"] is False
    assert result["outside_pixels"] == 100


def test_a_page_with_no_change_passes_without_any_permission():
    """没改的页面不需要许可——许可只管"改"。"""
    before = _canvas()

    result = cpx.scoped_check(before, before.copy(), [])

    assert result["ok"] is True
    assert result["changed_pixels"] == 0


def test_the_stray_change_is_reported_with_its_where():
    """红了要说清是哪儿红的：框外区域的位置要报出来。"""
    before = _canvas()
    after = _with_block(before, 50, 50, 70, 70)

    result = cpx.scoped_check(before, after, [(0, 0, 10, 10)])

    assert result["outside_regions"], "the stray change was not located"
    box = result["outside_regions"][0]["bbox"]
    assert box[0] <= 50 and box[1] <= 50, f"the reported region does not cover the change: {box}"
    assert box[2] >= 70 and box[3] >= 70, f"the reported region does not cover the change: {box}"


# ── 页面变高变矮：多出来的那一截也算改动 ──────────────────────────────

def test_a_grown_page_counts_the_new_rows_as_a_change():
    """页面变高了：新多出来的那一截是改动——比像素比不出来，因为另一边压根没有像素。

    整条带子都算，不只是变色的那几行：页面长高了四十行空白，这件事本身就是改动。
    报告把两件事分开记：`recoloured_pixels` 是颜色差，`grown_pixels` 是长出来的那截。
    """
    before = _canvas(100, 100)
    after = np.full((140, 100, 3), 255, dtype=np.uint8)
    after[120:140, :] = 0

    result = cpx.scoped_check(before, after, [(0, 0, 100, 100)])

    assert result["size_changed"] is True
    assert result["ok"] is False, "the rows that only exist after the change were not counted"
    assert result["outside_pixels"] == 4000, "the whole grown band must count, not just the ink"
    # The overlap is untouched, so nothing was *recoloured* — the whole band is new.
    assert result["recoloured_pixels"] == 0
    assert result["grown_pixels"] == 4000


def test_a_grown_page_is_fine_when_the_new_rows_are_declared():
    """那一截被声明了，就该过。"""
    before = _canvas(100, 100)
    after = np.full((140, 100, 3), 255, dtype=np.uint8)
    after[120:140, :] = 0

    result = cpx.scoped_check(before, after, [(0, 0, 100, 140)])

    assert result["ok"] is True


def test_a_shrunk_page_counts_the_lost_rows_as_a_change():
    """页面变矮了：少掉的那一截也是改动。"""
    before = _canvas(140, 100)
    after = _canvas(100, 100)

    result = cpx.scoped_check(before, after, [(0, 0, 100, 100)])

    assert result["ok"] is False, "the rows that disappeared were not counted"


def test_a_wider_page_counts_the_new_columns_as_a_change():
    """页面变宽了：多出来的那一列也是改动。"""
    before = _canvas(100, 100)
    after = np.full((100, 120, 3), 255, dtype=np.uint8)

    result = cpx.scoped_check(before, after, [(0, 0, 100, 100)])

    assert result["ok"] is False, "the columns that only exist after the change were not counted"
    assert result["outside_pixels"] == 2000


# ── 容差：只盖噪声，不盖改动 ──────────────────────────────────────────

def test_the_tolerance_silences_the_noise_but_not_the_change():
    """通道差 1 级是噪声（Chromium 抗锯齿的运行间抖动），差 40 级是改动。

    这里**不给**任何许可：所以判据就是"有没有变"。噪声不算变，改动算。
    """
    before = _canvas()
    noise = before.copy()
    noise[10:20, 10:20] = 254
    change = before.copy()
    change[10:20, 10:20] = 215

    quiet = cpx.scoped_check(before, noise, [])
    loud = cpx.scoped_check(before, change, [])

    assert quiet["ok"] is True, "the noise was counted as a change"
    assert quiet["changed_pixels"] == 0
    assert loud["ok"] is False, "a real change was silenced by the tolerance"
    assert loud["changed_pixels"] == 100


# ── 命令行：区域怎么写 ────────────────────────────────────────────────

def test_the_allowed_region_is_read_from_the_command_line():
    """`index@1280x800:0,1900,1280,2400` —— 页、视口、框。"""
    page, viewport, box = cpx.parse_allow_region("index@1280x800:0,1900,1280,2400")

    assert page == "index"
    assert viewport == "1280x800"
    assert box == (0, 1900, 1280, 2400)


def test_the_viewport_is_optional():
    """不带视口的区域，对该页的每个视口都生效。"""
    page, viewport, box = cpx.parse_allow_region("index:0,0,10,10")

    assert page == "index"
    assert viewport is None
    assert box == (0, 0, 10, 10)


@pytest.mark.parametrize("text", [
    "index",                      # 没有框
    "index:0,0,10",               # 少一个数
    "index:a,b,c,d",              # 不是数
    "index:10,0,10,10",           # 空框
    "index:0,10,10,0",            # 空框
    "index@1280x800:0,0,10,10 extra",  # 多余的东西
])
def test_a_malformed_allowed_region_is_an_error(text):
    """写错的区域要报错，不能默默当成"允许一切"。"""
    with pytest.raises(ValueError):
        cpx.parse_allow_region(text)


# ── 走进程：真的 PNG，真的退出码 ──────────────────────────────────────

def _write_png(path: Path, image) -> None:
    pil = pytest.importorskip("PIL.Image", reason="writing a PNG needs Pillow")
    pil.fromarray(image).save(path)


def test_the_scoped_command_passes_when_every_change_is_declared(tmp_path):
    """整条命令：真的 PNG、真的退出码 0。"""
    before_dir = tmp_path / "before"
    after_dir = tmp_path / "after"
    before_dir.mkdir()
    after_dir.mkdir()
    before = _canvas(100, 100)
    after = _with_block(before, 50, 50, 70, 70)
    _write_png(before_dir / cpx.image_name("index", "1280x800"), before)
    _write_png(after_dir / cpx.image_name("index", "1280x800"), after)

    code = cpx.main([
        "scoped",
        "--before", str(before_dir),
        "--after", str(after_dir),
        "--allow", "index@1280x800:40,40,80,80",
    ])

    assert code == 0, "a change inside the declared region failed the gate"


def test_the_scoped_command_fails_when_a_page_changed_outside(tmp_path):
    """整条命令：改在声明之外 → 退出码 1。**门禁必须能变红**，不然它就不是门禁。"""
    before_dir = tmp_path / "before"
    after_dir = tmp_path / "after"
    before_dir.mkdir()
    after_dir.mkdir()
    before = _canvas(100, 100)
    after = _with_block(before, 50, 50, 70, 70)
    _write_png(before_dir / cpx.image_name("index", "1280x800"), before)
    _write_png(after_dir / cpx.image_name("index", "1280x800"), after)

    code = cpx.main([
        "scoped",
        "--before", str(before_dir),
        "--after", str(after_dir),
        "--allow", "index@1280x800:0,0,10,10",
    ])

    assert code == 1, "a change outside the declared region passed the gate"


def test_the_scoped_command_fails_on_a_malformed_region(tmp_path):
    """写错的区域要退 2，不能退 0——退 0 就是"放行一切"。"""
    code = cpx.main([
        "scoped",
        "--before", str(tmp_path),
        "--after", str(tmp_path),
        "--allow", "index",
    ])

    assert code == 2


# ── 这个口径不能把"什么都没改"也判红 ────────────────────────────────

def test_an_untouched_tree_passes_the_scoped_gate_with_no_permissions(tmp_path):
    """两张一样的图，一个许可都不给，也得过——不然这个口径没法用。"""
    before_dir = tmp_path / "before"
    after_dir = tmp_path / "after"
    before_dir.mkdir()
    after_dir.mkdir()
    same = _canvas(100, 100)
    _write_png(before_dir / cpx.image_name("index", "1280x800"), same)
    _write_png(after_dir / cpx.image_name("index", "1280x800"), same.copy())

    code = cpx.main([
        "scoped",
        "--before", str(before_dir),
        "--after", str(after_dir),
    ])

    assert code == 0


# ── 新增的页：没有"之前"可比，所以只能声明 ────────────────────────────
#
# A change that *adds* a page has no image on the "before" side. The tool used to answer
# "missing in before", which the gate counts as a failure — so the change the author asked for
# reported itself as a regression. The way out is a declaration: the author names the pages that
# are new, and the gate says what it did with them. A declaration that does not hold is an error,
# not a pass: the page existed before (so its change was never compared), or it is not there at all.

def test_a_declared_new_page_is_reported_instead_of_compared(tmp_path):
    """声明为新增的页：进"新增"名单，不进"缺页"名单。"""
    before_dir = tmp_path / "before"
    after_dir = tmp_path / "after"
    before_dir.mkdir()
    after_dir.mkdir()
    _write_png(before_dir / cpx.image_name("index", "1280x800"), _canvas(100, 100))
    _write_png(after_dir / cpx.image_name("index", "1280x800"), _canvas(100, 100))
    _write_png(after_dir / cpx.image_name("register__index", "1280x800"), _canvas(100, 100))

    report = cpx.scoped_compare(
        before_dir,
        after_dir,
        allow=[],
        new_pages=["register__index"],
    )

    assert report["new"] == ["register__index"], "the new page was not reported as new"
    assert report["missing"] == [], "the new page was reported as a missing capture"
    assert report["declaration_errors"] == []
    assert "register__index" not in report["pages"], "a page with nothing to compare was compared"


def test_an_undeclared_new_page_is_still_a_failure(tmp_path):
    """没声明的新页照样红——不然"新增页"就成了绕过门禁的后门。"""
    before_dir = tmp_path / "before"
    after_dir = tmp_path / "after"
    before_dir.mkdir()
    after_dir.mkdir()
    _write_png(before_dir / cpx.image_name("index", "1280x800"), _canvas(100, 100))
    _write_png(after_dir / cpx.image_name("index", "1280x800"), _canvas(100, 100))
    _write_png(after_dir / cpx.image_name("register__index", "1280x800"), _canvas(100, 100))

    code = cpx.main([
        "scoped",
        "--before", str(before_dir),
        "--after", str(after_dir),
    ])

    assert code == 1, "an undeclared new page passed the gate"


def test_a_declared_new_page_lets_the_run_pass(tmp_path):
    """整条命令：声明了就过，并且跑完是 0。"""
    before_dir = tmp_path / "before"
    after_dir = tmp_path / "after"
    before_dir.mkdir()
    after_dir.mkdir()
    _write_png(before_dir / cpx.image_name("index", "1280x800"), _canvas(100, 100))
    _write_png(after_dir / cpx.image_name("index", "1280x800"), _canvas(100, 100))
    _write_png(after_dir / cpx.image_name("register__index", "1280x800"), _canvas(100, 100))

    code = cpx.main([
        "scoped",
        "--before", str(before_dir),
        "--after", str(after_dir),
        "--allow-new", "register__index",
    ])

    assert code == 0, "a declared new page failed the gate"


def test_a_declaration_for_a_page_that_existed_before_is_an_error(tmp_path):
    """声明"新"、其实不新 → 这页的改动压根没被比较 → 门禁不能装作通过。"""
    before_dir = tmp_path / "before"
    after_dir = tmp_path / "after"
    before_dir.mkdir()
    after_dir.mkdir()
    _write_png(before_dir / cpx.image_name("index", "1280x800"), _canvas(100, 100))
    _write_png(after_dir / cpx.image_name("index", "1280x800"), _canvas(100, 100))

    code = cpx.main([
        "scoped",
        "--before", str(before_dir),
        "--after", str(after_dir),
        "--allow-new", "index",
    ])

    assert code == 2, "a declaration that does not hold passed the gate"


def test_a_declaration_for_a_page_that_is_in_neither_capture_is_an_error(tmp_path):
    """声明了一页压根不存在的东西 → 也是声明不成立。"""
    before_dir = tmp_path / "before"
    after_dir = tmp_path / "after"
    before_dir.mkdir()
    after_dir.mkdir()
    _write_png(before_dir / cpx.image_name("index", "1280x800"), _canvas(100, 100))
    _write_png(after_dir / cpx.image_name("index", "1280x800"), _canvas(100, 100))

    code = cpx.main([
        "scoped",
        "--before", str(before_dir),
        "--after", str(after_dir),
        "--allow-new", "nowhere",
    ])

    assert code == 2, "a declaration for a page that does not exist passed the gate"


def test_the_plain_compare_command_knows_about_new_pages_too(tmp_path):
    """两个命令同一套规则：新页在 compare 里也一样声明。"""
    before_dir = tmp_path / "before"
    after_dir = tmp_path / "after"
    before_dir.mkdir()
    after_dir.mkdir()
    _write_png(before_dir / cpx.image_name("index", "1280x800"), _canvas(100, 100))
    _write_png(after_dir / cpx.image_name("index", "1280x800"), _canvas(100, 100))
    _write_png(after_dir / cpx.image_name("register__index", "1280x800"), _canvas(100, 100))

    undeclared = cpx.main([
        "compare",
        "--before", str(before_dir),
        "--after", str(after_dir),
    ])
    declared = cpx.main([
        "compare",
        "--before", str(before_dir),
        "--after", str(after_dir),
        "--allow-new", "register__index",
    ])

    assert undeclared == 1, "an undeclared new page passed the compare gate"
    assert declared == 0, "a declared new page failed the compare gate"


def test_the_plain_compare_command_refuses_a_declaration_that_does_not_hold(tmp_path):
    """compare 命令也得守同一条规矩：声明不成立 → 退 2，不是退 0。"""
    before_dir = tmp_path / "before"
    after_dir = tmp_path / "after"
    before_dir.mkdir()
    after_dir.mkdir()
    _write_png(before_dir / cpx.image_name("index", "1280x800"), _canvas(100, 100))
    _write_png(after_dir / cpx.image_name("index", "1280x800"), _canvas(100, 100))

    code = cpx.main([
        "compare",
        "--before", str(before_dir),
        "--after", str(after_dir),
        "--allow-new", "index",
    ])

    assert code == 2, "a declaration that does not hold passed the compare gate"
