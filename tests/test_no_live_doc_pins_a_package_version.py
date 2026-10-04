#!/usr/bin/env python3
"""No *current* document may pin a MisakaNet package version literal.

What this is for, measured on `main` at 206d7214d: `docs/LIMITATIONS.md`,
`docs/json-ld-schema.md` and `docs/mcp-quickstart.md` told readers to install
`misakanet@2.39.0` / `ghcr.io/.../misakanet:2.39.0` while the release manifest said
**2.41.0**. Two releases adrift, and nothing noticed, because the only version rule in
the repo (`tests/test_version_consistency.py`) compares manifests against *each other*
and reads `API.md` against an upper bound. A version in prose is not a manifest.

`API.md` already diagnosed this for its own example and prescribed the cure — a
placeholder plus "read the live value from here" — after watching `2.30.2` sit there for
nine releases. This gate generalises that: the two documented cures are

1. a placeholder (`<current version>`, `<serverInfo.version>`), or
2. no literal at all — `:latest`, or the package name on its own,

and a current document choosing neither is the defect.

The exclusion model is the same one `tests/test_zero_dependency_wording.py` established,
for the same reason: a record of a past event is not current guidance, and a rule that
cannot tell them apart goes red over history and is then switched off.

* **History directories** — dated snapshots, transcripts, corpus material. Same list that
  file uses, so the two gates cannot drift apart on what counts as history.
* **Shell transcripts** — a version inside a fenced block whose lines are prompts
  (`$ …`, `> …`) is a record of a command someone ran, and the output under it is the
  evidence. `docs/agents/client-half-testing.md` is the case in point: it quotes
  `npm pack misakanet@2.40.0` next to the grep output that command produced. Editing the
  literal there would falsify the transcript, not document anything.
* **The release ledger itself** — `.release-please-manifest.json`, `package.json`,
  `server.json` and friends *are* the version of record. A literal is the whole point.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Directories whose files are records rather than current guidance. Kept identical to
# `tests/test_zero_dependency_wording.py::HISTORY`; the rationale is documented there.
HISTORY = (
    "CHANGELOG.md",
    "archive/", "data/", "lessons/", "tasks/", "tests/",
    "docs/adr/", "docs/agents/crawler-intake-bot.md", "docs/baseline/", "docs/benchmarks/", "docs/blog/",
    "docs/bounty-notes/", "docs/data/", "docs/field-reports/", "docs/journey-reports/", "docs/lessons/",
    "docs/maintainer/", "docs/openclaw-pr/", "docs/prd/", "docs/releases/", "docs/reports/",
    "docs/reviews/", "docs/roadmap/",
)

# Files that are the version of record. A literal version is their job.
VERSION_OF_RECORD = {
    ".release-please-manifest.json",
    "package.json",
    "server.json",
    "glama.json",
    "packages/misakanet-setup/package.json",
    "docs/index.html",
    "docs/.well-known/agent.json",
    "docs/.well-known/agent-card.json",
    "docs/.well-known/mcp.json",
    "docs/.well-known/glama.json",
    ".claude-plugin/plugin.json",
    ".codex-plugin/plugin.json",
    "scripts/misakanet_cli.py",
    "workers/register-proxy-sw.js",
}

# `misakanet@1.2.3` (npm) and `misakanet:1.2.3` (container tag), either plain or in a host path.
PINNED = re.compile(r"misakanet[@:][0-9]+\.[0-9]+\.[0-9]+")

# A JSON-LD `softwareVersion` is the same defect wearing a different hat, and the first cut of
# this rule missed it: the line reads `"softwareVersion": "2.39.0"`, with no package name on it,
# so a `misakanet[@:]` pattern cannot see it. Caught only by running the detector against the
# real pre-fix text, which is why that run is in the verification and not just the unit tests.
SOFTWARE_VERSION = re.compile(r'"softwareVersion"\s*:\s*"[0-9]+\.[0-9]+\.[0-9]+"')

FENCE = re.compile(r"^\s*(```|~~~)")
# A prompt line is what makes a fenced block a transcript rather than an example.
PROMPT = re.compile(r"^\s*[$>]\s")


def _tracked_files(repo: Path) -> list[Path]:
    """The files git would publish — not everything on disk.

    `git ls-files -z`, for the reason recorded in `tests/test_zero_dependency_wording.py`:
    a filesystem walk reads nested copies of old releases as if they were the repository.
    `-z` keeps git from quoting non-ASCII names, `os.fsdecode` handles the platform encoding.
    """
    out = subprocess.run(["git", "-C", str(repo), "ls-files", "-z"],
                         capture_output=True, check=True).stdout
    return [repo / os.fsdecode(name) for name in out.split(b"\0") if name]


def _current_copy(root: Path | None = None) -> list[Path]:
    repo = REPO if root is None else Path(root)
    if (repo / ".git").exists():
        candidates = [p for p in _tracked_files(repo) if p.is_file()]
    else:
        # A `tmp_path` fixture is not a checkout; the red cases below build plain directories.
        candidates = [p for p in sorted(repo.rglob("*")) if p.is_file()]
    out = []
    for path in candidates:
        if path.suffix not in (".md", ".html", ".json", ".py", ".mjs", ".js"):
            continue
        rel = path.relative_to(repo).as_posix()
        if rel in VERSION_OF_RECORD or "node_modules" in rel:
            continue
        if any(rel.startswith(prefix) for prefix in HISTORY):
            continue
        out.append(path)
    return out


def _is_transcript(text: str) -> list[tuple[int, str]]:
    """Lines that sit inside a fenced block containing a shell prompt.

    Returns `(line number, line)` pairs for fenced-block lines only when the block looks
    like a transcript, and an empty list for a file with no such block — so an example
    block (`docker pull …`) is *not* excused, only a recorded session is.
    """
    hits: list[tuple[int, str]] = []
    in_block = False
    block: list[tuple[int, str]] = []
    for number, line in enumerate(text.splitlines(), 1):
        if FENCE.match(line):
            if in_block:
                if any(PROMPT.match(inner) for _, inner in block):
                    hits.extend(block)
                block = []
                in_block = False
            else:
                in_block = True
            continue
        if in_block:
            block.append((number, line))
    return hits


def pinned_version_offenders(root: Path | None = None) -> list[str]:
    """Current-copy lines that pin a package version literal."""
    repo = REPO if root is None else Path(root)
    offenders: list[str] = []
    for path in _current_copy(repo):
        rel = path.relative_to(repo).as_posix()
        # `errors="replace"`: a wording rule needs no byte fidelity, and a crash on one
        # undecodable file names nothing.
        text = path.read_text(encoding="utf-8", errors="replace")
        excused = {n for n, _ in _is_transcript(text)}
        for number, line in enumerate(text.splitlines(), 1):
            if number in excused:
                continue
            if PINNED.search(line) or SOFTWARE_VERSION.search(line):
                offenders.append(f"{rel}:{number}: {line.strip()[:100]}")
    return offenders


def current_version() -> str:
    """The version of record, read from the file release-please updates."""
    import json  # noqa: PLC0415 - only needed here
    return json.loads((REPO / ".release-please-manifest.json").read_text(encoding="utf-8"))["."]


def test_no_current_document_pins_a_package_version() -> None:
    """A version in prose is not a manifest, and nothing else here can see it."""
    offenders = pinned_version_offenders()
    assert not offenders, (
        f"{len(offenders)} current document(s) pin a MisakaNet version literal, while the "
        f"release manifest says {current_version()}. A reader following one installs an old "
        "build. Use a placeholder (`<current version>`), or no literal at all (`:latest`, or "
        "the package name on its own) and say where the real value comes from — the cure "
        "API.md already prescribes for its own example:\n"
        + "\n".join(f"  {line}" for line in offenders[:10])
    )


def test_the_rule_notices_a_pinned_version_in_a_current_doc(tmp_path) -> None:
    """Reverse test: the detector must fire on the shape it is meant to catch.

    Without this, a regex that silently stopped matching — a renamed package, a loosened
    pattern, a refactor — would leave the gate green forever.
    """
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "install.md").write_text(
        "Install it with `npm i -g misakanet@2.39.0`.\n", encoding="utf-8"
    )
    assert pinned_version_offenders(tmp_path), (
        "the rule did not notice a pinned version in a current doc — it would never fire"
    )


def test_the_rule_notices_a_json_ld_software_version(tmp_path) -> None:
    """The shape the first cut of this rule could not see.

    `docs/json-ld-schema.md` carried `"softwareVersion": "2.39.0"` — no package name on the
    line, so a `misakanet[@:]` pattern walks straight past it. It was found by running the
    detector against the real pre-fix text, and it gets its own test so the widening cannot
    be quietly undone.
    """
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "json-ld-schema.md").write_text(
        '      "softwareVersion": "2.39.0",\n', encoding="utf-8"
    )
    assert pinned_version_offenders(tmp_path), (
        "a JSON-LD softwareVersion literal was not noticed — that is the exact gap this test exists for"
    )


def test_a_pinned_version_inside_a_shell_transcript_is_a_record_not_guidance(tmp_path) -> None:
    """The other half: a recorded session must not trip the gate.

    `docs/agents/client-half-testing.md` quotes `npm pack misakanet@2.40.0` next to the
    grep output that command produced. Treating that as install guidance would push a
    maintainer to edit a transcript, which falsifies it.
    """
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "run.md").write_text(
        "Measured live:\n\n```console\n$ npm pack misakanet@2.40.0 --pack-destination /tmp\n"
        "main\n```\n",
        encoding="utf-8",
    )
    assert not pinned_version_offenders(tmp_path), (
        "a shell transcript was treated as current guidance; the exclusion is too broad"
    )


def test_an_example_block_is_not_excused_by_being_fenced(tmp_path) -> None:
    """Only a *transcript* is history. A fenced example is still an instruction.

    This is the direction the previous test does not cover: if the prompt check were
    dropped, every fenced example would become invisible and the gate would go quiet.
    """
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "install.md").write_text(
        "```bash\ndocker pull ghcr.io/ikalus1988/misakanet:2.39.0\n```\n", encoding="utf-8"
    )
    assert pinned_version_offenders(tmp_path), (
        "a fenced example block was excused; the transcript rule is matching any fence"
    )


def test_history_directories_keep_their_own_wording(tmp_path) -> None:
    """`CHANGELOG.md` and the dated reports record releases; they must not be rewritten."""
    (tmp_path / "docs" / "maintainer").mkdir(parents=True)
    (tmp_path / "docs" / "maintainer" / "handoff-2026-09-15.md").write_text(
        "`misakanet@2.30.0` was published.\n", encoding="utf-8"
    )
    (tmp_path / "CHANGELOG.md").write_text(
        "* publish misakanet@2.30.0\n", encoding="utf-8"
    )
    assert not pinned_version_offenders(tmp_path), (
        "history was flagged; the gate would go red on every release and be switched off"
    )


def test_the_version_of_record_files_are_exempt(tmp_path) -> None:
    """`package.json` *is* the version. A literal there is the whole point."""
    (tmp_path / "package.json").write_text('{"name": "misakanet", "version": "2.41.0"}\n',
                                           encoding="utf-8")
    assert not pinned_version_offenders(tmp_path), (
        "the version of record was flagged; the rule would contradict release-please"
    )


def main() -> int:
    offenders = pinned_version_offenders()
    if offenders:
        print(f"{len(offenders)} current document(s) pin a package version "
              f"(manifest says {current_version()}):", file=sys.stderr)
        for line in offenders:
            print(f"  {line}", file=sys.stderr)
        return 1
    print(f"no current document pins a package version literal (manifest {current_version()})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
