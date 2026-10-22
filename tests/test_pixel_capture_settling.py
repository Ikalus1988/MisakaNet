#!/usr/bin/env python3
"""采集必须**停稳**才配当证据——这一条是像素门禁的地基。

#3681 把稳定性判据从"两张相同"提到"三张相同"，方向是对的，但**预算没跟着涨**：
判据要三张连续相同，首页实测要第六张才凑得齐，而采集只肯拍四张。
于是采集交不出三张连续的相同图，就**写下了一张还在动的页面**——而门禁根本不看
`stable` 这个标记，直接把它当成基线拿去比。

实测（首页，1280×800 视口，两棵只差一个字符的树）：

| 采集规则 | 两个视口的采集状态 | 跨树差异 |
|---|---|---|
| 两张相同（#3681 之前），4 次尝试 | 三个视口都报 ok | 390×844 差 **4** 像素（超容差） |
| 三张相同（#3681），4 次尝试 | 四次采集里四次"没停稳" | 1280×800 差 **584** 像素 |
| 三张相同，**8 次尝试** | 三个视口都报 ok | **0** 像素 |

584 个像素全是**渲染状态**，没有一个像素是作者改的——把它报成"recolour"，
等于让作者为自己没做过的事背锅。

这里钉住三件事：

1. **预算要盖得住最坏的一次收敛**（首页实测要 6 次尝试）；
2. **没停稳的采集不许当证据**——门禁不比较它，并且说清楚哪些页面它没能判；
3. **噪声底不许在半渲染的图上量**——那会把渲染状态折进底噪，然后建议调高容差。

**不需要浏览器。** 这里全部用造出来的 PNG 和 manifest 驱动判定。
"""
from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import compare_site_pixels as cpx  # noqa: E402


# ── 造出来的素材 ────────────────────────────────────────────────────────────────────────────────
def _write_png(path: Path, colour: tuple[int, int, int] = (10, 20, 30), size=(8, 8)) -> Path:
    """一张纯色的小图。"""
    pytest.importorskip("PIL", reason="writing a PNG needs Pillow")
    from PIL import Image

    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, colour).save(path)
    return path


def _write_manifest(directory: Path, captures: list[dict]) -> Path:
    """一份采集 manifest。`captures` 是每条记录的字典。"""
    directory.mkdir(parents=True, exist_ok=True)
    manifest = directory / "manifest.json"
    manifest.write_text(
        json.dumps({"captures": captures}, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return manifest


def _capture_record(page: str, viewport: str, stable: bool = True, error: str = "") -> dict:
    return {
        "page": page,
        "viewport": viewport,
        "image": f"{page}__{viewport}.png",
        "stable": stable,
        "error": error,
    }


# ── 1. 预算 ────────────────────────────────────────────────────────────────────────────────────
def test_the_budget_covers_the_worst_convergence_measured():
    """首页实测：前四张每张都与上一张不同，第五张起才不动；三张连续相同要第六张。

    这条是纯逻辑——喂进假的截图字节就行，不需要浏览器。
    """
    # 实测的收敛过程：四张互不相同，然后连着三张相同。
    shots = [b"A", b"B", b"C", b"D", b"D", b"D"]
    run = cpx._IdenticalRun()
    attempts_needed = None
    for attempt, shot in enumerate(shots, start=1):
        if run.feed(shot):
            attempts_needed = attempt
            break
    assert attempts_needed == 6, (
        "the measured convergence changed: the homepage now needs "
        f"{attempts_needed} attempts, not 6 — re-measure before trusting the budget"
    )
    assert cpx.STABILITY_ATTEMPTS >= attempts_needed, (
        f"the capture may take {cpx.STABILITY_ATTEMPTS} shots, but the homepage needs "
        f"{attempts_needed} to settle — an unsettled capture is written down and compared "
        "anyway"
    )


def test_the_budget_is_not_smaller_than_six():
    """数字只有一处，改它之前要重新量（见 `STABILITY_ATTEMPTS` 的注释）。"""
    assert cpx.STABILITY_ATTEMPTS >= 6


# ── 1b. 时钟与滚动位置也要钉住 ─────────────────────────────────────────────────────────────────
def test_the_frozen_clock_is_a_fixed_instant_in_the_past():
    """冻结时刻是**固定**的，而且早于站点上任何一条时间戳。

    固定：两个采集必须在同一个世界里比。早：所有相对时间于是都渲染成"刚刚"，
    既确定、又短到不会把版面撑开。
    """
    assert cpx.CLOCK_FROZEN_MS == 1_577_836_800_000  # 2020-01-01T00:00:00Z
    assert cpx.CLOCK_FROZEN_MS < 1_600_000_000_000


def test_the_capture_pins_the_clock_and_the_scroll_position():
    """采集必须把**时钟**和**滚动位置**都钉住——这两条各自值上千个像素。

    - 时钟不钉：首页按墙钟打印 feed 的年龄（"59分钟前" / "60分钟前"），
      两棵树的采集差一分钟就是一次"没人改过的改动"；
    - 滚动位置不钉：Chromium 把层合成到整数位置、内容保留分数偏移，
      同一页在不同滚动位置上栅格化出来差 1017 个像素（整页的亚像素位移）。
    """
    source = inspect.getsource(cpx._capture_one)
    assert "set_fixed_time" in source, "the capture does not pin the clock"
    assert "CLOCK_FROZEN_MS" in source, "the capture does not pin the clock to the fixed instant"
    assert "scrollTo(0, 0)" in source, "the capture does not pin the scroll position"


# ── 2. 没停稳的采集不许当证据 ─────────────────────────────────────────────────────────────────
def test_unsettled_captures_reads_the_manifest(capture_dir):
    """manifest 说没停稳，助手就说没停稳；说停稳了、或者压根没有 manifest，就不乱说。"""
    directory = capture_dir("capture")
    _write_manifest(
        directory,
        [
            _capture_record("index", "390x844", stable=True),
            _capture_record("index", "768x1024", stable=False),
            _capture_record("index", "1280x800", stable=True, error="TimeoutError: page.goto"),
        ],
    )
    unsettled = cpx.unsettled_captures(directory)
    assert set(unsettled) == {("index", "768x1024"), ("index", "1280x800")}
    assert "never stopped changing" in unsettled[("index", "768x1024")]
    assert "the capture failed" in unsettled[("index", "1280x800")]


def test_a_directory_without_a_manifest_carries_no_verdict(capture_dir):
    """没有 manifest 就不知道有没有停稳——这时候门禁照旧比较，不装作知道。"""
    directory = capture_dir("capture")
    _write_png(directory / "index__390x844.png")
    assert cpx.unsettled_captures(directory) == {}


def test_the_capture_directory_carries_its_own_manifest(capture_dir):
    """采集目录里必须有 manifest——门禁就是靠它知道哪张图没停稳。"""
    directory = capture_dir("capture")
    record = cpx.CaptureRecord(page="index", viewport="390x844", image="index__390x844.png")
    record.stable = False
    path = cpx.write_manifest(directory, [record], REPO / "docs")

    assert path == directory / "manifest.json"
    assert path.is_file(), "the capture directory has no manifest of its own"
    assert set(cpx.unsettled_captures(directory)) == {("index", "390x844")}


def test_a_capture_that_never_settled_is_not_compared(capture_dir):
    """没停稳的那一张**不参与比较**——它的差异是渲染状态，不是作者改的。"""
    before = capture_dir("before")
    after = capture_dir("after")
    _write_png(before / "index__390x844.png", (10, 20, 30))
    _write_png(after / "index__390x844.png", (200, 40, 40))
    _write_manifest(before, [_capture_record("index", "390x844", stable=True)])
    _write_manifest(after, [_capture_record("index", "390x844", stable=False)])

    report = cpx.compare(before, after)
    assert "index" not in report["pages"], "an unsettled capture was compared anyway"
    assert [item["page"] for item in report["unsettled"]] == ["index"]
    assert "never stopped changing" in report["unsettled"][0]["problem"]


def test_a_settled_capture_is_still_compared(capture_dir):
    """反面对照：停稳了就是要比——新检查不能把正常路径一起挡掉。"""
    before = capture_dir("before")
    after = capture_dir("after")
    _write_png(before / "index__390x844.png", (10, 20, 30))
    _write_png(after / "index__390x844.png", (200, 40, 40))
    _write_manifest(before, [_capture_record("index", "390x844", stable=True)])
    _write_manifest(after, [_capture_record("index", "390x844", stable=True)])

    report = cpx.compare(before, after)
    assert "index" in report["pages"], "a settled capture was not compared"
    assert report["unsettled"] == []
    assert report["pages"]["index"]["390x844"]["diff_pixels"] > 0, "the difference was lost"


def test_a_directory_without_a_manifest_is_compared_as_before(capture_dir):
    """没有 manifest 的目录照旧比较——这条路径不能被新检查改掉。"""
    before = capture_dir("before")
    after = capture_dir("after")
    _write_png(before / "index__390x844.png", (10, 20, 30))
    _write_png(after / "index__390x844.png", (200, 40, 40))

    report = cpx.compare(before, after)
    assert "index" in report["pages"], "a capture without a manifest was skipped"
    assert report["unsettled"] == []


# ── 3. 门禁要"说不能判" ───────────────────────────────────────────────────────────────────────
def test_compare_exits_2_when_a_capture_never_settled(capture_dir, capsys):
    """退 2，不是退 0：**没判就是没判**，不能装作一切正常。"""
    before = capture_dir("before")
    after = capture_dir("after")
    _write_png(before / "index__390x844.png", (10, 20, 30))
    _write_png(after / "index__390x844.png", (10, 20, 30))
    _write_manifest(before, [_capture_record("index", "390x844", stable=True)])
    _write_manifest(after, [_capture_record("index", "390x844", stable=False)])

    code = cpx.main(["compare", "--before", str(before), "--after", str(after)])
    out = capsys.readouterr().out
    assert code == 2, f"the gate did not refuse to decide (exit {code})"
    assert "CANNOT DECIDE" in out
    assert "never settled" in out
    assert "not compared" in out, "the gate did not say which page it could not decide"
    assert "index @390x844" in out, "the gate did not name the page it could not decide"


def test_scoped_exits_2_when_a_capture_never_settled(capture_dir, capsys):
    """scoped 同样是"没判就是没判"。"""
    before = capture_dir("before")
    after = capture_dir("after")
    _write_png(before / "index__390x844.png", (10, 20, 30))
    _write_png(after / "index__390x844.png", (10, 20, 30))
    _write_manifest(before, [_capture_record("index", "390x844", stable=True)])
    _write_manifest(after, [_capture_record("index", "390x844", stable=False)])

    code = cpx.main(["scoped", "--before", str(before), "--after", str(after)])
    out = capsys.readouterr().out
    assert code == 2, f"the scoped gate did not refuse to decide (exit {code})"
    assert "CANNOT DECIDE" in out
    assert "not compared" in out, "the gate did not say which page it could not decide"


def test_compare_still_exits_1_when_a_page_really_changed(capture_dir, capsys):
    """反面对照：真改动仍然退 1——"不能判"不能把"判红"吃掉。"""
    before = capture_dir("before")
    after = capture_dir("after")
    _write_png(before / "index__390x844.png", (10, 20, 30))
    _write_png(after / "index__390x844.png", (200, 40, 40))
    _write_manifest(before, [_capture_record("index", "390x844", stable=True)])
    _write_manifest(after, [_capture_record("index", "390x844", stable=True)])

    code = cpx.main(["compare", "--before", str(before), "--after", str(after)])
    capsys.readouterr()
    assert code == 1, f"a real change did not fail the gate (exit {code})"


# ── 4. 噪声底不许在半渲染的图上量 ─────────────────────────────────────────────────────────────
def test_the_noise_floor_refuses_to_measure_on_a_page_that_never_settles(monkeypatch):
    """把渲染状态折进底噪，就会建议调高容差——那是这条命令最不该给出的建议。"""
    pytest.importorskip("numpy", reason="the noise floor compares images")

    def fake_capture(docs_root, out_dir, **kwargs):
        record = cpx.CaptureRecord(page="index", viewport="390x844", image="index__390x844.png")
        record.stable = False
        return [record], ["index @390x844: page did not stop changing"]

    monkeypatch.setattr(cpx, "capture", fake_capture)
    with pytest.raises(SystemExit) as raised:
        cpx.measure_noise_floor(REPO / "docs", runs=2)
    assert "never settled" in str(raised.value)


# ── 工具 ──────────────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def capture_dir(tmp_path):
    """造一个空的采集目录。每个名字一个目录。"""

    def _make(name: str) -> Path:
        path = tmp_path / name
        path.mkdir(parents=True, exist_ok=True)
        return path

    return _make
