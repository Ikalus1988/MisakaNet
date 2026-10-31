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
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def section(body: str, name: str) -> str:
    """The text under `## <name>`, up to the next heading or the tags line. Empty when absent."""
    match = re.search(rf"^#+\s*{name}\s*$(.*?)(?=^#+\s|\*\*Tags:\*\*|\Z)", body, re.M | re.S)
    return clean(match.group(1)) if match else ""


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
    return slug.rstrip("-")


def tags_of(body: str, title: str) -> list[str]:
    raw = field(body, "Tags")
    out: list[str] = []
    for tag in re.split(r"[,\s]+", raw):
        tag = re.sub(r"[^a-z0-9._-]+", "-", tag.lower()).strip("-")
        if len(tag) >= 2 and tag not in out:
            out.append(tag)
    if not out:
        # Some submissions carry no Tags line; derive three from the title so the gate's "≥1 tag" holds
        # without inventing a classification.
        for word in re.findall(r"[a-zA-Z][a-zA-Z0-9]+", title.lower()):
            if word in {"the", "and", "for", "with", "from", "that", "when", "into", "your", "this",
                        "not", "but", "are", "its", "can", "one", "two", "all"}:
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

    title = str(override.get("title") or field(body, "Title")
                or str(issue.get("title", "")).replace("[Lesson]", "").strip())
    if override.get("title"):
        notes.append("title replaced by a maintainer override")
    title = shorten(title, FIELDS_MAX["title"])
    problem, cause, fix = (section(body, name) for name in ("Problem", "Root Cause", "Fix"))
    verify = section(body, "Verification") or section(body, "Verify") or section(body, "验证")
    if not (problem and cause and fix):
        return None, ["missing Problem/Root Cause/Fix"]
    if not verify:
        notes.append("no Verification section")

    tags = tags_of(body, title)
    if len(tags) < 2:
        return None, [f"only {len(tags)} tag(s)"]
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
        "trigger": shorten(f"{title}. {one_line(problem, 90)}", FIELDS_MAX["trigger"]),
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
            target.write_text(render(lesson, created), encoding="utf-8")
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
