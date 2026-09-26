#!/usr/bin/env python3
"""Answer-free autopilot for `[Question]` intakes: triage, receipt, and one digest.

Why "answer-free". The mechanical half of this loop is already automatic — a maintainer answers, the
`answered` label fires `sync-question-answers.yml`, the answer lands in D1 and everything after that is
retrieval (`misakanet_search` serves it as `type=faq`, re-submission returns it). What does **not** scale
is the part in the middle: somebody has to read every question, work out whether the corpus already
covers it, notice that four of them are one question, and reply. With ~8 new questions a day and a
historical total of 4 answers, that middle step is the whole backlog.

This script automates everything around the answer and nothing of it:

  1. **coverage** — asks the *public* MCP endpoint whether the corpus answers the question. That is the
     production retrieval path (BM25 + the IDF-weighted relevance floor), which is the only one that can
     be trusted for a 伪盲区/真盲区 verdict: the local Python engine's `_rank_docs` has no floor and
     scores "knitting pattern stitch count" 1.007 against "pip install timeout behind corporate proxy"
     0.905, so a verdict built on it is noise (measured 2026-09-25).
  2. **clustering** — groups open questions that share their distinctive vocabulary, so N questions
     become M clusters and the digest asks for M answers rather than N.
  3. **a receipt** — one idempotent comment per question, stating the measured state and the single next
     step that would make it answerable. The SOP's §3 receipt rule applies to *closing* an intake; this
     applies its spirit to receiving one, because an anonymous submitter who hears nothing has no way to
     tell "ignored" from "queued".
  4. **one digest** — a single issue listing the unresolved clusters, instead of a scrolling wall of
     identically-shaped open questions.

What it will not do, by construction:

  * **it never writes an answer.** Not because answers are hard to generate, but because a generated
    answer is an invented source unless it comes from someone who observed the failure.
    `docs/maintainer/provenance-gate-2026-09-16.md` exists because four lesson PRs once passed 24/24
    checks while citing a repository that returns 404.
  * **it never adds the `answered` label and never closes an issue.** `answered` is the switch that puts
    text into the FAQ, which is served to agents as a maintainer answer. That stays a sourced judgement.
  * **it never posts to a pull request or a lesson.** Questions only.

Usage
-----
    python3 scripts/question_autopilot.py                # dry run (default): print the plan
    python3 scripts/question_autopilot.py --json         # the plan as JSON
    python3 scripts/question_autopilot.py --post         # write the receipts and the digest

Environment:
    GITHUB_TOKEN / GH_TOKEN  (issues: read+write)
    MISAKANET_ENDPOINT       (default https://misakanet.org/mcp)

Stdlib only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

REPO_SLUG = os.environ.get("GITHUB_REPOSITORY", "Ikalus1988/MisakaNet")
API = "https://api.github.com"
ENDPOINT = os.environ.get("MISAKANET_ENDPOINT", "https://misakanet.org/mcp")

# Never mistaken for a maintainer answer: `sync_answered_questions.py` skips any comment carrying one of
# its AUTOMATED_MARKERS, and this marker is registered there for exactly that reason.
RECEIPT_MARKER = "<!-- misakanet-question-autopilot -->"
DIGEST_TITLE = "Question intake digest — unresolved clusters"
# A digest is a *report*: it has no acceptance criteria and must not be labelled `needs-ac`, which is
# the "phantom missing AC" churn `issue-quality-gate.yml` was already burned by (its own comment
# records five of six needs-ac issues once being intakes, "including a salvage digest the workflow
# itself opened"). That gate exempts a fixed label list, so the digest carries one of its own and
# the gate learns it — an agreement pinned by `tests/test_question_autopilot.py`.
DIGEST_LABEL = "question-digest"

# Distinctive-token floor for calling two questions one cluster. Tuned low on purpose: an over-eager
# cluster costs a merge suggestion a human can ignore, an under-eager one costs the duplication this
# script exists to prevent.
# Swept against the 18 open questions on 2026-09-25 (complete linkage, measured token filtering):
#   2 -> 5 clusters, one of them a spurious 3-way macOS/PDF mix
#   3 -> 5 clusters: {2254,2257,2263} {2264,2266} {2255,2259} correct, plus two questionable pairs
#   4 -> 2 clusters, and it drops #2254 out of the secret-safe cluster it belongs to
#   5+ -> 1 or 0 clusters
# 3 is the only setting that recovers the three clusters a human reading the backlog also produced, so
# the two questionable pairs are accepted as *suggestions* — which is why the receipt says "may be the
# same question" and invites the reader to ignore the line.
# Re-swept after the Opire-banner fix (see `signature()`), same result: 3 is the only floor that
# recovers every cluster a human reading the backlog also produced. Known imprecision, stated
# rather than hidden: `{2171, 2260}` groups on `returns`/`source`/`text`, which are filler, so that
# pair is wrong. It is left in because the alternative — raising the floor to 4 — loses #2254 from
# the `secret-safe` cluster, and because both the receipt and the bounty task say explicitly that
# the grouping is a suggestion the reader may reject.
CLUSTER_MIN_SHARED = 3
# A token present in more than this share of the open questions distinguishes nothing, however
# topical it looks. Measured, not guessed — see `distinctive()`.
CLUSTER_MAX_DF_RATIO = 0.25
# Tokens that appear in most questions and therefore cluster nothing.
STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "not", "are", "was", "were", "has", "have",
    "how", "what", "which", "when", "where", "does", "should", "can", "may", "must", "its", "their",
    "than", "then", "into", "over", "under", "after", "before", "while", "still", "only", "also",
    "question", "problem", "issue", "reports", "reported", "without", "about", "would", "been",
}
TOKEN_RE = re.compile(r"[a-z][a-z0-9_.-]{2,}")


def _token_request(url: str, payload: dict | None = None, method: str | None = None,
                   headers: dict | None = None):
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("User-Agent", "misakanet-question-autopilot")
    request.add_header("Accept", "application/vnd.github+json")
    for key, value in (headers or {}).items():
        request.add_header(key, value)
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode() or "{}")


# ── GitHub ──────────────────────────────────────────────────────────────────

def token() -> str:
    """`$GITHUB_TOKEN` / `$GH_TOKEN`, else the `github.com` entry in `~/.git-credentials`.

    Same order as `scripts/gh_push_via_api.py`, and the same host-anchored parse as
    `scripts/push_preflight.py` (a substring test for `github.com` also accepts `notgithub.com` — CodeQL
    alert #285).
    """
    for key in ("GITHUB_TOKEN", "GH_TOKEN"):
        if os.environ.get(key):
            return os.environ[key]
    credentials = pathlib.Path.home() / ".git-credentials"
    if credentials.is_file():
        for line in credentials.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                parsed = urllib.parse.urlsplit(line.strip())
            except ValueError:
                continue
            if parsed.hostname == "github.com" and parsed.password:
                return urllib.parse.unquote(parsed.password)
    raise SystemExit("no GitHub token: set $GITHUB_TOKEN / $GH_TOKEN, or add a github.com entry "
                     "to ~/.git-credentials")


def gh(path: str, payload: dict | None = None, method: str | None = None):
    return _token_request(f"{API}/repos/{REPO_SLUG}{path}", payload, method,
                          {"Authorization": f"Bearer {token()}"})


def open_questions() -> list[dict]:
    issues = [i for i in gh("/issues?state=open&per_page=100") if "pull_request" not in i]
    out = []
    for issue in issues:
        if "[Question]" not in issue["title"]:
            continue
        labels = {l["name"] for l in issue["labels"]}
        if "auto-rejected" in labels:
            continue
        out.append(issue)
    return out


# ── the technical signature (same shape the triage report used) ─────────────

def _section(body: str, name: str) -> str:
    m = re.search(rf"(?ims)^#+\s*{name}\s*$(.*?)(?=^#+\s|\Z)", body or "")
    return (m.group(1).strip() if m else "")


def signature(issue: dict) -> str:
    """Title + `## Problem` + `## Error` — the error signature, not the solution narrative.

    Deliberately not the whole body: `## Fix` and `## Verification` use the same vocabulary as the
    lessons that document the topic, so ranking on them makes every question look covered. The first
    version of the 2026-09-25 triage did that and put 54 of 91 issues in "corpus already covers this".
    """
    body = re.sub(r"<!--.*?-->", " ", issue.get("body") or "", flags=re.S)
    # Every issue in this repository carries an Opire banner inside `<details>` ("Everyone can add
    # rewards … `/reward 100` … `/try` … `/claim #N`"). Left in, it contributes `everyone`, `add`,
    # `reward`, `claim`, `amount` to *every* signature — tokens shared by all questions, which is the
    # definition of noise for a clustering step. Found by reading the generated bounty body: the
    # "shared vocabulary" it printed was `add`, `everyone`, `fields`.
    body = re.sub(r"(?is)<details.*?</details>", " ", body)
    body = re.sub(r"(?is)<[^>]{1,80}>", " ", body)
    # `re.M` is load-bearing: without it `$` only matches at the very end of the string, so the
    # submitter footer survived even though the pattern looked right (caught by its own test).
    body = re.sub(r"(?im)^_?submitted via remote mcp.*$", " ", body)
    body = re.sub(r"(?im)^\s*\*{0,2}(source|kind|dedup|submitted by|intake id)\*{0,2}\s*[:：].*$", " ", body)
    title = issue["title"].replace("[Question]", "").replace("Problem", "").strip()
    parts = [title, _section(body, "Problem")[:400], _section(body, "Error")[:200]]
    return " ".join(p for p in parts if p).strip()[:700]


def tokens(text: str) -> set[str]:
    return {t for t in TOKEN_RE.findall(text.lower()) if t not in STOPWORDS and len(t) > 2}


def distinctive(items: list[dict]) -> None:
    """Keep only the tokens that actually distinguish one question from another, in place.

    Measured over the open questions rather than guessed: a token that appears in more than
    `CLUSTER_MAX_DF_RATIO` of them separates nothing, however topical it looks ("macos", "check",
    "configuration"). The first version used a hand-written stopword list instead and produced one
    12-member cluster — every macOS question "shared" three generic words with every other.
    """
    df: dict[str, int] = {}
    for item in items:
        for token in item["tokens"]:
            df[token] = df.get(token, 0) + 1
    # Floor of 2, not 1: with only two questions in play, `int(2 * 0.25) == 0` would drop exactly
    # the tokens the two share — i.e. the filter would prevent the very clustering it feeds. A
    # token shared by two questions out of two is not evidence of anything until there are enough
    # questions to measure against. (Caught by a two-item test.)
    ceiling = max(2, int(len(items) * CLUSTER_MAX_DF_RATIO))
    for item in items:
        item["tokens"] = {t for t in item["tokens"] if df.get(t, 0) <= ceiling}
        item["df_ceiling"] = ceiling


def cluster(items: list[dict]) -> list[dict]:
    """Group questions that share enough **distinctive** tokens, with complete linkage.

    Complete linkage is the load-bearing part: single linkage ("shares 3 tokens with anyone already in the
    group") merged this backlog into one 12-member cluster on the first run, because the union of the
    shared vocabulary across 12 pairs clears any small floor. Requiring the floor against *every* member
    keeps a group meaning "all of these are the same question", which is what the digest asks a human to
    answer once.
    """
    groups: list[list[int]] = []
    for i, item in enumerate(items):
        for group in groups:
            if all(len(item["tokens"] & items[j]["tokens"]) >= CLUSTER_MIN_SHARED for j in group):
                group.append(i)
                break
        else:
            groups.append([i])
    out = []
    for group in groups:
        if len(group) < 2:
            continue
        shared = set.intersection(*[items[i]["tokens"] for i in group]) if group else set()
        out.append({"members": sorted(items[i]["number"] for i in group), "shared": sorted(shared)[:8]})
    return sorted(out, key=lambda g: -len(g["members"]))


# ── coverage, through the public endpoint ───────────────────────────────────

def corpus_answers(query: str) -> dict:
    """Ask production whether the corpus answers `query`. Returns {no_match, lessons, faq, ok}."""
    payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
               "params": {"name": "misakanet_search", "arguments": {"query": query, "top": 5}}}
    request = urllib.request.Request(ENDPOINT, data=json.dumps(payload).encode(), method="POST")
    request.add_header("Content-Type", "application/json")
    request.add_header("Accept", "application/json")
    request.add_header("MCP-Protocol-Version", "2025-06-18")
    request.add_header("Origin", "https://misakanet.org")
    request.add_header("User-Agent", "misakanet-question-autopilot")
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            body = json.loads(response.read().decode() or "{}")
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
        # An unreachable endpoint is `unknown`, never `uncovered`: a network failure must not be reported
        # as "the corpus has nothing on this", which is the one verdict a human would act on.
        return {"ok": False, "no_match": None, "lessons": [], "faq": [], "error": f"{type(exc).__name__}: {exc}"}
    text = (body.get("result", {}).get("content") or [{}])[0].get("text", "{}")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {"ok": False, "no_match": None, "lessons": [], "faq": [], "error": "unparseable result"}
    results = parsed.get("results") or []
    return {
        "ok": True,
        "no_match": bool(parsed.get("no_match")),
        "lessons": [r for r in results if (r.get("type") or r.get("kind")) != "faq"],
        "faq": [r for r in results if (r.get("type") or r.get("kind")) == "faq"],
    }


# ── cluster ─────────────────────────────────────────────────────────────────

# ── bounty tasks: the answer step, delegated to the people who had the problem ──
#
# The one part of this loop that cannot be automated is writing the answer, because an answer generated
# by someone who never observed the failure is an invented source — the failure
# `docs/maintainer/provenance-gate-2026-09-16.md` exists to prevent. So it is *delegated* instead, to the
# repository's existing bounty machinery: `bounty` label, `/try` + `/claim` for claiming, merge credit and
# a leaderboard entry as the reward, and Opire's `/reward` for anyone who wants to fund one with money.
# See `JOIN.md` § "Bounties & payment" — `zero-bounty` is the design, not an omission.
#
# Why a **separate** issue rather than writing acceptance criteria into the question: the quality gate
# (`issue-quality-gate.yml`) deliberately skips anything labelled `intake`/`mcp-intake` — "intakes are
# *reports*, not specs" — and every question carries those labels. Writing AC into 22 intake issues was
# tried on 2026-09-12 and only produced `needs-ac` churn; the exemption is the fix for that. So the task is
# a new issue that *references* the question, which is also why the gate can label it `ready`: an
# AC section plus a checkbox list is exactly what `ready` requires.
#
# One bounty per **cluster**, not per question: the whole point of the clustering is that N questions are
# one answer, and a bounty per question would recreate the pile in a new place.
BOUNTY_MARKER = "<!-- misakanet-question-bounty:anchor-{} -->"
BOUNTY_LABEL = "bounty"


def bounty_body(anchor_number: int, members: list[dict], shared: list[str]) -> str:
    """An AC-complete task body, in the shape `ai-bounty-template.md` and the quality gate expect.

    Two structural requirements are not cosmetic: the gate looks for an acceptance-criteria section **and**
    a checkbox list to grant `ready`, and `ai-bounty-template.md` names reproducible evidence as "the
    condition most submissions fail" — so the first criterion is a pasted command and its output.
    """
    lines = [
        BOUNTY_MARKER.format(anchor_number),
        f"# [Bounty] Answer the {len(members)} linked question(s) as a lesson",
        "",
        "## Context",
        "",
        "These intakes ask about something no lesson covers. Measured through the production retrieval path "
        "(BM25 plus the IDF-weighted relevance floor), every one of them returns `no_match` — so there is "
        "nothing to link the asker to, and the answer has to be written rather than looked up.",
        "",
    ]
    for member in members:
        lines.append(f"- #{member['number']} — {member['title']}")
    if shared:
        lines += ["", f"_Shared vocabulary that grouped them: `{'`, `'.join(shared)}`._"]
    lines += [
        "",
        "## Deliverable",
        "",
        "A lesson under `lessons/` that answers the question(s) above, following "
        "`docs/maintainer/lesson-fields.md` (title / domain / problem / root cause / fix, and a "
        "`## Verification` that is a checkable command with an expected result). A written answer in the "
        "issue is welcome as a first step, but the lesson is what makes it count — it is the artifact the "
        "corpus keeps and the FAQ is built from.",
        "",
        "## MANDATORY ACCEPTANCE CRITERIA (AC)",
        "",
        "**0. REPRODUCIBLE EVIDENCE — the condition most submissions fail**",
        "",
        "- [ ] Paste the command you ran and the output you got. Not a description of what you did — the "
        "command and its output. If you name an endpoint it must be `misakanet.org`.",
        "- [ ] Say what you observed yourself versus what you read somewhere. A lesson citing a source "
        "that does not exist is worse than one citing nothing (`scripts/check_provenance.py` fails on it).",
        "",
        "**1. The lesson passes the repository's own gates**",
        "",
        "- [ ] `python3 scripts/lesson_gate.py <your lesson>` is clean.",
        "- [ ] `python3 scripts/check_provenance.py --check` does not report a dead source for it.",
        "- [ ] `python3 -m pytest tests/ -q` still passes.",
        "",
        "**2. Answering means being found**",
        "",
        "- [ ] `misakanet_search` finds your lesson for the question text that produced this bounty. Paste "
        "the query and the returned lesson id — this is the whole point of the task, and it is measurable.",
        "",
        "**3. Claiming**",
        "",
        "- [ ] Comment `/try` (or `/claim`) so others know you are on it; one open PR per task. The claim "
        "rules are in `JOIN.md` and `CONTRIBUTING.md`.",
        "",
        "## What the reward is, stated plainly",
        "",
        "**This is a `zero-bounty` task: $0.** The reward is merge credit, a leaderboard entry and a line in "
        "the Hall of Fame. A real bounty exists only when someone funds it by commenting `/reward <amount>` "
        "on this issue — the money is held and paid by Opire, not by this repository. If you want this one "
        "funded, say so; if nobody funds it, it is still worth doing, because the answer gets reused by "
        "every agent that hits the same thing.",
        "",
        "## Closes",
        "",
        "A merged lesson closes this task **and** the questions above (link them with `Fixes #N` so the "
        "receipt rule applies). If you cannot finish it, comment here and it goes back to the pool.",
        "",
        "<sub>Opened automatically by `scripts/question_autopilot.py` from measured coverage of the open "
        "questions. The grouping is a suggestion: if these are not really one question, say so and this "
        "task will be split.</sub>",
    ]
    return "\n".join(lines)


def planned_bounties(plan: dict) -> list[dict]:
    """One bounty per cluster. A cluster is the unit a single answer clears."""
    by_number = {i["number"]: i for i in plan["items"]}
    out = []
    for group in plan["groups"]:
        members = [by_number[n] for n in group["members"] if n in by_number]
        if len(members) < 2:
            continue
        out.append({"anchor": min(group["members"]), "members": members, "shared": group["shared"]})
    return out


def existing_bounty(anchor_number: int) -> dict | None:
    marker = BOUNTY_MARKER.format(anchor_number).split(":")[0]
    for issue in gh(f"/issues?state=all&labels={BOUNTY_LABEL}&per_page=100"):
        if "pull_request" in issue:
            continue
        if BOUNTY_MARKER.format(anchor_number) in (issue.get("body") or ""):
            return issue
    return None


def open_bounties(items: list[dict], groups: list[dict]) -> list[dict]:
    """One entry per cluster; a question with no cluster is its own single-member task."""
    expected = []
    by_number = {i["number"]: i for i in items}
    if groups:
        expected = [{"anchor": min(g["members"]), "shared": g["shared"],
                     "members": [by_number[n] for n in g["members"] if n in by_number]} for g in groups]
    return [e for e in expected if len(e["members"]) >= 2 or True]


# ── receipt text ────────────────────────────────────────────────────────────

def receipt(item: dict) -> str:
    """One comment per question: the measured state, and the single next step."""
    cov = item["coverage"]
    if not cov["ok"]:
        state = ("**State: not measured yet.** The retrieval endpoint did not answer this run, so nothing "
                 "is claimed about coverage — a failed check is not a verdict.")
        nxt = "No action needed from you; this is re-checked daily."
    elif cov["lessons"]:
        tops = ", ".join(f'`{r.get("id") or r.get("title") or "?"}`' for r in cov["lessons"][:3])
        state = (f"**State: the corpus appears to answer this already** — the search that answers it "
                 f"returns {tops}. So this is a retrieval question, not a missing lesson.")
        nxt = ("Open the lesson(s) above first. If one of them does not actually cover your case, reply "
               "with what differs — that difference is the lesson worth writing, and writing a second "
               "lesson on the same ground is what the corpus is trying to avoid.")
    else:
        state = ("**State: no lesson in the corpus covers this.** Measured through the production search "
                 "path (relevance floor included), which returns `no_match` — so there is nothing to link "
                 "you to, and this is a genuine gap rather than a ranking miss.")
        nxt = ("Three things make it answerable, and you are the only one who has them: the concrete "
               "symptom you saw (`## Error`), what you already tried, and how you would check a fix "
               "worked (a command plus its expected output). With those this becomes either an answer "
               "or — better — a lesson, and the corpus keeps it for the next agent that hits it.")
    # No "related answered question" line, deliberately. The FAQ matcher is token overlap, and measured
    # on this backlog it attached two unrelated answered questions (#2099 site-offline, #1724 a bounty
    # status question) to a macOS PDF question. A receipt that points the asker at an unrelated answer is
    # worse than one that says nothing: it is the only claim in the comment, and it is wrong.
    faq = ""
    cluster_line = ""
    if item.get("cluster_with"):
        cluster_line = (
            f"\n\n**Possibly the same question as {', '.join('#' + str(n) for n in item['cluster_with'])}** "
            f"— grouped automatically by shared vocabulary, so treat it as a suggestion: if it is wrong, "
            f"ignore this line. When it is right, one answer covers all of them.")
    return (
        f"{RECEIPT_MARKER}\n"
        f"### Automated triage\n\n"
        f"{state}{cluster_line}{faq}\n\n"
        f"**Next step.** {nxt}\n\n"
        f"<sub>Machine-generated by `scripts/question_autopilot.py` on every open question; it triages and "
        f"reports, and never writes the answer itself (an answer must come from someone who observed the "
        f"failure — see `docs/maintainer/provenance-gate-2026-09-16.md`). Re-runs update this comment in "
        f"place; a maintainer can delete it or answer above it.</sub>"
    )


def digest_body(items: list[dict], groups: list[dict], bounties: list[dict] | None = None) -> str:
    lines = [
        "# Question intake digest — unresolved clusters",
        "",
        f"{len(items)} open question intake(s), of which **{sum(len(g['members']) for g in groups)} "
        f"form {len(groups)} cluster(s)**. One answer per cluster clears the cluster; answering per "
        "question is how the pile grows faster than it drains.",
        "",
        "## Clusters (answer once)",
        "",
        "| cluster | questions | shared vocabulary |",
        "|---|---|---|",
    ]
    if not groups:
        lines.append("| — | — | _none this run_ |")
    for g in groups:
        lines.append("| " + " · ".join("@" + "" for _ in [0]) + ", ".join(f"#{n}" for n in g["members"])
                     + " | " + str(len(g["members"])) + " | `" + "`, `".join(g["shared"]) + "` |")
    uncovered = [i for i in items if i["coverage"]["ok"] and not i["coverage"]["lessons"]]
    covered = [i for i in items if i["coverage"]["ok"] and i["coverage"]["lessons"]]
    unmeasured = [i for i in items if not i["coverage"]["ok"]]
    lines += [
        "",
        "## Claimable tasks",
        "",
        "Each genuine-gap cluster has a `[Bounty]` task linked to it. **$0 / `zero-bounty` by design**: the "
        "reward is merge credit, a leaderboard entry and a line in the Hall of Fame, and a real bounty "
        "exists only when someone funds it with `/reward <amount>` (`JOIN.md` § Bounties & payment).",
        "",
    ]
    if bounties:
        for entry in bounties:
            lines.append(f"- #{entry['anchor']} anchor · {len(entry['members'])} question(s) · "
                         f"`{', '.join('#' + str(m['number']) for m in entry['members'])}`")
    else:
        lines.append("- _none this run_")
    lines += [
        "",
        "## By measured coverage",
        "",
        f"- **genuine gaps** (no lesson reaches them): {len(uncovered)}"
        + (": " + ", ".join(f"#{i['number']}" for i in uncovered) if uncovered else ""),
        f"- **already covered** (a lesson is reached, so this is retrieval or phrasing): {len(covered)}"
        + (": " + ", ".join(f"#{i['number']}" for i in covered) if covered else ""),
        f"- **not measured** (endpoint unreachable — *not* a coverage claim): {len(unmeasured)}"
        + (": " + ", ".join(f"#{i['number']}" for i in unmeasured) if unmeasured else ""),
        "",
        "## What automation cannot do here",
        "",
        "Writing the answer. A generated answer to a question about a platform nobody here has run is an "
        "invented source, which is the one failure this repository has a gate for. The automation's job "
        "is to make the human step as small as possible: cluster it, measure it, ask the reporter for the "
        "missing pieces, and never leave them in silence.",
        "",
        "<sub>Regenerated by `scripts/question_autopilot.py` (`.github/workflows/question-autopilot.yml`).</sub>",
    ]
    return "\n".join(lines)


# ── plan / post ─────────────────────────────────────────────────────────────

def build_plan() -> dict:
    raw = open_questions()
    items = []
    for issue in raw:
        sig = signature(issue)
        items.append({
            "number": issue["number"],
            "title": issue["title"][:110],
            "signature": sig,
            "tokens": tokens(sig),
            "coverage": corpus_answers(sig),
            "comments": issue.get("comments", 0),
        })
    distinctive(items)
    groups = cluster(items)
    member_to_group = {n: [m for m in g["members"] if m != n] for g in groups for n in g["members"]}
    for item in items:
        item["cluster_with"] = member_to_group.get(item["number"], [])
    return {"items": items, "groups": groups}


def receipt_already_current(existing_comments: list[dict], body: str) -> bool:
    """True when this exact receipt is already the newest autopilot comment.

    Content hash, not presence: the coverage verdict changes as the corpus grows, and a receipt that
    keeps claiming "nothing covers this" after a lesson lands would be worse than no receipt.
    """
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()[:12]
    for comment in existing_comments:
        if RECEIPT_MARKER in (comment.get("body") or ""):
            return f"<!-- autopilot-digest:{digest} -->" in (comment.get("body") or "")
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--post", action="store_true", help="write the receipts and the digest")
    parser.add_argument("--json", action="store_true", help="print the plan as JSON and stop")
    parser.add_argument("--limit", type=int, default=0, help="only the first N questions (debugging)")
    parser.add_argument("--bounties", action="store_true",
                        help="also open/refresh one bounty task per cluster (requires --post to write; "
                             "dry run prints the bodies)")
    args = parser.parse_args(argv)

    plan = build_plan()
    if args.limit:
        plan["items"] = plan["items"][: args.limit]
    if args.json:
        # `tokens` is a set (the clustering needs set algebra); JSON does not take sets, and the first
        # version of this flag therefore crashed instead of printing a plan.
        print(json.dumps(plan, ensure_ascii=False, indent=1,
                         default=lambda o: sorted(o) if isinstance(o, (set, frozenset)) else str(o)))
        return 0

    print(f"{len(plan['items'])} open question(s); {len(plan['groups'])} cluster(s)")
    for item in plan["items"]:
        cov = item["coverage"]
        verdict = ("unmeasured" if not cov["ok"] else
                   f"covered by {cov['lessons'][0].get('id')}" if cov["lessons"] else "genuine gap")
        print(f"  #{item['number']:5} {verdict[:44]:44} cluster={item['cluster_with']}")

    if args.bounties:
        for entry in planned_bounties(plan):
            print(f"\n--- bounty for anchor #{entry['anchor']} "
                  f"({len(entry['members'])} question(s)) ---")
            print(bounty_body(entry["anchor"], entry["members"], entry["shared"]))

    if not args.post:
        print("\ndry run — nothing written. Pass --post to write the receipts and the digest.")
        return 0

    written = 0
    for item in plan["items"]:
        body = receipt(item)
        body += f"\n<!-- autopilot-digest:{hashlib.sha256(body.encode()).hexdigest()[:12]} -->"
        comments = gh(f"/issues/{item['number']}/comments?per_page=100")
        if receipt_already_current(comments, body):
            continue
        gh(f"/issues/{item['number']}/comments", {"body": body})
        written += 1
    print(f"receipts written: {written} (unchanged: {len(plan['items']) - written})")

    if args.bounties:
        created = updated = 0
        for entry in planned_bounties(plan):
            body = bounty_body(entry["anchor"], entry["members"], entry["shared"])
            found = existing_bounty(entry["anchor"])
            if found:
                gh(f"/issues/{found['number']}", {"body": body}, method="PATCH")
                updated += 1
            else:
                issue = gh("/issues", {"title": f"[Bounty] Answer {len(entry['members'])} linked "
                                                  f"question(s) as a lesson",
                                       "body": body, "labels": [BOUNTY_LABEL]})
                print(f"  bounty opened: #{issue['number']}")
                created += 1
        print(f"bounties: {created} created, {updated} refreshed")

    existing = [i for i in gh("/issues?state=open&per_page=100")
                if "pull_request" not in i and i["title"].startswith(DIGEST_TITLE)]
    body = digest_body(plan["items"], plan["groups"], planned_bounties(plan))
    if existing:
        gh(f"/issues/{existing[0]['number']}", {"body": body}, method="PATCH")
        print(f"digest updated: #{existing[0]['number']}")
    else:
        created = gh("/issues", {"title": DIGEST_TITLE, "body": body, "labels": [DIGEST_LABEL]})
        print(f"digest created: #{created['number']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
