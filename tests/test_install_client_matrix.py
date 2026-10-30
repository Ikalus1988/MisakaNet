#!/usr/bin/env python3
"""/install/ 的验收标准（issue #3640）：一条通用命令优先，客户端表由数据生成。

这一页原来把用户当傻子：先让他判断"我属于哪一段"，再照做。判据改成
**默认路径只给一条命令**，客户端差异放进折叠表，而那张表由
`docs/data/clients.json` 生成、`--check` 检测漂移。

这里钉住五件事：

1. 前两步是**同一条通用命令**，与客户端无关；
2. 客户端表由数据生成，页面与数据漂移时 `--check` **退 1**；
3. README 的接入段 **≤ 8 行、不含表格**；
4. 十二个客户端在表里**各占一行**；
5. 表格在 **≤640px** 下不横向溢出（这一条靠 CSS 断言 + 真浏览器实测）。

**不需要浏览器。** 全部用文件与纯函数驱动。
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import generate_clients_table as gct  # noqa: E402

PAGE = REPO / "docs" / "install" / "index.html"
DATA = REPO / "docs" / "data" / "clients.json"
README = REPO / "README.md"
GENERATOR = REPO / "scripts" / "generate_clients_table.py"


def _page_text() -> str:
    return PAGE.read_text(encoding="utf-8")


def _readme_section() -> str:
    """The README's onboarding section: from its heading to the next heading of any level."""
    text = README.read_text(encoding="utf-8")
    start = text.index("## How to use it")
    rest = text[start + 1 :]
    match = re.search(r"^#{2,3} ", rest, flags=re.MULTILINE)
    return rest[: match.start()] if match else rest


# ── 1. 前两步是同一条通用命令 ─────────────────────────────────────────────────────────────────
def test_the_first_two_steps_are_the_same_generic_command():
    """①② 是同一条命令，客户端无关——客户端差异在折叠表里。"""
    text = _page_text()
    commands = re.findall(r'<code id="cmd-(install|verify)">([^<]+)</code>', text)
    assert commands, "the install page has no command blocks"
    steps = dict(commands)
    assert steps["install"] == "npx @misaka-net/misakanet-setup"
    assert steps["verify"] == "npx @misaka-net/misakanet-setup --verify"


def test_the_command_does_not_depend_on_the_client():
    """页面上不能出现"按客户端挑命令"——那正是这个 issue 要去掉的东西。"""
    text = _page_text()
    body = text[text.index("<body>") :]
    # 一个客户端专属的命令只能出现在生成的那张表里（表里没有命令列），所以这里不该有。
    for forbidden in ("claude mcp add", "codex mcp add", "cursor mcp add", "gemini mcp add"):
        assert forbidden not in body.lower(), (
            f"the page still offers a client-specific command: {forbidden}"
        )


def test_the_data_file_holds_one_command_for_everybody():
    """数据源里只有一条安装命令——客户端那一列写的是"它写了哪些文件"。"""
    data = json.loads(DATA.read_text(encoding="utf-8"))
    assert data["install_command"] == "npx @misaka-net/misakanet-setup"
    assert data["verify_command"] == "npx @misaka-net/misakanet-setup --verify"
    for client in data["clients"]:
        assert "command" not in client, (
            f"{client['id']} carries its own command — the point is that nobody has to pick one"
        )


# ── 2. 表由数据生成，漂移要被抓住 ─────────────────────────────────────────────────────────────
def test_the_table_is_in_sync_with_the_data():
    """页面上的表就是数据渲染出来的那张。"""
    assert gct.main(["--check"]) == 0, (
        "the install page's client table has drifted from docs/data/clients.json — "
        "run: python scripts/generate_clients_table.py --write"
    )


def test_a_changed_client_is_caught_by_the_check(tmp_path):
    """数据改了一行而页面没跟上，`--check` 必须退 1——这就是那道门禁。"""
    original = DATA.read_text(encoding="utf-8")
    try:
        data = json.loads(original)
        data["clients"][0]["name"] = "Claude Code (renamed)"
        DATA.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        assert gct.main(["--check"]) == 1, "the drift check did not notice a renamed client"
    finally:
        DATA.write_text(original, encoding="utf-8")
    assert gct.main(["--check"]) == 0, (
        "the drift check did not come back after the file was restored"
    )


def test_the_check_fails_when_the_data_is_broken(tmp_path):
    """数据缺一个字段，生成器要**停下来**，不能渲染一张残缺的表。"""
    original = DATA.read_text(encoding="utf-8")
    try:
        data = json.loads(original)
        del data["clients"][0]["reporting"]
        broken = tmp_path / "clients.json"
        broken.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        with pytest.raises(SystemExit):
            gct.load_clients(broken)
    finally:
        DATA.write_text(original, encoding="utf-8")


def test_the_generator_is_runnable_from_the_command_line():
    """门禁要在 CI 里能直接跑，所以它得是一个能独立运行的脚本。"""
    proc = subprocess.run(
        [sys.executable, str(GENERATOR), "--check"],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


# ── 3. README 的接入段 ───────────────────────────────────────────────────────────────────────
def test_the_readme_onboarding_section_is_short_and_has_no_table():
    """接入段 ≤ 8 行、不含表格——十行表格会漂，而且把 README 撑长。"""
    section = _readme_section()
    lines = [line for line in section.splitlines() if line.strip()]
    assert len(lines) <= 8, f"the onboarding section has {len(lines)} lines:\n{section}"
    assert "|" not in section, "the onboarding section still has a table:\n" + section


def test_the_readme_points_at_the_install_page():
    """1 行 + 链接：客户端矩阵在 /install/，不在 README 里抄一份。"""
    section = _readme_section()
    assert "https://misakanet.org/install/" in section


# ── 4. 十二个客户端各占一行 ─────────────────────────────────────────────────────────────────────
def test_every_supported_client_has_a_row():
    """十二个客户端，十二行。少一行就有一个客户端在页面上没有答案。"""
    data = json.loads(DATA.read_text(encoding="utf-8"))
    assert len(data["clients"]) == 12
    table = gct.render_table(data)
    rows = [line for line in table.splitlines() if "<tr>" in line and "<th>" not in line]
    assert len(rows) == 12, f"the table has {len(rows)} client rows, expected 12"
    for client in data["clients"]:
        assert client["name"] in table, f"{client['name']} is missing from the table"


def test_the_table_answers_install_reporting_and_account():
    """三列：装什么、能不能上报、要不要账号。"""
    data = json.loads(DATA.read_text(encoding="utf-8"))
    table = gct.render_table(data)
    for header in ("Client", "Install", "Reporting", "Account"):
        assert f"<th>{header}</th>" in table


def test_the_count_in_the_disclosure_line_is_generated():
    """`<summary>Show the ten supported clients</summary>` sat over an eleven-row table (2026-10-30).

    A hand-maintained number next to a generated list drifts exactly the way the table itself was
    made impossible to drift — it was already one client behind. So the disclosure line is inside
    the generated block now, and this pins both halves: the page carries the generated count, and
    the hand-written one is gone rather than merely hidden behind it.
    """
    data = json.loads(DATA.read_text(encoding="utf-8"))
    page = _page_text()
    assert gct.render_summary(data).strip() in page, (
        "the page's disclosure line is not the generated one — "
        "run: python scripts/generate_clients_table.py --write"
    )
    assert f"the {len(data['clients'])} supported clients" in page
    assert "the ten supported clients" not in page


def test_the_installers_own_client_list_is_the_one_on_the_page():
    """页面上的客户端必须就是安装器支持的那十二个——两边漂了就是假信息。"""
    installer = REPO / "packages" / "misakanet-setup" / "bin" / "misakanet-setup.mjs"
    text = installer.read_text(encoding="utf-8")
    match = re.search(r"const AGENTS = \[(.*?)\];", text, flags=re.DOTALL)
    assert match, "the installer's client list moved"
    ids = re.findall(r"'([a-z]+)'", match.group(1))
    data = json.loads(DATA.read_text(encoding="utf-8"))
    assert [client["id"] for client in data["clients"]] == ids, (
        "the client table and the installer's own list disagree"
    )


# ── 5. ≤640px 不横向溢出 ─────────────────────────────────────────────────────────────────────
def _narrow_screen_rules() -> str:
    """The body of the `@media (max-width: 640px)` block, braces counted."""
    text = _page_text()
    start = text.index("@media (max-width: 640px)")
    depth = 0
    for index in range(start, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    raise AssertionError("the narrow-screen block is not closed")


def test_the_table_collapses_on_a_narrow_screen():
    """五列表在手机上放不下：≤640px 时每行变成一张卡片，每格自带标签。"""
    text = _page_text()
    assert "@media (max-width: 640px)" in text, "the page has no narrow-screen rule"
    narrow = _narrow_screen_rules()
    assert ".client-table thead { display: none; }" in narrow, (
        "the header row is still shown on a phone — five columns do not fit"
    )
    assert "display: block" in narrow, "the rows do not become cards on a phone"
    assert "attr(data-label)" in narrow, "the cells do not carry their own label on a phone"


def test_every_generated_cell_carries_its_label():
    """窄屏下每格靠 `data-label` 自报家门，所以生成器必须写它。"""
    data = json.loads(DATA.read_text(encoding="utf-8"))
    table = gct.render_table(data)
    for label in ("Client", "Install", "Reporting", "Account", "Docs"):
        assert f'data-label="{label}"' in table
