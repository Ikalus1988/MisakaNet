#!/usr/bin/env python3
"""The `[Lesson]` converter must be mechanical, and its failures must be visible.

Every test here corresponds to something that went wrong in the 2026-10-30 hand-converted batch:

* a Windows path inside a double-quoted YAML scalar made **the whole frontmatter unparseable** (the
  file looked fine, the gate reported every field missing);
* a non-canonical domain (`qt`, `agent-tooling`) would have failed the gate rather than being mapped;
* a title longer than 120 characters silently broke the gate's limit;
* two of every batch are lessons that already merged, and checking only the batch doubles the corpus.

The converter is deliberately allowed to *skip* with a reason and never to invent a field: the section
that is absent in the issue stays absent in the file.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import yaml  # noqa: E402 — the converter writes frontmatter; parsing it back is the assertion

from scripts import intake_lesson_to_file as conv  # noqa: E402

CANONICAL = set(json.loads((REPO / "data" / "domains.json").read_text(encoding="utf-8"))["canonical"])


def issue(number: int, title: str, body: str) -> dict:
    return {"number": number, "title": f"[Lesson] {title}", "body": body}


BODY = """**Kind:** lesson_submission
**Source:** dsh
**Node:** Misaka1
**Domain:** {domain}
**Title:** {title}
## Problem
{problem}
## Root Cause
{cause}
## Fix
{fix}
## Verification
{verify}
**Tags:** npm, registry, tls

<br/>
<hr/>

<details><summary>Opire banner</summary>do not copy me</details>
"""


def sample(**over) -> dict:
    values = {
        "domain": "devops",
        "title": "npm registry unreachable: pin a mirror",
        "problem": "pnpm failed with ERR_PNPM_META_FETCH_FAIL against registry.npmjs.org.",
        "cause": "The default registry is unreachable with valid certificates from this network.",
        "fix": "Set registry=https://registry.npmmirror.com in the profile .npmrc.",
        "verify": "Metadata fetch returns HTTP 200 and the install completes.",
    }
    values.update(over)
    return issue(101, values["title"], BODY.format(**values))


def test_a_clean_submission_becomes_a_lesson_with_the_gate_fields():
    lesson, notes = conv.convert(sample(), CANONICAL)
    assert lesson is not None, notes
    assert lesson["domain"] == "devops"
    assert lesson["tags"] == ["npm", "registry", "tls"]
    assert lesson["source"] == "dsh"
    assert lesson["summary_plain"].startswith("pnpm failed with ERR_PNPM_META_FETCH_FAIL")
    assert "## Verification" in lesson["content"]
    assert "Opire" not in lesson["content"], "the banner is not lesson text"


def test_a_non_canonical_domain_is_mapped_and_the_mapping_is_reported():
    lesson, notes = conv.convert(sample(domain="qt"), CANONICAL)
    assert lesson is not None
    assert lesson["domain"] == "frontend"
    assert any("qt → frontend" in note for note in notes), notes


def test_an_unknown_domain_is_skipped_with_the_name_in_the_reason():
    lesson, notes = conv.convert(sample(domain="quantum-computing"), CANONICAL)
    assert lesson is None
    assert "quantum-computing" in notes[0]


def test_a_missing_verification_is_recorded_as_missing_not_invented():
    full = sample()
    body = full["body"].replace("## Verification\nMetadata fetch returns HTTP 200 and the install completes.\n", "")
    lesson, notes = conv.convert({**full, "body": body}, CANONICAL)
    assert lesson is not None
    assert "Not recorded by the submitter." in lesson["content"]
    assert any("no Verification" in note for note in notes), notes


def test_a_windows_path_survives_the_yaml_round_trip():
    """The 2026-10-30 batch: `verify: "E:\\Deepseek\\..."` made YAML read `\\D` as an escape."""
    lesson, _ = conv.convert(sample(verify=r"Run C:\Users\eric\bin\tool.exe and check exit 0."),
                             CANONICAL)
    text = conv.render(lesson, "2026-10-31")
    block = text.split("---", 2)[1]
    parsed = yaml.safe_load(block)
    assert parsed["verify"].startswith("Run C:\\Users\\eric\\bin\\tool.exe"), parsed["verify"]
    assert parsed["title"] and parsed["domain"] == "devops"


def test_a_title_longer_than_the_gate_limit_is_trimmed_on_a_word_boundary():
    lesson, _ = conv.convert(sample(title="word " * 40), CANONICAL)
    assert lesson is not None
    assert len(lesson["title"]) <= 120
    assert lesson["title"].endswith("…")


def test_tags_are_capped_at_ten_and_deduplicated():
    full = sample()
    body = full["body"].replace("**Tags:** npm, registry, tls",
                                "**Tags:** npm, npm, " + ", ".join(f"tag{i}" for i in range(15)))
    lesson, _ = conv.convert({**full, "body": body}, CANONICAL)
    assert lesson is not None
    assert len(lesson["tags"]) == 10


def test_a_chinese_title_keeps_its_words_in_the_slug():
    """ASCII-stripping turned `偏航阈值…50/30/35 是上限` into `50-30-35` — a URL made of a number."""
    assert conv.slugify("长上下文污染", 2738) == "长上下文污染"
    assert conv.slugify("偏航阈值是几何下限 50/30/35 是上限", 4170).startswith("偏航阈值是几何下限")
    assert conv.slugify("npm registry unreachable: pin a mirror", 1) == "npm-registry-unreachable-pin-a-mirror"


def test_a_duplicate_of_a_published_lesson_is_skipped_not_written(tmp_path, monkeypatch):
    published = tmp_path / "lessons.json"
    published.write_text(json.dumps([{"id": "npm-registry-unreachable-pin-a-mirror",
                                      "title": "npm registry unreachable: pin a mirror"}]),
                         encoding="utf-8")
    monkeypatch.setattr(conv, "PUBLISHED", published)
    assert "npm registry unreachable: pin a mirror" in conv.published_titles()


def test_the_cli_writes_files_and_a_slug_map(tmp_path, monkeypatch):
    monkeypatch.setattr(conv, "LESSONS_DIR", tmp_path / "contrib")
    (tmp_path / "contrib").mkdir()
    issues = tmp_path / "issues.json"
    issues.write_text(json.dumps([sample()]), encoding="utf-8")
    slugs = tmp_path / "slugs.json"
    code = conv.main(["--issues-json", str(issues), "--write", "--created", "2026-10-31",
                      "--slugs", str(slugs)])
    assert code == 0
    written = list((tmp_path / "contrib").glob("*.md"))
    assert len(written) == 1
    assert written[0].name == "npm-registry-unreachable-pin-a-mirror.md"
    assert json.loads(slugs.read_text(encoding="utf-8")) == {"101": "npm-registry-unreachable-pin-a-mirror"}


def test_the_cli_dry_run_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(conv, "LESSONS_DIR", tmp_path / "contrib")
    (tmp_path / "contrib").mkdir()
    issues = tmp_path / "issues.json"
    issues.write_text(json.dumps([sample()]), encoding="utf-8")
    assert conv.main(["--issues-json", str(issues)]) == 0
    assert list((tmp_path / "contrib").glob("*.md")) == []


def test_a_maintainer_override_corrects_one_domain_and_says_so():
    """Four `packaging` issues in the 2026-10-31 queue are all iOS IPA signing — `mobile`, not `devops`."""
    lesson, notes = conv.convert(sample(domain="packaging"), CANONICAL, {"domain": "mobile"})
    assert lesson is not None
    assert lesson["domain"] == "mobile"
    assert any("maintainer override" in note for note in notes), notes


def test_a_title_override_replaces_the_submitter_title():
    lesson, notes = conv.convert(sample(), CANONICAL, {"title": "A clearer title"})
    assert lesson is not None
    assert lesson["title"] == "A clearer title"
    assert any("title replaced" in note for note in notes), notes


def test_a_fenced_fix_keeps_its_shell_comments():
    """Measured 2026-11-02: `# 1)` inside a bash fence ended the section and the lesson lost its Fix."""
    body = """**Kind:** lesson_submission

## Problem

It fails.

## Root Cause

The array is empty.

## Fix

```bash
# 1) expand safely
rm -f "${ARR[@+\"${ARR[@]}\"}"

# 2) braces after the variable
echo "size=${size}）"
```

Use python for logic.

## Verification

Run it with `set -u` and see no unbound variable.

**Tags:** bash, set-u
"""
    fix = conv.section(body, "Fix")
    assert "# 1) expand safely" in fix, "the first bash comment must survive"
    assert "# 2) braces after the variable" in fix, "so must the second"
    assert "Use python for logic." in fix, (
        "prose after the fence is part of the section too; stopping at the fence would be the same "
        "truncation one step later")
    assert conv.section(body, "Verification").startswith("Run it with"), (
        "Verification must still start after the fence ends, not inside it")


def test_an_empty_form_heading_does_not_shadow_the_submitters_heading():
    """The MCP intake form writes `## Problem` with nothing under it, then the submitter's own heading.

    Measured 2026-11-09 on 50 open need-human-review intakes: the first occurrence is empty for most
    of them, and taking only that occurrence made the converter report "missing Problem" for reports
    that carried a complete one.
    """
    full = sample()
    body = full["body"].replace(
        "## Problem\npnpm failed with ERR_PNPM_META_FETCH_FAIL against registry.npmjs.org.\n",
        "## Problem\n\n## Problem\npnpm failed with ERR_PNPM_META_FETCH_FAIL against registry.npmjs.org.\n",
    )
    lesson, notes = conv.convert({**full, "body": body}, CANONICAL)
    assert lesson is not None, notes
    assert "ERR_PNPM_META_FETCH_FAIL" in lesson["content"]


def test_a_symptom_heading_is_accepted_as_the_problem():
    full = sample()
    body = full["body"].replace("## Problem\n", "## Problem\n\n## 症状\n", 1)
    lesson, notes = conv.convert({**full, "body": body}, CANONICAL)
    assert lesson is not None, notes
    assert "ERR_PNPM_META_FETCH_FAIL" in lesson["content"]


def test_the_trigger_does_not_say_the_title_twice():
    """An intake body opens with the sentence its title was cut from.

    So `f"{title}. {problem}"` produced a trigger whose second half repeated the first, and the part
    `shorten()` then cut off was the distinctive one — the error string. Measured on the 2026-11-15
    batches: all ten drafts had a trigger that read the same 80 characters twice, and every one of
    them had to be rewritten by hand before the lesson could ship.
    """
    title = "PySide6 GUI app aborts at an arbitrary moment with a Fatal Python error"
    problem = ("PySide6 GUI app aborts at an arbitrary moment with a Fatal Python error "
               "none_dealloc: deallocating None, and the stack names innocent paint code.")
    trigger = conv.trigger_of(title, problem, conv.FIELDS_MAX["trigger"])
    assert trigger.count(title[:40]) == 1, f"the title's opening appears more than once: {trigger!r}"
    assert "none_dealloc" in trigger, (
        "the distinctive half — the error text — is what a reader searches for, and it is what the "
        f"duplicated-title version cut off: {trigger!r}")


def test_an_unrelated_title_still_gets_the_problem_after_it():
    trigger = conv.trigger_of("uv rebuilds a per-version environment",
                              "A bare `uv run` resolved another interpreter and recreated the path.",
                              conv.FIELDS_MAX["trigger"])
    assert trigger.startswith("uv rebuilds a per-version environment.")
    assert "bare `uv run`" in trigger


def test_tags_come_from_the_tools_when_the_submission_has_none():
    """`while`/`testing`/`project` is what a first-sentence title produces, and it names nothing.

    The tools a lesson actually shows (`uv`, `pyside6`, `json`) are what a reader searches for, and
    they are already in the text as single-token code spans.
    """
    body = ("## Problem\nA bare `uv run` rebuilt `pyside6`'s environment and `json.loads` behaved "
            "differently.\n## Root Cause\nBecause the interpreter moved.\n")
    tags = conv.tags_of(body, "While testing one project on multiple Python versions")
    assert tags[:2] == ["uv", "pyside6"], tags
    assert "while" not in tags and "project" not in tags


def test_a_submission_without_tags_or_tools_falls_back_to_title_words_minus_connectives():
    tags = conv.tags_of("## Problem\nx\n", "While testing one project with pnpm on windows")
    assert "while" not in tags and "with" not in tags, tags
    assert tags, "the gate needs at least one tag"


def test_a_uuid_is_not_a_tag():
    """`e17ad3b9-e76` is what the submitter's system handed them, not a topic a reader searches for.

    Measured on the 2026-11-15 queue: two of five drafts were tagged with a hex fragment of a request
    id, and one with the intake's own formatting word (`problem`) because it survived into the title.
    """
    body = ("## Problem\nStore ids like `e17ad3b9-e76a-4c` and `abdffc0e-acd` leaked into the log.\n"
            "## Root Cause\nTwo stores.\n")
    tags = conv.tags_of(body, "Problem stdio server used two stores")
    assert not any("e17ad3b9" in t or "abdffc0e" in t for t in tags), tags
    assert "problem" not in tags, tags


def test_the_submitters_own_trigger_wins_over_the_synthesised_one():
    """`## Trigger` is the field the intake tool requires now. A synthesised trigger restated the
    title instead of generalising it, so when the submitter wrote one the converter must keep it."""
    body = (
        "**Kind:** lesson_submission\n"
        "**Domain:** devops\n"
        "**Tags:** git, gitlab, permissions\n"
        "\n## Problem\n"
        "GitLab push denied on a project whose remote is already configured\n"
        "\n## Trigger\n"
        "git push denied but clone works protected branch role\n"
        "\n## Root Cause\n"
        "The protected branch allows Maintainers; the account is a Developer.\n"
        "\n## Fix\n"
        "Ask for the role, or push from a fork.\n"
        "\n## Verification\n"
        "re-run `git push origin HEAD`: it creates the commit instead of 403\n"
    )
    lesson, notes = conv.convert(issue(5088, "GitLab push denied", body), CANONICAL)
    assert lesson is not None, notes
    assert lesson["trigger"] == "git push denied but clone works protected branch role"
    assert lesson["verify"].startswith("re-run `git push origin HEAD`")


def test_an_issue_without_a_trigger_falls_back_to_the_old_synthesis():
    """Older issues and hand-converted bodies carry no `## Trigger`; they must still convert."""
    lesson, notes = conv.convert(sample(), CANONICAL)
    assert lesson is not None, notes
    assert lesson["trigger"].startswith("npm registry unreachable")


def test_a_generic_label_is_dropped_from_the_title():
    """The intake form's first heading is a label, not a topic (#5380).

    Measured 2026-11-19: 16 of the 38 lessons in one batch were titled `症状 …` / `Problem …` /
    `Symptom: …`, because the client writes the form's first heading as the issue title.
    """
    lesson, notes = conv.convert(sample(title="症状 写了一堆断言全绿，把实现改回错的测试还是全绿"), CANONICAL)
    assert lesson is not None
    assert lesson["title"].startswith("写了一堆断言")
    assert "generic label dropped from the title" in notes

    latin, _ = conv.convert(sample(title="Symptom: the panel reads nothing after a resize"), CANONICAL)
    assert latin is not None
    assert latin["title"].startswith("the panel reads nothing")


def test_a_title_that_is_only_the_label_keeps_it():
    """An empty title fails the gate; a redundant one does not. So the label stays when it is all there is."""
    lesson, _ = conv.convert(sample(title="Symptom"), CANONICAL)
    assert lesson is not None
    assert lesson["title"] == "Symptom"


def test_a_fence_that_opens_after_prose_is_moved_to_its_own_line():
    """#5349: `可脚本化：```bash` renders a literal fence and opens a block that never ends."""
    lesson, _ = conv.convert(
        sample(verify='对每条断言执行四步，可脚本化：```bash\ncp impl.py impl.bak\n```'), CANONICAL)
    assert lesson is not None
    # A fence line is what the renderer recognises; moving it off the prose line is the whole fix.
    assert re.search(r"(?m)^```bash$", lesson["content"])

    # The assertion that actually failed CI: no fence marker may survive into the rendered prose.
    sys.path.insert(0, str(REPO / "scripts"))
    import lesson_markdown
    prose = re.sub(r"<pre>[\s\S]*?</pre>", "", lesson_markdown.render(lesson["content"]))
    assert "```" not in prose


def test_a_trimmed_body_title_yields_to_the_untrimmed_issue_title():
    """The client trims `**Title:**`; the issue title is the same sentence, untrimmed.

    Measured 2026-11-20 on three submissions: the body carried `… flag always-r` while the issue title
    read `… flag always-rewritten logs`, so the lesson shipped with the stub even though the full
    sentence was one API field away.
    """
    full = sample()
    trimmed = "npm registry unreachable: pin"
    body = full["body"].replace("**Title:** " + full_title(full), "**Title:** " + trimmed)
    lesson, notes = conv.convert({**full, "body": body}, CANONICAL)
    assert lesson is not None
    assert lesson["title"] == full_title(full)
    assert any("title taken from the issue" in note for note in notes)


def test_two_different_titles_keep_the_submitters_field():
    """Only a prefix relation means "one of them was cut"; anything else is a judgement, not a guess."""
    assert conv._the_longer_prefix("the panel is blank", "npm registry unreachable") == "the panel is blank"
    assert conv._the_longer_prefix("", "issue title") == "issue title"


def full_title(issue_dict: dict) -> str:
    return issue_dict["title"].removeprefix("[Lesson] ").strip()


def test_one_tag_is_enough_because_the_gate_says_so():
    """The converter was stricter than `lesson_gate.validate_tags()`: it demanded two.

    Measured 2026-11-20 on 81 open intakes: 10 were refused for having exactly one tag while being
    otherwise complete — the batch was applying a rule the corpus does not have.
    """
    full = sample()
    body = full["body"].replace("**Tags:** npm, registry, tls", "**Tags:** npm")
    lesson, _ = conv.convert({**full, "body": body}, CANONICAL)
    assert lesson is not None
    assert lesson["tags"][0] == "npm" and len(lesson["tags"]) >= 1


def test_a_submission_with_no_tags_still_converts_from_its_tools():
    """`tags_of()` tops up from the tools the lesson names, so "no Tag line" is not a refusal."""
    full = sample()
    body = full["body"].replace("**Tags:** npm, registry, tls", "**Tags:** ")
    lesson, _ = conv.convert({**full, "body": body}, CANONICAL)
    assert lesson is not None
    assert lesson["tags"]


def test_a_hyphenated_phrase_in_a_code_span_stops_reading_as_a_command():
    """`delete-candidate` is a phrase; `get-help` is a command. Only the first is un-backticked."""
    prose, touched = conv.debacktick_prose_compounds(
        "keep it out of the `delete-candidate` list, unlike `get-help` or `write-warning`", known={"get-help", "write-warning"})
    assert touched == 1
    assert "`delete-candidate`" not in prose
    assert "delete-candidate list" in prose
    assert "`get-help`" in prose and "`write-warning`" in prose


def test_a_single_word_in_a_code_span_is_left_alone():
    """A single lowercase word may be an internal binary name — that is what the gate is protecting."""
    prose, touched = conv.debacktick_prose_compounds("run `skillspector` before the build", known=set())
    assert touched == 0
    assert "`skillspector`" in prose


def test_a_cause_heading_inside_the_problem_paragraph_is_used():
    """#5403: `## Root Cause` sat mid-paragraph, so it was reported missing while being right there.

    `section()` matches headings at line start, and this client wrote one inside the free-text
    paragraph. The fix lives in the paragraph; the submitter marked the boundary, so splitting there
    is strictly better evidence than any sentence heuristic.
    """
    body = """**Kind:** lesson_submission
**Domain:** mcp
**Title:** item count alone does not identify a stale read
## Problem
An asynchronous task-list read returned the old items after a recovery transition. ## Root Cause
Item count alone does not identify a stale read: the list length was identical before and after.
## Fix
Compare the item identities, not the count.
## Verification
Re-read the list and compare ids.
**Tags:** mcp, cache
"""
    lesson, notes = conv.convert(issue(5403, "item count alone does not identify a stale read", body), CANONICAL)
    assert lesson is not None, notes
    assert "## Root Cause\n\nItem count alone does not identify a stale read" in lesson["content"]
    assert "returned the old items after a recovery transition." in lesson["content"]
    assert any("sat inside the Problem paragraph" in note for note in notes)
