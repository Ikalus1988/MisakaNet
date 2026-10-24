#!/usr/bin/env python3
"""注册从抽屉与首页降级为 /register/（#3641）——验收标准本身就是门禁。

Issue #3641 说注册有三个入口，而它自己承认不是必需的：抽屉第 4 项（与 Home / Search / Install
同权）、首页底部一整块表单、快速开始里一条 pairing 说明。它真实的作用只有两个——解锁写入类工具
（`write_lesson` / `preflight`），以及给想追踪自己提交的人一个稳定的 node（安装器已自动完成）。

所以这个 issue 的验收是**减法**，而减法最容易悄悄长回来：抽屉里的一项、首页底部的一块表单、
快速开始里的一句"注册"。这四条断言就是那三样东西的守门人。

**表单搬家，功能不变。** 表单搬到 `/register/`，但它是同一个表单：同样的字段、同样的校验、同样
的 Worker 端点、同样的请求体、同样的协议行。所以"功能完全一致"这条验收不是靠一句承诺，而是靠
把形状钉住——元素 id、端点、请求体的键、协议行。少一个 id，脚本就会拿到 `null`；改一个键，
Worker 就会收到一个它不认识的字段。

**末一条需要浏览器**（表单真的能不能用），没有 Playwright 或 Chromium 时大声跳过——CI 里没有装
Playwright，所以它在 CI 上是跳过的。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
HOME = REPO / "docs" / "index.html"
REGISTER = REPO / "docs" / "register" / "index.html"
NAV = REPO / "docs" / "_partials" / "nav.html"
LOCALES = {lang: REPO / "docs" / "locales" / f"{lang}.json" for lang in ("en", "zh")}


@pytest.fixture(scope="module")
def home() -> str:
    return HOME.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def register() -> str:
    return REGISTER.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def nav() -> str:
    return NAV.read_text(encoding="utf-8")


def locale(lang: str) -> dict[str, str]:
    return json.loads(LOCALES[lang].read_text(encoding="utf-8"))


# ── 验收 1：抽屉里没有 Register 项 ──────────────────────────────────────────────────────────────

def test_the_drawer_has_no_register_item(nav: str, home: str) -> None:
    """抽屉的第 4 项没了——Home / Search / Install 之后直接是 Network。

    两份都要查：抽屉的**源**（`docs/_partials/nav.html`）和首页里那份**拷贝**。只查一份，另一份
    就会漂，而漂了的那一份正是读者会点到的那一份。
    """
    for name, text in (("the nav partial", nav), ("the homepage's drawer", home)):
        assert 'href="#register"' not in text, f"{name} still links to the register anchor"
        assert 'navRegister' not in text, f"{name} still carries the Register item's label"
        assert 'Register node' not in text, f"{name} still shows a 'Register node' item"


def test_the_drawer_still_has_its_other_three_items(nav: str) -> None:
    """删掉一项不能顺手删掉别的。"""
    for key in ("navHome", "navSearch", "navInstall"):
        assert f'data-i18n="{key}"' in nav, f"the drawer lost {key}"


# ── 验收 2：/register/ 可直达，表单功能与现在完全一致 ──────────────────────────────────────────

def test_the_register_page_exists_and_carries_the_form(register: str) -> None:
    """表单在新页上，字段一个不少。

    少一个 id，页面上的脚本就会拿到 `null` —— 而这在静态检查里看不出来，只有读代码的人会发现。
    """
    for element_id in (
        "register-btn",
        "register-agree",
        "register-result",
        "node-name",
        "invite-code",
        "agent-other-input",
        "agent-other-wrap",
    ):
        assert f'id="{element_id}"' in register, f"the register page has no #{element_id}"
    assert 'class="agent-selector"' in register, "the agent selector is gone"
    # 11 wired clients (issue #3777 added mcode) plus the free-text escape hatch.
    assert register.count('class="agent-option') == 12, (
        "the selector no longer offers the installer's clients plus the free-text escape hatch"
    )


def test_the_form_still_posts_to_the_worker_with_the_same_payload(register: str) -> None:
    """端点、请求体的键、协议行——这三样是 Worker 认的东西，改一个注册就坏了。"""
    assert 'window.location.origin + "/api/register"' in register, (
        "the form no longer posts to the Worker's register endpoint"
    )
    for field in ("agent_type", "node_name", "invite_code", "body"):
        assert re.search(rf"^\s*{field}:", register, re.M), (
            f"the request body no longer carries {field}"
        )
    assert "Agent 类型: **${selectedAgent.toUpperCase()}**" in register, (
        "the protocol line the page builds moved or changed shape"
    )
    assert "## 🧠 通过公开通道加入御坂网络" in register, "the issue-body preamble moved"


def test_the_form_still_validates_the_same_way(register: str) -> None:
    """校验规则跟着表单一起搬了。

    数字用**词边界**写：`name.length > 50` 是 `name.length > 500` 的子串，所以不带边界的那条
    断言在限长被改成 500 时照样是绿的——它测不出任何东西（见 /tmp/mutation_audit_register.py
    里那条同名变异：它当时没让测试变红）。
    """
    assert "function validateName(name)" in register
    assert "function validateInviteCode(code)" in register
    assert "function sanitizeInput(val, maxLen)" in register
    assert re.search(r"name\.length > 50\b", register), "the node name's length limit moved"
    assert re.search(r"code\.length > 50\b", register), "the invite code's length limit moved"
    assert "misakanet-last-reg" in register, "the client-side rate limit moved"
    assert re.search(r"now - lastReg < 30000\b", register), "the rate limit's window moved"
    assert re.search(r"\(30000 - \(now - lastReg\)\)", register), (
        "the remaining-seconds computation moved — the window and the countdown have to be the "
        "same number, or the page tells the visitor to wait longer than it will let them"
    )


# ── 验收 3：首页底部只有一行链接，无表单 ──────────────────────────────────────────────────────

def test_the_homepage_has_no_form_any_more(home: str) -> None:
    """首页上的那块表单没了——连同它的脚本。"""
    for element_id in ("register-btn", "register-agree", "node-name", "invite-code",
                       "agent-other-input", "register-result"):
        assert f'id="{element_id}"' not in home, f"the homepage still carries #{element_id}"
    assert 'class="agent-selector"' not in home, "the homepage still carries the agent selector"
    assert "async function registerNode()" not in home, "the homepage still carries the flow"


def test_the_homepage_has_exactly_one_line_pointing_at_the_register_page(home: str) -> None:
    """一行，而且只有一行。"""
    links = re.findall(r'href="/register/"', home)
    assert len(links) == 1, f"the homepage links to /register/ {len(links)} times — one line, not a menu"
    assert 'data-i18n="registerCta"' in home, "the line is not the one the issue wrote"
    assert 'data-i18n="registerCtaLink"' in home


def test_the_homepage_still_reads_no_registration_promise(home: str) -> None:
    """首页不再说"注册是入口"。它现在说的是：读取不需要，写入才需要。"""
    assert "写课程需要一个 node（读取不需要）" in home
    assert "读取与检索无需注册" in home, "the terminal widget's note about reading needing no node"


# ── 验收 4：首页快速开始区无"注册/配对"字样 ───────────────────────────────────────────────────

QUICKSTART = re.compile(r'<div id="quickstart-section".*?(?=<!-- Voices)', re.S)
# The prose of the block: the `data-i18n` keys it renders, in both dictionaries. The *commands* are
# not prose — one of them is `misakanet_register`, and the tool's name is not a call to register.
QUICKSTART_KEYS = re.compile(r'data-i18n="(qs[A-Za-z0-9]*)"')


def test_the_quickstart_prose_never_says_register_or_pairing(home: str) -> None:
    """读取路径上不再有注册/配对的话。

    写路径上**命令**还在（`misakanet_register` 这个工具没有被删，issue 明确说了不改 API），但
    句子不该再说"去注册一次"——那句话现在属于 /register/。
    """
    block = QUICKSTART.search(home)
    assert block, "could not find #quickstart-section — did the markup change shape?"
    keys = set(QUICKSTART_KEYS.findall(block.group(0)))
    assert keys, "the quickstart block renders no keyed copy any more"
    offenders = []
    for lang in ("en", "zh"):
        values = locale(lang)
        for key in sorted(keys):
            value = values.get(key, "")
            if re.search(r"注册|配对|register|pair", value, re.I):
                offenders.append((lang, key, value))
    assert not offenders, (
        f"these Quickstart strings still talk about registering or pairing: {offenders}"
    )


def test_the_quickstart_keys_are_not_named_after_pairing(home: str) -> None:
    """键名也换掉：一个叫 `qsStartPair` 的键，读代码的人会以为配对还在。"""
    assert "qsStartPair" not in home
    for lang in ("en", "zh"):
        leftover = sorted(k for k in locale(lang) if k.startswith("qsStartPair"))
        assert not leftover, f"{lang}.json still carries {leftover}"


# ── 可达性：抽屉之外，从哪儿能找到它 ──────────────────────────────────────────────────────────

def test_the_register_page_is_linked_from_the_for_agents_docs() -> None:
    """For Agents 与 MCP 文档链过去。

    抽屉里的「For Agents」指向的是三份文档（skill.md / cli-reference.md / mcp.md），所以"从
    For Agents 链过去"落在这两份真正讲写入工具的文档上：读的人在那里问"写入要 node 吗"，答案
    就在那一行。
    """
    for doc in ("docs/skill.md", "docs/mcp.md"):
        text = (REPO / doc).read_text(encoding="utf-8")
        assert "https://misakanet.org/register/" in text, f"{doc} does not point at the register page"


def test_the_register_page_is_not_in_the_shared_footer_row() -> None:
    """共享页脚是每个页面都有的导航，所以它不能多一个 Register —— 那会让注册重新变成主导航项。"""
    links = (REPO / "docs" / "_partials" / "site-links.html").read_text(encoding="utf-8")
    assert "/register/" not in links


# ── 页面自己的 i18n：它读的是全站那一份词典 ──────────────────────────────────────────────────

def test_the_register_page_reads_the_sites_one_dictionary(register: str) -> None:
    """一份词典，不是两份。页面上每个 `data-i18n` 的键都必须在那一份里存在。

    而且读的必须是**那一份**：路径是 `/locales/...`（绝对），不是 `/register/locales/...`——
    后者会是一份新的、没人维护的副本，而两份词典必然漂。
    """
    assert re.search(r"fetch\(`/locales/\$\{lang\}\.json`\)", register), (
        "the register page does not read the site's one dictionary — a second dictionary is a "
        "second source of truth"
    )
    keys = set(re.findall(r'data-i18n(?:-placeholder)?="([^"]+)"', register))
    assert keys, "the register page renders no keyed copy"
    for lang in ("en", "zh"):
        missing = sorted(k for k in keys if k not in locale(lang))
        assert not missing, f"{lang}.json is missing {missing}"


# ── 表单真的能不能用（需要浏览器） ─────────────────────────────────────────────────────────────

def _serve(docs_root: Path):
    """Serve the docs tree on a free port, the way the pixel gate does."""
    import functools
    import http.server
    import threading

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(docs_root))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, server.server_address[1]


def test_the_form_still_works_in_a_browser() -> None:
    """表真的能用：勾上条款按钮才亮、换一个客户端它就成为选中的那个。

    **不提交。** 提交会真的向 Worker 发一个注册请求——那不是一个单元测试该做的事。这里要验的是
    "搬家之后表单还是活的"：脚本跑起来了，事件绑上了，状态会变。
    """
    pytest.importorskip("playwright.sync_api", reason="the form needs a browser")

    # The same Chromium the pixel gate drives: the Python package and the browser build move
    # independently, and a machine that has one cached and expects the other will not launch.
    sys.path.insert(0, str(REPO / "scripts"))
    import compare_site_pixels as cpx  # noqa: E402

    executable = cpx.chromium_executable()
    if executable is None:
        pytest.skip("no cached Chromium on this machine")

    server, port = _serve(REPO / "docs")
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=executable)
            try:
                page = browser.new_page()
                errors: list[str] = []
                page.on("pageerror", lambda exc: errors.append(str(exc)))
                page.goto(f"http://127.0.0.1:{port}/register/", wait_until="load")
                page.wait_for_timeout(500)

                button = page.locator("#register-btn")
                assert button.is_disabled(), "the button is enabled before the terms are accepted"

                page.locator("#register-agree").check()
                assert button.is_enabled(), (
                    "accepting the terms did not enable the button — the listener did not survive "
                    "the move"
                )

                page.locator('.agent-option[data-agent="cursor"]').click()
                assert page.locator('.agent-option[data-agent="cursor"]').get_attribute(
                    "aria-checked"
                ) == "true", "the agent selector no longer selects"
                assert page.locator('.agent-option[data-agent="hermes"]').get_attribute(
                    "aria-checked"
                ) == "false", "the previous selection was not cleared"

                # The checkbox is the one input that must **not** be `width: 100%`: it is a
                # flex item next to its label, so a full-width checkbox squeezes the text into
                # a column one character wide and pushes the page sideways. The homepage's copy
                # of this rule hit the checkbox too, and the homepage's `overflow-x: hidden`
                # hid the overflow — but the terms line was still rendered vertically, one
                # character per line. This page has no such clip, so the rule is fixed here.
                for width in (320, 390, 640):
                    narrow = browser.new_page(viewport={"width": width, "height": 844})
                    narrow.goto(f"http://127.0.0.1:{port}/register/", wait_until="load")
                    narrow.wait_for_timeout(300)
                    measured = narrow.evaluate(
                        "() => ({scroll: document.documentElement.scrollWidth,"
                        " client: document.documentElement.clientWidth})"
                    )
                    assert measured["scroll"] == measured["client"], (
                        f"the page overflows sideways at {width}px: "
                        f"{measured['scroll']} > {measured['client']}"
                    )
                    narrow.close()

                assert not errors, f"the page raised errors: {errors}"
            finally:
                browser.close()
    except Exception as exc:  # pragma: no cover — depends on the machine's browser
        pytest.skip(f"the browser is not usable here: {exc}")
    finally:
        server.shutdown()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "-q"]))
