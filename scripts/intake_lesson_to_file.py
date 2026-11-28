#!/usr/bin/env python3
"""Convert `[Lesson]` submission issues into lesson files — mechanically, and only mechanically.

The `[Lesson]` queue is the one backlog whose material is already written: each issue carries
`Kind/Source/Node/Domain/Title` plus `## Problem`, `## Root Cause`, `## Fix`, `## Verification`. On
2026-10-30 a batch of 53 was converted by hand-rolled code kept outside the repository; this is that
code, with the parts that were wrong fixed and the decisions written down:

* **YAML quoting is not cosmetic.** The first batch emitted `verify: "E:\\Deepseek\\..."`; YAML read
  `\\D` as an unknown escape and the whole frontmatter became unparseable — the file looked fine in an
  editor while the gate saw *no frontmatter at all* and reported every field missing.
* **The domain vocabulary is closed.** `qt`, `agent-tooling`, `ai-agent`, `tia`, `design`, `edge-ai`
  are not canonical domains; they map to the nearest canonical one and every substitution is printed.
* **The gate's limits are the contract**: title ≤120, `summary_plain` ≤120, `trigger` ≤160,
  `verify` ≤200, ≤10 tags. Values are trimmed, never invented: a section that is absent in the issue
  stays absent (`Verification` is filled with an explicit "not recorded by the submitter"), because a
  fabricated verification line is the one thing this pipeline exists to prevent.
* **Duplicates are corpus-wide.** Two of every batch turn out to be lessons that already merged (4 of
  53 on 2026-10-30); the check compares against `data/lessons.json`, not just against the batch, or the
  queue quietly doubles.

Usage
-----
    python3 scripts/intake_lesson_to_file.py --issues-json issues.json          # dry run
    python3 scripts/intake_lesson_to_file.py --issues-json issues.json --write  # write the files
    python3 scripts/intake_lesson_to_file.py --fetch --write --limit 20         # from GitHub

`--issues-json` takes the REST payload (`GET /repos/{owner}/{repo}/issues?labels=lesson-submission`).
`--fetch` calls the API itself and needs `GITHUB_TOKEN`/`GH_TOKEN`.

What it does not do: it does not close the source issues, and it does not run the gates. Both are
deliberate — a converter that closes issues would hide a bad conversion, and one that ran the gate
would have to re-implement it. The flow is: convert → `lesson_gate.py` → receipts on the issues that
were converted, close those and the duplicates.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LESSONS_DIR = REPO / "lessons" / "contrib"
PUBLISHED = REPO / "data" / "lessons.json"
DOMAINS = REPO / "data" / "domains.json"

SLUG_MAX = 60
#: Bytes, not characters: the corpus is checked out on Windows filesystems too (see `slugify`).
SLUG_MAX_BYTES = 96
FIELDS_MAX = {"summary_plain": 120, "trigger": 160, "verify": 200, "title": 120}
TAGS_MAX = 10

#: Non-canonical domains seen in submissions, and the canonical one each really is. A closed vocabulary
#: is what keeps `--domain search` meaningful; the mapping is here rather than in the issues because it
#: is a data problem (the issue says `qt`, the corpus says `frontend`), not a submitter's mistake.
DOMAIN_MAP = {
    "qt": "frontend",
    "agent-tooling": "agent",
    "ai-agent": "agent",
    "ai": "llm",
    "edge-ai": "llm",
    "design": "ux",
    "tia": "automation",
    # The 2026-10-31 wave: 21 `ios` + 5 `swiftui` submissions and 4 `packaging` ones, none of which is a
    # canonical domain. Apple UI work is `mobile` (the corpus's generic mobile bucket, next to `android`),
    # and packaging is `devops` — it is build/release work, not language work.
    "ios": "mobile",
    "swiftui": "mobile",
    "packaging": "devops",
}


# ── parsing an issue body ───────────────────────────────────────────────────

def clean(text: str) -> str:
    text = text.replace("<br/>", " ").replace("<hr/>", " ")
    text = re.sub(r"<details.*?</details>", " ", text, flags=re.S)  # the Opire banner
    # The footer `submit_intake` appends after its sections. Without this it lands inside whichever
    # section is last — measured 2026-11-02, it turned up at the end of `Verification` and inside the
    # `verify:` frontmatter field, so a reader saw "_Submitted via remote MCP_" as part of the fix.
    text = re.sub(r"\n---\s*\n_Submitted via remote MCP[^\n]*\n?", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


_FENCE_RE = re.compile(r"^\s*(?:```|~~~)")

#: The intake form's own first heading, when a client uses it as the title. Not a topic: it says
#: "this is a symptom" and nothing about what broke, so it is dropped before the gate's 120-character
#: budget is spent on it (measured 2026-11-19 on the batch that produced 16 of 38 lessons titled
#: `症状 …` / `Problem …` / `Symptom: …`). `现象` joined the list on 2026-11-22 for the same reason and
#: from the same gap: four submissions used it as the heading where the form's `## Problem` was empty,
#: so the section reader had to learn it and the titles arrived as `现象 Windows 上 …`.
_GENERIC_TITLE_PREFIX = re.compile(r"^(?:症状|问题|现象|Problem|Symptom)\s*[:：]?\s+", re.IGNORECASE)


def strip_generic_prefix(title: str) -> str:
    """The title without a leading `症状` / `问题` / `Problem` / `Symptom` label.

    A label is not a topic: it is the intake form's first heading, and the same word would be on
    every lesson that came in through the same shape. Dropped only when something is left — a title
    that *is* the label keeps it, because an empty title fails the gate and a wrong one does not.
    """
    stripped = _GENERIC_TITLE_PREFIX.sub("", title.strip(), count=1).strip()
    return stripped if len(stripped) >= 8 else title


#: A code span that is a hyphenated phrase of ordinary lowercase words is prose, not a command name.
#: The lesson gate reads every code span as a command name (`validate_public_surface`), so a sentence
#: like "keep them out of the `delete-candidate` list" fails it — the same confusion that had to be
#: fixed by hand on 2022-11-20 batches. A real hyphenated command (`get-help`, `write-warning`) is in
#: the corpus vocabulary or its allowlist, so it is never touched here.
_HYPHENATED_PROSE = re.compile(r"^[a-z]+(?:-[a-z]+)+$")


def _known_surface_names() -> set[str]:
    """The corpus vocabulary plus the allowlist, or an empty set when it cannot be read."""
    try:
        import lesson_gate  # local import: this module is importable without the gate
        return lesson_gate.load_public_vocabulary(REPO, base=False) or set()
    except Exception:  # noqa: BLE001 — a missing vocabulary must not stop a conversion
        return set()


def debacktick_prose_compounds(text: str, known: set[str] | None = None) -> tuple[str, int]:
    """Turn `` `delete-candidate` `` into `delete-candidate` when it is a phrase, not a command.

    Returns the rewritten text and how many spans were touched, so the batch report can say so.
    """
    vocabulary = _known_surface_names() if known is None else known
    touched = 0

    def replace(match: re.Match) -> str:
        nonlocal touched
        token = match.group(1).strip()
        if not _HYPHENATED_PROSE.match(token) or token in vocabulary:
            return match.group(0)
        touched += 1
        return token

    return re.sub(r"`([^`\n]{2,60})`", replace, text), touched


def _the_longer_prefix(a: str, b: str) -> str:
    """Whichever of two renderings of the same sentence is longer, or `a` when they differ.

    The client trims the `**Title:**` field and the issue title is the same sentence untrimmed, so a
    prefix relation means one of them was cut. Anything else (two genuinely different titles) keeps
    the submitter's field, which is the more specific of the two.
    """
    a, b = (a or "").strip(), (b or "").strip()
    if a and b and (b.startswith(a) or a.startswith(b)):
        return b if len(b) > len(a) else a
    return a or b


def fences_start_a_line(text: str) -> str:
    """Move a fence that opens mid-line onto its own line.

    The renderer only recognises a fence at the start of a line (`_FENCE_RE` above, and
    `scripts/lesson_markdown.py`). A fence that opens after prose is therefore *text* — and the
    closing fence, which does start a line, then opens a block that never ends. Measured
    2026-11-19 on the batch PR #5349: an intake whose Verification read `可脚本化：```bash` was copied
    verbatim, so the page rendered a literal ``` and
    `test_no_fence_marker_leaks_outside_a_code_block` failed on all six test legs.

    The fix belongs here rather than in the renderer: the renderer is right to require a fence line,
    and the intake is the thing that wrote a marker where no fence can be.
    """
    lines = []
    for line in text.split("\n"):
        lines.append(re.sub(r"(?<=\S)(```|~~~)", r"\n\1", line))
    return "\n".join(lines)


def section(body: str, name: str, *, allow_qualifier: bool = False) -> str:
    r"""The text under **every** `## <name>` heading, concatenated; empty when absent.

    Concatenating instead of taking the first occurrence: the MCP intake form emits an empty
    `## Problem` before the submitter's own heading, so the first occurrence is empty while the text
    lives under the second one. Measured 2026-11-09 on 50 open `needs-human-review` intakes — 16 of
    the 22 structurally complete ones were reported "missing Problem" for this reason alone.

    Headings are only headings **outside** a code fence. The first version of this function matched
    `^#+\s` anywhere, so a shell comment inside a `Fix` block ended the section: measured
    2026-11-02, a Chinese lesson whose Fix was a bash fence beginning `# 1) 空数组安全展开` was
    converted with an empty Fix and an empty Verification, and the lesson gate passed it because
    both headings were present. Every lesson with a commented command would have lost the same way.

    `allow_qualifier` accepts a heading that carries a parenthetical after the name —
    `## Root Cause（分两层，第一层是误诊）`, `## Fix（已验证有效）`. Measured 2026-11-22: two complete
    intakes were refused over one clause of heading decoration. A qualifier that **hedges** is not
    accepted, because reading `## Root Cause（推测，未证实）` would put a guess into the slot the rest
    of this pipeline treats as established — the one thing the conversion exists to prevent (#4556
    carries exactly that heading, same day).
    """
    lines = body.split("\n")
    suffix = r"(?:\s*[（(][^)）]*[)）])?" if allow_qualifier else ""
    wanted = re.compile(rf"^#+\s*{re.escape(name)}{suffix}\s*$")
    heading_re = re.compile(r"^#+\s*")
    chunks: list[str] = []
    current: list[str] | None = None
    in_fence = False
    for line in lines:
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            if current is not None:
                current.append(line)
            continue
        if not in_fence and heading_re.match(line):
            if current is not None:
                chunks.append("\n".join(current))
            hit = bool(wanted.match(line))
            if hit and allow_qualifier and _HEDGE_RE.search(line):
                # A heading that says its own content is a guess is not the cause. Dropped rather
                # than read, so the intake keeps its qualifier and stays in the queue — the same
                # outcome as a missing section, which is the honest one.
                hit = False
            current = [] if hit else None
            continue
        if current is not None:
            if not in_fence and line.strip().startswith("**Tags:**"):
                chunks.append("\n".join(current))
                current = None
                continue
            current.append(line)
    if current is not None:
        chunks.append("\n".join(current))
    return clean("\n".join(chunk for chunk in chunks if chunk.strip()))


def field(body: str, name: str) -> str:
    match = re.search(rf"\*\*{name}:\*\*\s*(.+)", body)
    return match.group(1).strip() if match else ""


def shorten(text: str, limit: int) -> str:
    """Trim to `limit` on a word boundary, marking the cut. Never rephrases."""
    text = re.sub(r"\s+", " ", text).strip().strip('"')
    if len(text) <= limit:
        return text
    cut = text[: limit - 1]
    if " " in cut:
        cut = cut[: cut.rfind(" ")]
    return cut.rstrip(" ,;:.") + "…"


def yq(value: str) -> str:
    """A double-quoted YAML scalar that survives Windows paths and stray quotes.

    `verify: "E:\\Deepseek\\..."` made YAML read `\\D` as an unknown escape, so the whole frontmatter
    became unparseable — the file still looked fine in an editor while the gate reported every field
    missing. Escaping both characters is the fix.
    """
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text.replace("\\", "\\\\").replace('"', '\\"')


def slugify(title: str, number: int) -> str:
    """The URL stem: Unicode words kept, everything else collapsed to dashes.

    ASCII-stripping was the first version, and it is wrong for most of this queue: a Chinese title lost
    its leading half and became `50-30-35` or `adddatarepresentative` — a URL that names a number
    fragment. The page generator (`build_lesson_pages.slugify`) keeps Unicode word characters, so the
    file stem and the page URL agree when this does the same.
    """
    text = unicodedata.normalize("NFKC", title).lower().strip()
    slug = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    if not slug:
        # Nothing word-like survived: the issue number keeps the URL stable and unique.
        return f"lesson-{number}"
    if len(slug) > SLUG_MAX:
        cut = slug[:SLUG_MAX]
        slug = cut[: cut.rfind("-")] if "-" in cut else cut
    # ...and in **bytes**, because the limit that actually bites is the path, not the characters:
    # this checkout lives under `/mnt/c/...` on a Windows filesystem, where the whole path stops at
    # 260 characters. A 60-character Chinese slug is 180 bytes, and `os.rename` failed with
    # "File name too long" on 2026-11-02 for exactly the titles this queue produces. 96 bytes keeps
    # ~30 CJK characters, which is still a name a person can read.
    encoded = slug.encode("utf-8")
    if len(encoded) > SLUG_MAX_BYTES:
        trimmed = encoded[:SLUG_MAX_BYTES].decode("utf-8", "ignore")
        slug = trimmed[: trimmed.rfind("-")] if "-" in trimmed else trimmed
    return slug.rstrip("-")


def _without_shared_opening(title: str, text: str) -> str:
    """`text` with the words it shares with `title` as an opening removed.

    An intake body opens with the sentence its title was cut from — that is how the client writes it —
    so `${title}. ${problem}` produced a trigger whose second half was the first half again. Measured
    on the 2026-11-15 batches: every generated draft's `trigger` read the same ~80 characters twice,
    and the part `shorten()` cut off was exactly the distinctive one (the error string).

    Three shared words is the floor: below that the two openings are coincidence ("A test…" /
    "A tool…"), and cutting would remove real text.
    """
    title_words = re.findall(r"\w+", title.lower())
    matches = list(re.finditer(r"\w+", text))
    shared = 0
    while (shared < len(title_words) and shared < len(matches)
           and title_words[shared] == matches[shared].group(0).lower()):
        shared += 1
    if shared < 3 or shared >= len(matches):
        return text
    return text[matches[shared].start():].lstrip(" \t,;:.-—")


def trigger_of(title: str, problem: str, limit: int) -> str:
    """The matchable fragment: the title, then only the part of the problem the title does not say.

    This is the **fallback** since 2026-11-16. The intake tool asks a lesson-shaped submission for
    `trigger` (the error fragment a future search would use) and requires it, because a trigger
    synthesised from `title + problem` is a restatement of the title, not a generalisation — measured
    on the 2026-11-15 batches, every generated draft read the same ~80 characters twice. Older issues
    and hand-converted ones still land here, which is why the function stays.
    """
    tail = _without_shared_opening(title, one_line(problem, 160))
    if not tail.strip():
        return shorten(title, limit)
    return shorten(f"{title}. {tail}", limit)


def normalise_tags(values) -> list[str]:
    """Tags as the corpus writes them: lower-case, hyphenated, de-duplicated, ≥2 characters."""
    out: list[str] = []
    for value in values:
        tag = re.sub(r"[^a-z0-9._-]+", "-", str(value).lower()).strip("-")
        if len(tag) >= 2 and tag not in out:
            out.append(tag)
    return out


def tags_of(body: str, title: str) -> list[str]:
    out = normalise_tags(re.split(r"[,\s]+", field(body, "Tags")))
    if len(out) < 3:
        # Some submissions carry no Tags line. Three candidates come from the **tools the lesson
        # actually names** (single-token code spans: `uv`, `pyside6`, `json.loads`), because that is
        # what a reader searches for — the 2026-11-15 batches tagged three lessons
        # `while`/`testing`/`project` off the first sentence of a title, which names nothing.
        #
        # Additive, not either/or: one tool is not a tag set. `tests/test_intake_form_asks_for_a_cause`
        # caught the first version refusing a report whose only span was `npm_config_registry` —
        # "only 1 tag(s)" — and that report was perfectly convertible.
        for span in re.findall(r"`([^`\n]{2,40})`", body):
            token = span.strip()
            if "\\" in token or "/" in token:
                continue
            parts = token.split()
            if not parts:
                continue
            # `uv run` is a command, and `uv` is the name a reader searches for. A span of four or
            # more words is prose or an error string (`Fatal Python error: none_dealloc …`), and its
            # first word is not a tool.
            if len(parts) > 3 or not parts[0][:1].islower():
                continue
            token = parts[0]
            tag = re.sub(r"[^a-z0-9._-]+", "-", token.lower()).strip("-.")
            # A UUID or a hex blob is an identifier the submitter's system handed them, not a topic:
            # `e17ad3b9-e76` as a tag is a string nobody searches for. Same for the intake's own
            # section words ("Problem …"), which are formatting that survived into the title.
            if re.fullmatch(r"[0-9a-f]{2,8}(-[0-9a-f]{2,})+", tag):
                continue
            if tag in {"problem", "error", "issue", "symptom", "cause", "fix", "solution", "root"}:
                continue
            if len(tag) >= 2 and tag not in out and not tag.isdigit():
                out.append(tag)
            if len(out) >= 3:
                break
    if len(out) < 3:
        for word in re.findall(r"[a-zA-Z][a-zA-Z0-9]+", title.lower()):
            if word in {"the", "and", "for", "with", "from", "that", "when", "into", "your", "this",
                        "not", "but", "are", "its", "can", "one", "two", "all", "while", "after",
                        "before", "during", "which", "what", "how", "why", "was", "were", "has",
                        "have", "does", "did", "then", "than", "them", "they", "there", "here",
                        "problem", "error", "issue", "symptom", "cause", "fix", "solution", "root",
                        "using", "shows", "appeared", "between", "because", "after", "under"}:
                continue
            if word not in out:
                out.append(word)
            if len(out) >= 3:
                break
    return out[:TAGS_MAX]


def one_line(text: str, limit: int) -> str:
    first = re.split(r"(?<=[.!?。！？])\s+", re.sub(r"\s+", " ", text).strip())[0]
    return shorten(first, limit)


# ── one issue → one lesson ──────────────────────────────────────────────────

CAUSE_MARKERS = ("根因", "原因是", "原因：", "原因:", "root cause", "Root Cause", "起因")
FIX_MARKERS = ("修复", "改为", "换用", "解决", "绕过", "改法", "对策", "fix:", "Fix:")


#: Words a heading uses to say its own content is not established. See `section(allow_qualifier=)`.
_HEDGE_RE = re.compile(r"推测|未证实|未确认|待确认|待定|不确定|猜测|suspected|unconfirmed|unknown|tbd",
                       re.IGNORECASE)

#: A cause marker the client wrote mid-paragraph: `## Root Cause`, `Root Cause:`, `根因：`, `原因：`.
_INLINE_CAUSE_RE = re.compile(r"#{1,6}\s*Root\s*Cause\s*|Root\s*Cause\s*[:：]\s*|根因\s*[:：]\s*|原因\s*[:：]\s*",
                              re.IGNORECASE)


def split_intake_problem(text: str) -> tuple[str, str, str] | None:
    """Split a `missing_lesson` Problem paragraph into (problem, cause, fix), verbatim.

    The intake form is documented as accepting "a partial failure description", and it writes one
    free-text paragraph under `## Problem` with no `## Root Cause` section. That is why **none** of
    the 164 intakes open on 2026-11-02 could be converted: `convert()` needs a cause, and a cause
    section was never asked for.

    This does not invent one. It splits the paragraph on sentence boundaries and assigns whole
    sentences by the markers the submitter wrote: the sentences before a 根因 / 原因是 / root cause
    sentence are the problem; that sentence is the cause; sentences carrying 修复 / 改为 / 绕过 are
    the fix. If any of the three is missing, it returns `None` and the intake stays in the queue —
    which is the honest outcome, because a lesson without a cause cannot be acted on.
    """
    sentences = [s.strip() for s in re.split(r"(?<=[。；;！!？?])\s*", text) if s.strip()]
    if len(sentences) < 2:
        return None
    cause_at = next((i for i, s in enumerate(sentences) if any(m in s for m in CAUSE_MARKERS)), None)
    if cause_at is None or cause_at == 0:
        return None
    problem = " ".join(sentences[:cause_at])
    cause = sentences[cause_at]
    rest = sentences[cause_at + 1:]
    fix = " ".join(s for s in rest if any(m in s for m in FIX_MARKERS))
    if not fix:
        rest_all = " ".join(rest).strip()
        fix = rest_all if rest_all else ""
    if not (problem and cause and fix):
        return None
    return problem, cause, fix


def convert(issue: dict, canonical: set[str],
            override: dict | None = None) -> tuple[dict | None, list[str]]:
    """A lesson record plus the normalisations applied, or `None` and the reasons it was skipped.

    `override` is a maintainer's correction for one issue — `{"domain": ...}` and/or `{"title": ...}`.
    Per-issue rather than a bigger `DOMAIN_MAP`, because the submitter's label is a guess about *their*
    submission, not a vocabulary: four `packaging` issues in the 2026-10-31 queue are all iOS IPA
    signing (`mobile`), while `packaging` as a topic is build/release work (`devops`). A vocabulary
    entry would be permanently wrong for one of them; an override is a decision about one issue.
    """
    notes: list[str] = []
    body = clean(issue.get("body") or "")
    raw_domain = field(body, "Domain").lower()
    override = override or {}
    if override.get("domain"):
        notes.append(f"domain {raw_domain or '?'} → {override['domain']} (maintainer override)")
        raw_domain = str(override["domain"]).lower()
    domain = DOMAIN_MAP.get(raw_domain, raw_domain)
    if domain not in canonical:
        return None, [f"domain {raw_domain!r} has no canonical form"]
    if domain != raw_domain:
        notes.append(f"domain {raw_domain} → {domain}")

    # `**Title:**` in the body is what the client wrote, and the client trims it; the issue title is the
    # same sentence untrimmed. When one is a prefix of the other, keep the longer — measured
    # 2026-11-20 on three submissions: the body carried `… flag always-r` while the issue title was
    # `… flag always-rewritten logs`, and the lesson shipped with the stub.
    body_title = field(body, "Title")
    issue_title = re.sub(r"^\[(?:Lesson|Intake|Question)\]\s*", "",
                         str(issue.get("title", ""))).strip()
    title = str(override.get("title") or _the_longer_prefix(body_title, issue_title))
    if override.get("title"):
        notes.append("title replaced by a maintainer override")
    elif body_title and title == issue_title and len(issue_title) > len(body_title):
        notes.append("title taken from the issue: the body's Title was trimmed")
    elif title != (stripped := strip_generic_prefix(title)):
        title = stripped
        notes.append("generic label dropped from the title")
    title = shorten(title, FIELDS_MAX["title"])
    # `现象` (symptom) is the heading four submissions used where the form's own `## Problem` was left
    # empty — measured 2026-11-22 on #5513–#5516, all four complete down to `## Verification`. `症状`
    # and `Symptom` were already here; `现象` was the one missing word.
    #
    # `背景` / `问题描述` / `问题`: what an **agent** writes when the client's empty `## Problem`
    # heading is left in place and the actual text goes under the next heading it types itself.
    # Measured 2026-11-28 over the 180 open `[Intake]` issues: **27** had an empty `## Problem` for
    # exactly this reason, 19 of them `## Problem` immediately followed by `## 背景` — and 24 of the
    # 27 came from `remote-agent`, i.e. the shape is specific to how agents submit, not to Chinese.
    # Including `背景` alone moves **1** of those 27 to convertible (#5852), so this is not a
    # conversion lever; it is a *message* lever. Without it the skip histogram says "missing
    # Problem/Root Cause/Fix" and the reader concludes the submitter wrote nothing, when the real
    # answer for most of them is "missing Root Cause" — a different backlog with a different fix.
    problem = (section(body, "Problem") or section(body, "现象") or section(body, "症状")
               or section(body, "Symptom") or section(body, "背景")
               or section(body, "问题描述") or section(body, "问题"))
    cause = section(body, "Root Cause")
    if not cause:
        # Two heading shapes the reader refused, both measured on 2026-11-22: the same section under
        # the Chinese name the submitter wrote (`## 根因`, #4748/#4671), and the canonical name
        # followed by a descriptive parenthetical (`## Root Cause（实测修正版）`, #5072). Neither
        # invents anything — the text is the submitter's own — so both are read, and the note says
        # which heading it came from.
        for heading, kwargs in (("根因", {}), ("Root Cause", {"allow_qualifier": True})):
            cause = section(body, heading, **kwargs)
            if cause:
                notes.append(f"Root Cause read from a `## {heading}` heading"
                             + (" carrying a qualifier" if kwargs else ""))
                break
    split = None
    if not cause:
        # A cause heading the client wrote **inside** the Problem paragraph is better evidence than
        # any sentence heuristic: the submitter marked the boundary themselves. Measured 2026-11-21 on
        # #5403, where `## Root Cause` sits mid-paragraph — `section()` matches headings at line start,
        # so the cause was reported missing while being right there (and the fix was in its own
        # `## Fix` section all along).
        inline = _INLINE_CAUSE_RE.search(problem or "")
        if inline:
            head = problem[:inline.start()].strip()
            tail = problem[inline.end():].strip()
            if head and tail:
                problem, cause = head, tail
                notes.append("Root Cause heading sat inside the Problem paragraph; split there, verbatim")
    if not cause:
        split = split_intake_problem(problem)
        if split:
            problem, cause, split_fix = split
            notes.append("sections split from the intake's Problem paragraph, sentences verbatim")
    # `## Fix (if known)` is what `misakanet_submit_intake` writes for a `missing_lesson` report, and
    # this reader only knew `## Fix` — so 111 of the 164 intakes open on 2026-11-02 carried a fix the
    # converter could not see. An alias, not a guess: it is the same section under the heading the
    # form actually emits.
    fix = (section(body, "Fix") or section(body, "Fix (if known)")
           or section(body, "修复") or section(body, "Solution")
           or (split[2] if split else ""))
    verify = section(body, "Verification") or section(body, "Verify") or section(body, "验证")
    if not (problem and cause and fix):
        # Two different backlogs, named separately. Before 2026-11-28 this was one string, and it read
        # as "the submitter wrote nothing" when measured over the open queue: 180 intakes, 146 hits —
        # but **143 of the 180 had no cause at all** (90 of them from the September/October form,
        # which had no Root Cause field), while `## Problem` itself was present in 156 and empty in
        # only 27. One label for both sent every reader after the wrong half.
        missing = []
        if not problem:
            missing.append("Problem")
        if not cause:
            missing.append("Root Cause")
        if not fix:
            missing.append("Fix")
        return None, [f"missing {'/'.join(missing)}"]
    if not verify:
        notes.append("no Verification section")

    # One tag is enough: `lesson_gate.validate_tags()` requires **at least one**, and the converter was
    # stricter than the gate. Measured 2026-11-20 on 81 open intakes: 10 were refused here while being
    # otherwise complete, i.e. the batch was applying a rule the corpus does not have.
    tags = tags_of(body, title)
    if override.get("tags"):
        # A report that carries everything except a `Tags` line is a lesson nobody can find: the two
        # fallbacks in `tags_of` (the tools the text names, then the title's words) both assume Latin
        # identifiers, so a Chinese report written in prose lands on zero — measured 2026-11-21 on
        # seven such intakes, each complete down to `## Verification`. Supplying tags is the same kind
        # of decision as `domain` and `title`: about one issue, by a human, said out loud in the notes
        # rather than typed into the submitter's text.
        tags = normalise_tags(override["tags"])[:TAGS_MAX]
        notes.append(f"tags supplied by a maintainer override: {', '.join(tags) or '(none left)'}")
    if not tags:
        return None, ["no tag(s) at all — the gate requires one"]
    problem, cause, fix, verify = (fences_start_a_line(value)
                                   for value in (problem, cause, fix, verify))
    # A hyphenated phrase in a code span reads to the gate as an unlisted command name; the prose
    # around it is what the submitter wrote, so the span — not the sentence — is what changes.
    known = _known_surface_names()
    debackticked = 0
    rewritten = []
    for value in (problem, cause, fix, verify):
        text_value, touched = debacktick_prose_compounds(value, known)
        debackticked += touched
        rewritten.append(text_value)
    problem, cause, fix, verify = rewritten
    if debackticked:
        notes.append(f"{debackticked} prose compound(s) un-backticked so the gate does not read them as commands")
    content = (f"## Problem\n\n{problem}\n\n## Root Cause\n\n{cause}\n\n## Fix\n\n{fix}\n\n"
               f"## Verification\n\n{verify or 'Not recorded by the submitter.'}\n")
    if len(content) < 120:
        return None, ["content under the gate's 100-character floor"]

    return {
        "number": issue["number"],
        "domain": domain,
        "title": title,
        "tags": tags,
        "content": content,
        "summary_plain": one_line(problem, FIELDS_MAX["summary_plain"]),
        # The submitter's own trigger wins: they are the only one who knows what a stranger would
        # search for. `## Trigger` is what `misakanet_submit_intake` writes; `**Trigger:**` and
        # `Trigger:` cover an issue written by hand or by an older client.
        "trigger": shorten(
            section(body, "Trigger") or field(body, "Trigger")
            or trigger_of(title, problem, FIELDS_MAX["trigger"]),
            FIELDS_MAX["trigger"],
        ),
        "verify": shorten(verify or fix, FIELDS_MAX["verify"]),
        "source": field(body, "Source") or "unknown",
    }, notes


def render(lesson: dict, created: str) -> str:
    tags = "\n".join(f'  - "{tag}"' for tag in lesson["tags"])
    return (
        "---\n"
        f'title: "{yq(lesson["title"])}"\n'
        f'domain: "{lesson["domain"]}"\n'
        "tags:\n"
        f"{tags}\n"
        'status: "published"\n'
        'evidence_level: "E1"\n'
        f'created: "{created}"\n'
        f'updated: "{created}"\n'
        f'source: "intake-{lesson["number"]}"\n'
        f'summary_plain: "{yq(lesson["summary_plain"])}"\n'
        f'trigger: "{yq(lesson["trigger"])}"\n'
        f'verify: "{yq(lesson["verify"])}"\n'
        "provenance:\n"
        f'  issue: "#{lesson["number"]}"\n'
        f'  source: "MCP intake ({lesson["source"]}), lesson submission converted by the maintainer"\n'
        "---\n\n"
        f'{lesson["content"]}'
    )


# ── the corpus, for duplicates ──────────────────────────────────────────────

def published_titles() -> dict[str, str]:
    """Normalised title → the lesson id that already has it."""
    try:
        rows = json.loads(PUBLISHED.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {re.sub(r"\s+", " ", str(row.get("title") or "")).strip().lower(): str(row.get("id"))
            for row in rows if isinstance(row, dict) and row.get("title")}


def fetch_issues(token: str, label: str = "lesson-submission", limit: int = 200) -> list[dict]:
    """Open issues carrying `label`, newest first."""
    url = (f"https://api.github.com/repos/{os.environ.get('GITHUB_REPOSITORY', 'Ikalus1988/MisakaNet')}"
           f"/issues?state=open&labels={label}&per_page={min(limit, 100)}&sort=created&direction=desc")
    request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                                   "Authorization": f"Bearer {token}",
                                                   "User-Agent": "misakanet-intake-converter"})
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.loads(response.read().decode() or "[]")
    if not isinstance(payload, list):
        raise ValueError("the issues endpoint did not return a list")
    return [issue for issue in payload if "pull_request" not in issue][:limit]


# ── CLI ─────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--issues-json", type=Path,
                        help="a saved REST issue payload (the `lesson-submission` label)")
    parser.add_argument("--fetch", action="store_true",
                        help="read the open `lesson-submission` issues from the API (needs GITHUB_TOKEN)")
    parser.add_argument("--write", action="store_true", help="write the lesson files (default: dry run)")
    parser.add_argument("--created", default=None,
                        help="the `created:` date for the new files (default: today, UTC)")
    parser.add_argument("--limit", type=int, default=0, help="only the first N issues")
    parser.add_argument("--overrides", type=Path, default=None,
                        help="JSON {issue number: {domain|title: value}} — maintainer corrections")
    parser.add_argument("--slugs", type=Path, default=None,
                        help="also write a JSON map {issue number: file stem} here (for receipts)")
    args = parser.parse_args(argv)

    from datetime import datetime, timezone
    created = args.created or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if args.issues_json:
        issues = json.loads(args.issues_json.read_text(encoding="utf-8"))
    elif args.fetch:
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
        if not token:
            print("--fetch needs GITHUB_TOKEN or GH_TOKEN", file=sys.stderr)
            return 2
        issues = fetch_issues(token, limit=args.limit or 200)
    else:
        parser.error("one of --issues-json or --fetch is required")
    if not isinstance(issues, list):
        print("the payload is not a list of issues", file=sys.stderr)
        return 2
    if args.limit:
        issues = issues[: args.limit]

    canonical = set(json.loads(DOMAINS.read_text(encoding="utf-8"))["canonical"])
    overrides = (json.loads(args.overrides.read_text(encoding="utf-8"))
                 if args.overrides else {})
    existing = published_titles()
    written: dict[int, str] = {}
    skipped: list[tuple[int, list[str]]] = []

    for issue in sorted(issues, key=lambda i: i.get("number", 0)):
        lesson, notes = convert(issue, canonical, overrides.get(str(issue.get("number"))))
        if lesson is None:
            skipped.append((issue["number"], notes))
            continue
        key = re.sub(r"\s+", " ", lesson["title"]).strip().lower()
        if key in existing:
            skipped.append((issue["number"], [f"duplicate of lessons/{existing[key]}"]))
            continue
        stem = slugify(lesson["title"], lesson["number"])
        target = LESSONS_DIR / f"{stem}.md"
        if target.exists():
            stem = f"{stem}-{lesson['number']}"
            target = LESSONS_DIR / f"{stem}.md"
            notes.append("slug already existed → suffixed with the issue number")
        if args.write:
            # newline="\n": `Path.write_text` translates to `os.linesep` otherwise, so a
            # conversion run on Windows commits CRLF lessons — measured 2026-11-20 on eight
            # submissions, which the `test_tracked_text_files_are_lf` gate rejected for six of them.
            # The gate is right: the cost lands on review, as a whole-file diff where the change is invisible.
            target.write_text(render(lesson, created), encoding="utf-8", newline="\n")
        written[lesson["number"]] = stem
        if notes:
            print(f"{issue['number']:6d} {stem[:60]:60s} " + "; ".join(notes))

    print(f"{'wrote' if args.write else 'would write'} {len(written)} lesson(s); "
          f"skipped {len(skipped)}")
    for number, notes in skipped:
        print(f"  skip #{number}: {'; '.join(notes)}")
    if args.slugs:
        args.slugs.write_text(json.dumps(written, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"slug map: {args.slugs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
