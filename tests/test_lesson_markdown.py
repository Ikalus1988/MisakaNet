#!/usr/bin/env python3
"""The renderer's contract, one construct at a time.

`scripts/lesson_markdown.py` is standard-library-only on purpose (its docstring says why: six
workflows run the page generator and each installs its own package list). That choice means the
renderer is *this repository's* code, so its behaviour has to be pinned here rather than trusted to a
library's test suite — and the corpus is the fixture: 988 lessons use fenced code (75%), ordered lists
(49%), tables (20%), blockquotes (6%) and nested bullets (5%), which is the whole surface.

Two properties matter more than any single construct:

* **escaping** — a lesson that writes `<user>`, or quotes `<div class="modal">`, must show those
  characters. 81 of 988 lessons contain `<…>` in prose, and a browser would swallow an unknown tag as
  nothing at all, leaving a hole in the sentence;
* **no invented markup** — the renderer emits only tags it wrote itself, so there is no passthrough to
  configure wrongly and no lesson can put a `<script>` on the site.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import lesson_markdown  # noqa: E402


def render(text: str) -> str:
    return lesson_markdown.render(text)


# ── escaping ────────────────────────────────────────────────────────────────────────────────────
def test_a_placeholder_is_shown_rather_than_swallowed():
    """`<user>` in prose is a placeholder, and a browser would render it as nothing."""
    assert render("Owned by <user> and <path>.") == "<p>Owned by &lt;user&gt; and &lt;path&gt;.</p>"


def test_a_quoted_html_tag_is_shown_as_text():
    html = render('The element <div class="modal-overlay"> sits above.')
    assert "&lt;div class=&quot;modal-overlay&quot;&gt;" in html or '&lt;div class="modal-overlay"&gt;' in html
    assert "<div" not in html


def test_a_script_in_prose_never_becomes_a_script():
    html = render("then <script>alert(1)</script> ran")
    assert "<script" not in html
    assert "&lt;script&gt;" in html


def test_html_comments_are_dropped_like_markdown_does():
    assert render("a\n<!-- hidden note -->\nb") == "<p>a</p><p>b</p>"


# ── code ───────────────────────────────────────────────────────────────────────────────────────
def test_a_fenced_block_keeps_its_language_and_its_content_literal():
    html = render("```bash\nrm -rf / # <b>not html</b>\n```\n")
    assert html == (
        '<pre><code class="language-bash">rm -rf / # &lt;b&gt;not html&lt;/b&gt;</code></pre>'
    )


def test_an_unclosed_fence_runs_to_the_end_rather_than_swallowing_the_page():
    html = render("```\nno closing fence\n")
    assert html.startswith("<pre><code>") and "no closing fence" in html


def test_a_fence_without_a_language_gets_no_empty_class():
    assert render("```\nx\n```") == "<pre><code>x</code></pre>"


def test_an_inline_code_span_is_not_reformatted():
    assert render("run `a ** b` now") == "<p>run <code>a ** b</code> now</p>"


def test_an_indented_block_is_code_not_prose():
    html = render("para\n\n    <div class=\"x\">\n    </div>\n\nend\n")
    assert "<pre><code>" in html and "&lt;div" in html


# ── structure ──────────────────────────────────────────────────────────────────────────────────
def test_a_level_one_heading_is_demoted_so_the_page_has_one_h1():
    assert render("# Title\n") == "<h2>Title</h2>"


def test_headings_below_the_demotion_keep_their_level():
    assert render("## Two\n### Three\n#### Four\n") == "<h2>Two</h2><h3>Three</h3><h4>Four</h4>"


def test_a_bullet_list_keeps_items_apart():
    assert render("- one\n- two\n") == "<ul><li>one</li><li>two</li></ul>"


def test_an_ordered_list_is_ordered():
    assert render("1. one\n2. two\n") == "<ol><li>one</li><li>two</li></ol>"


def test_a_wrapped_bullet_is_one_item_not_two_paragraphs():
    """The first version of this rendered an indented wrap as its own <p> inside the <li>."""
    html = render("- a long item that wraps\n  onto a second line\n- next\n")
    assert html == "<ul><li>a long item that wraps onto a second line</li><li>next</li></ul>"


def test_a_nested_bullet_nests():
    html = render("- top\n  - child\n- second\n")
    assert html == "<ul><li>top<ul><li>child</li></ul></li><li>second</li></ul>"


def test_a_pipe_table_becomes_a_table():
    html = render("| a | b |\n|---|---|\n| 1 | 2 |\n")
    assert html == (
        "<table><thead><tr><th>a</th><th>b</th></tr></thead>"
        "<tbody><tr><td>1</td><td>2</td></tr></tbody></table>"
    )


def test_a_pipe_that_is_not_a_table_stays_a_paragraph():
    assert render("a | b\n") == "<p>a | b</p>"


def test_a_blockquote_is_quoted():
    assert render("> quoted\n") == "<blockquote><p>quoted</p></blockquote>"


def test_a_horizontal_rule_is_a_rule():
    assert render("a\n\n---\n\nb\n") == "<p>a</p><hr><p>b</p>"


# ── inline ────────────────────────────────────────────────────────────────────────────────────
def test_emphasis_and_strong():
    assert render("**bold** and *bare*") == "<p><strong>bold</strong> and <em>bare</em></p>"


def test_underscores_are_left_alone_so_identifiers_survive():
    """The corpus is code-heavy: `some_var_name` must not turn into emphasis."""
    assert render("set some_var_name here") == "<p>set some_var_name here</p>"


def test_a_link_is_a_link():
    assert render("[docs](https://example.com/a)") == (
        '<p><a href="https://example.com/a">docs</a></p>'
    )


def test_a_site_relative_link_is_allowed_and_an_unknown_scheme_is_not():
    assert 'href="/topics/python/"' in render("[t](/topics/python/)")
    assert 'href="javascript:' not in render("[x](javascript:alert(1))")
    assert 'href="data:text/html,x"' not in render("[x](data:text/html,x)")


def test_an_image_becomes_a_link_rather_than_a_remote_request():
    html = render("![badge](https://example.com/b.svg)")
    assert "<img" not in html
    assert '<a href="https://example.com/b.svg">badge</a>' in html


def test_frontmatter_is_not_rendered():
    assert render('---\ntitle: "x"\n---\n\nbody\n') == "<p>body</p>"


# ── the corpus as a fixture ───────────────────────────────────────────────────────────────────
def test_every_lesson_renders_without_raising_and_without_inventing_markup():
    """The whole corpus, not a sample: 988 files is 2 seconds and it is the real surface."""
    offenders = []
    for path in sorted((REPO / "lessons").glob("*/*.md")):
        html = render(path.read_text(encoding="utf-8"))
        lowered = html.lower()
        if "<script" in lowered or "onerror=" in lowered or 'href="javascript:' in lowered:
            offenders.append(path.name)
    assert not offenders, f"these lessons produced markup the renderer never emits: {offenders}"


@pytest.mark.parametrize("filename", ["contrib/symptom.md"])
def test_a_file_that_is_mostly_metadata_still_renders(filename):
    """The thinnest lesson in the corpus used to render 112 bytes; it must still render something."""
    html = render((REPO / "lessons" / filename).read_text(encoding="utf-8"))
    assert html and "<p>" in html
