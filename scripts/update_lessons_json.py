#!/usr/bin/env python3
"""Regenerate data/lessons.json from indexed lesson directories.

The public index intentionally keeps a stable, lightweight shape used by the
website and GitHub workflows. It indexes curated/core lessons and contrib
lessons, while excluding archives, drafts, templates, locale docs, and the
top-level lessons/index.md.
"""
import json
import os
import re
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from misakanet.evidence import evidence_of, trust_score  # noqa: E402

LESSONS_DIR = REPO / "lessons"
# The published index. A *test* may redirect the write (MISAKANET_LESSONS_INDEX, the same
# env-override shape as MISAKANET_GAP_LOG / MISAKANET_CONTRIBUTION_QUEUE); nothing in
# production sets it, so the CLI and the daily job write here as before.
#
# WHY (2026-09-26): `tests/test_frontmatter_writers_agree.py` drives `queue_lesson.write_lesson`
# with a stubbed `git push` that *reports success*. The success branch of `write_lesson` rebuilds
# this index, so the real `data/lessons.json` was rewritten from the working tree in the middle of
# the suite — 411 entries → 415 the moment a pull request added a lesson. Two things followed:
# every *published* count surface (README, ARCHITECTURE, the site's meta tags, the issue
# templates, `docs/_lessons_count.txt`, …) was rewritten too, and
# `test_lesson_page_generator::test_repo_pages_match_the_index` — which runs later and compares
# the pages against that same file — failed with "generated pages drifted from data/lessons.json"
# for pages nobody had touched. The failure named the wrong test, appeared only when a PR added a
# lesson (i.e. only on the contribution path the repository most needs), and read as an
# instruction to regenerate pages rather than as evidence that the suite edits the checkout.
PUBLISHED_INDEX = REPO / "data" / "lessons.json"
OUTPUT = Path(os.environ.get("MISAKANET_LESSONS_INDEX") or PUBLISHED_INDEX)
# The copy the browser downloads (`docs/` is what Cloudflare Workers Builds publishes). It used to be
# produced only by `cp data/lessons.json docs/data/lessons.json` in the three-hourly `build-feed.yml`,
# so between a regeneration and the next feed run the site served a corpus that disagreed with the
# repository. Measured 2026-09-29: the two files held 426 and 418 lessons for about a day and no check
# noticed — they agreed again only because the 3-hourly job happened to have run. The guarantee now
# comes from the job that owns the corpus: this same generator writes both files, so a daily
# `update-lessons.yml` run cannot land a canonical index without its published copy.
# `tests/test_docs_data_copy.py` pins that (both the copy and the comparison), and
# `scripts/check_docs_data_copy.py` is the standalone gate the audit job runs.
DOCS_INDEX = REPO / "docs" / "data" / "lessons.json"
INDEXED_DIRS = ("core", "contrib")
# Non-lesson markdown that must never be indexed (mirrors sync_lessons_to_d1.py).
EXCLUDED = {"README.md", "index.md", "TEMPLATE.md", "CONTRIBUTING.md"}

# The optional structured fields (#1783). MUST stay in lockstep with
# `PLAIN_FIELD_KEYS` in workers/register-proxy-sw.js — that array is the contract
# for what the search projection can carry, and this tuple is the only thing that
# puts the values where the projection can read them.
#
# WHY THIS EXISTS: the D1 path gets these three from the row's `frontmatter`
# column, so they arrived there and nowhere else. The GitHub/KV fallback reads
# `data/lessons.json` (register-proxy-sw.js: loadLessons → fetchFromGitHub) and
# applies no lift at all, so the only thing the projection can see is a
# *top-level key on the index entry* — and the generator never wrote one. The
# symptom was invisible: `evidence_level` works on that path purely because the
# generator does emit it top-level (411/411), and the fallback code beside the
# plain fields (`frontmatterField(lesson.frontmatter, …)`) cannot rescue them
# because no index entry has a `frontmatter` key. docs/maintainer/lesson-fields.md
# documented this gap; this closes it.
PLAIN_FIELD_KEYS = ("summary_plain", "trigger", "verify")


# ── writing the corpus ────────────────────────────────────────────────────────
#
# Every write below replaces a *published* file: the 1.4 MB authoritative index and the two copies
# Cloudflare Workers Builds serves from `docs/`. `Path.write_text` / `Path.write_bytes` open the
# destination with O_TRUNC, so the file a reader is using is already gone by the time the first byte
# is written — a `kill -9`, a full disk or any exception between open and close leaves
# `data/lessons.json` half a JSON document, and the next thing to read it is the site's search page or
# `scripts/check_docs_data_copy.py`. Measured 2026-10-07 in this repository, on a different file: an
# unrelated edit opened a 255-line document with `open(path, "wb")` and raised before writing, which
# truncated it to zero bytes; only git had a copy.
#
# So: write a sibling temp file, then `os.replace`. The rename is atomic within a filesystem, which
# is the whole guarantee — a reader sees either the old bytes or the new ones, never a prefix. The
# temp file must be a *sibling* for that to hold, which is also why this is not `NamedTemporaryFile`
# in the system temp dir (which is very often a different filesystem, where `os.replace` raises
# EXDEV instead of renaming).
#
# This is the same pattern as `misakanet/profile.py::_save`, the repository's other JSON writer that
# must not leave a half-written file; two details that file does not need and this one does, because
# the destination is tracked and world-readable rather than a private per-machine file: the temp
# file's 0600 mode is copied onto the destination, and the directory is fsynced as well as the file.


def fsync_dir(directory: Path) -> None:
    """Flush a directory entry so a finished rename survives a power loss.

    `os.replace` is atomic for readers the instant it returns, but the new *name* is only durable
    once the directory itself is on disk — fsyncing the file's bytes is not enough. Best-effort:
    Windows/WSL mounts and some network filesystems refuse to open or fsync a directory (EACCES /
    EINVAL / ENOTSUP), and the atomicity guarantee above does not depend on this call, so a refusal
    is ignored rather than turned into a failed corpus regeneration on a platform that cannot satisfy
    it. The guarantee deliberately not made is "survives power loss", not "is never half-written".
    """
    try:
        fd = os.open(str(directory), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def atomic_write(target: Path, payload: bytes) -> None:
    """Replace `target` with `payload` in one step. Returns nothing; raises on failure.

    The failure mode this exists for is a *partial* destination, so the temp file is removed on any
    way out that is not the rename (`BaseException`, not `Exception`: a KeyboardInterrupt between
    the write and the rename must not leave the debris either).
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    # mkstemp creates 0600; a tracked file that is rewritten must not silently become private.
    mode = target.stat().st_mode & 0o777 if target.exists() else None
    fd, tmp_name = tempfile.mkstemp(
        dir=str(target.parent),
        prefix=f".{target.name}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        if mode is not None:
            os.chmod(tmp_name, mode)
        os.replace(tmp_name, str(target))
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    fsync_dir(target.parent)


def plain_fields(meta: dict) -> dict:
    """The three structured fields, or `{}` when a lesson carries none.

    Mirrors `plainFields()` in workers/register-proxy-sw.js: a *usable* value is a
    non-empty string, and anything else — missing, "", a number, the nested
    objects legacy frontmatter carries — counts as absent. Emitting nothing for
    such a lesson is what keeps the worker's byte-identity guarantee ("a lesson
    without these fields answers exactly as it did before") structural rather
    than a promise.
    """
    out = {}
    for key in PLAIN_FIELD_KEYS:
        value = meta.get(key)
        if isinstance(value, str) and value.strip():
            out[key] = value.strip()
    return out


def parse_frontmatter(text: str) -> dict:
    """Parse lesson frontmatter: JSON first, then YAML fallback.

    Older lessons use JSON frontmatter, some with a trailing YAML-ish
    `provenance:` block (081e64d5) — raw_decode extracts only the leading JSON
    object. Newer lessons (2026-08+) use YAML frontmatter, which the public
    index now trusts too (build_worker_index.py already does). Falls back to
    {} when there is no frontmatter block, or when the block parses as neither
    format.

    A non-JSON frontmatter block with no PyYAML available is a hard error, not
    a fallback: returning {} here silently rewrote every YAML lesson's title to
    its file stem and its domain to the parent directory name in
    data/lessons.json (CI installed no dependencies, so `import yaml` raised
    ImportError and `except Exception: pass` swallowed it).
    """
    if not text.startswith("---\n") and not text.startswith("---"):
        return {}
    end = text.find("\n---", 4)
    if end == -1:
        return {}
    raw = text[4:end].strip()
    if raw.startswith("{"):
        try:
            return json.JSONDecoder().raw_decode(raw)[0]
        except (json.JSONDecodeError, ValueError):
            pass
    # YAML fallback — import lazily so JSON-frontmatter lessons still parse
    # without pyyaml, but fail loudly when YAML is what we actually need.
    try:
        import yaml
    except ImportError:
        raise RuntimeError(
            "PyYAML is required to parse YAML frontmatter (pip install -r requirements.txt); "
            "refusing to fall back to slug/dir metadata"
        ) from None
    try:
        fm = yaml.safe_load(raw)
        if isinstance(fm, dict):
            return fm
    except Exception:
        pass
    return {}


def get_preview(content: str, max_chars: int = 2400) -> str:
    """Extract lesson body after frontmatter for inline preview."""
    lines = content.split('\n')
    start = 0
    if lines and lines[0].strip() == '---':
        for i in range(1, len(lines)):
            if lines[i].strip() == '---':
                start = i + 1
                break
    body = '\n'.join(lines[start:]).strip()
    if len(body) > max_chars:
        body = body[:max_chars] + '\n\n[clipped]'
    return body


def strip_html_comments(text: str) -> str:
    """Drop well-formed ``<!-- ... -->`` blocks before any prose extraction."""
    return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)


def get_summary(content: str, max_chars: int = 160) -> str:
    """Extract first meaningful sentence after frontmatter."""
    lines = strip_html_comments(content).split('\n')
    start = 0
    if lines and lines[0].strip() == '---':
        for i in range(1, len(lines)):
            if lines[i].strip() == '---':
                start = i + 1
                break
    for line in lines[start:]:
        line = line.strip()
        if not line:
            continue
        # Comment fragments. The well-formed `<!-- provenance: ... -->` block is
        # removed above, but 19 imported lessons also carry a *stray* `<!--`
        # opener with no closing `-->`, which comments out their entire body when
        # rendered — get_summary() returned the literal `<!--` as the public
        # summary, and the site/generated pages showed it (found 2026-09-12 while
        # regenerating the lesson pages; the stray lines are removed too).
        if line.startswith("<!--") or line.endswith("-->"):
            continue
        if line == "---":
            continue
        if line.startswith("---{") and line.endswith("}---"):
            continue
        if line == "{":
            continue
        if line.startswith("{") and line.endswith("}"):
            continue
        if line.startswith('#') or line.startswith('- **'):
            continue
        if line.startswith("domain:") or line.startswith("title:") or line.startswith("verification:"):
            continue
        if line:
            return line[:max_chars] + ('…' if len(line) > max_chars else '')
    return ''


# Public lesson counts are kept in lockstep by scripts/sync_lesson_count.py,
# which owns the registry of surfaces that must carry the literal number — since
# 2026-09-28 that is three files (docs/index.html's meta/no-JS copy and the two
# llms.txt) plus the docs/_lessons_count.txt mirror. Everything else points at the
# number (shields badge over data/badges/lessons.json, or the source named in prose).
# Do not hand-edit a count there.


def refresh_lesson_count_markers(count: int) -> None:
    """Keep every documented lesson count derived from the canonical index.

    (2026-09-12) This used to substitute a literal for each
    ``{{LESSONS_COUNT}}`` placeholder — which *consumed* the placeholder, so the
    second run matched nothing and every count froze at its first
    materialization (README stayed at 310+, ARCHITECTURE at 358+, the site's
    ``<meta description>`` at 435, …). The registry in
    ``scripts/sync_lesson_count.py`` re-matches a numeric group on every run
    (idempotent) and treats a reworded sentence as a hard error instead of a
    silent skip. It also writes docs/_lessons_count.txt and normalises the trust
    vocabulary ("verified" → "indexed", see docs/trust-semantics.md).

    Raises SystemExit(1) when a managed surface can no longer be refreshed, so
    the daily workflow fails loudly rather than committing a half-synced tree.
    """
    from scripts.sync_lesson_count import sync_all

    changes, errors = sync_all(count)
    for change in changes:
        print(f"OK count: {change}")
    if errors:
        print("lesson-count SSOT could not be refreshed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        raise SystemExit(1)


def mirror_published_index(source: Path | None = None) -> bool:
    """Copy the canonical index onto the site's copy. Returns True when the copy moved.

    WHY (2026-09-29): the two files are one corpus shipped twice, and the copy existed only as a `cp`
    in the three-hourly `build-feed.yml` — so a regeneration of `data/lessons.json` left
    `docs/data/lessons.json` serving the previous corpus until the next feed run. Measured 2026-09-29:
    426 vs 418 for about a day, with the site internally inconsistent and no check complaining. Writing
    both from the generator means the guarantee comes from the job that owns the corpus, not from a
    schedule that happens to run later.

    Byte-compares before writing (and skips the write when they already match) so a no-op regeneration
    produces no diff: `land_change.py` opens a pull request for any change in the tree, so a needless
    write here would manufacture a daily commit for nothing.
    """
    source = Path(source) if source is not None else PUBLISHED_INDEX
    payload = source.read_bytes()
    if DOCS_INDEX.exists() and DOCS_INDEX.read_bytes() == payload:
        print(f"OK site copy already current: {DOCS_INDEX}")
        return False
    DOCS_INDEX.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(DOCS_INDEX, payload)
    print(f"OK site copy refreshed: {DOCS_INDEX} ({len(payload)} bytes)")
    return True


# The fields the site's pages read from the corpus, derived from their own code rather than guessed —
# `tests/test_docs_data_copy.py::test_the_projection_carries_every_field_the_pages_read` re-derives this set
# from `docs/index.html` and `docs/search/index.html` and fails when a page starts reading a field that is
# not here. That rule exists because the first version of this projection was built from the *search*
# scoring code alone and silently broke the homepage's stats card: `evidence_level` was missing, so the
# "evidence-backed lessons" counter computed 0 (it should be E3+E4 = 26), and a `const` ordering bug in the
# same change meant the page loaded no corpus at all (both counters stayed "—").
#
# `preview` is deliberately **not** here even though the search page's preview panel used to read it from the
# corpus: it is ~2.1 KB of body text per lesson (median 2088 chars), i.e. 1.09 MB of the corpus's 1.32 MB —
# shipping it to run a search over a few short fields was the whole cost. That panel fetches the one lesson
# it needs, on demand.
LITE_FIELDS = ("id", "title", "summary", "domain", "tags", "evidence_level", "url")


def build_lite_projection(rows: list) -> list:
    """The type-ahead/search projection of the corpus: the fields the browser reads, and nothing else."""
    return [{key: row.get(key) for key in LITE_FIELDS} for row in rows]


def mirror_lite_projection(source: Path | None = None) -> bool:
    """Write the browser projection beside the site's corpus copy. Returns True when it moved.

    WHY (2026-09-30): both pages downloaded the whole corpus (1.27 MB raw, 418 KB transferred) to run a
    local search over six fields. The projection is ~5-7× smaller, which removes the largest object the
    site makes a visitor fetch — and it is written *here*, in the job that owns the corpus, so it cannot
    drift from it (`scripts/check_docs_data_copy.py` asserts the id sets match).

    Same byte-compare rule as `mirror_published_index`: a no-op regeneration must not manufacture a diff,
    because `land_change.py` opens a pull request for any change in the tree.
    """
    source = Path(source) if source is not None else PUBLISHED_INDEX
    # Derived from `DOCS_INDEX` at call time, deliberately **not** a module constant: #2459's redirect
    # contract is that a test (or a redirected run) moves `DOCS_INDEX` and every write follows it. A
    # constant evaluated at import time does not follow — the first version of this function wrote a
    # fixture corpus into the real `docs/data/lessons-lite.json` during the test suite, which is the
    # "a write that no redirection covers" failure that whole gate exists to prevent.
    target = DOCS_INDEX.with_name("lessons-lite.json")
    rows = json.loads(source.read_text(encoding="utf-8"))
    payload = json.dumps(build_lite_projection(rows), ensure_ascii=False, separators=(",", ":")).encode()
    if target.exists() and target.read_bytes() == payload:
        print(f"OK browser projection already current: {target}")
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(target, payload)
    print(f"OK browser projection refreshed: {target} ({len(payload)} bytes)")
    return True


def main():
    # Audit T2.2/T2.5 "图书馆" policy: index every lessons/ subdir with real
    # content, deduplicated by stem (canonical_lessons: core > contrib >
    # other dirs), so mirror/translation copies (e.g. en/) don't show up
    # twice. INDEXED_DIRS stays as the historical fallback/legacy reference.
    from misakanet.lesson_index import EXCLUDED_LESSON_FILES, canonical_lessons

    entries = []
    # canonical_lessons returns dir-major canonical order (core, contrib,
    # then the rest alphabetically) — keeps the historic prefix stable.
    for f in canonical_lessons(LESSONS_DIR):
        dir_name = f.parent.name
        if f.name.startswith(".") or f.name in EXCLUDED_LESSON_FILES:
            continue
        content = f.read_text(encoding="utf-8", errors="replace")
        meta = parse_frontmatter(content)
        # YAML frontmatter may yield non-JSON types (date, etc.) — normalize
        meta = {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in meta.items()}
        title = meta.get("title", f.stem)
        domain = meta.get("domain", dir_name)
        if isinstance(domain, list):
            domain = domain[0] if domain else dir_name
        tags = meta.get("tags", [])
        if not isinstance(tags, list):
            tags = [tags] if tags else []
        status = meta.get("status", "active")
        summary = meta.get("summary", "") or get_summary(content)
        preview = get_preview(content)
        rel_path = f.relative_to(LESSONS_DIR).as_posix()
        # Check for Verification section (badge-only verified semantics)
        verified = bool(re.search(r"##\s*(Verify|Verification)", content, re.IGNORECASE))
        # Evidence level (#786): frontmatter wins when present; legacy
        # lessons that predate the field get a content-inferred level
        # (same inference the intake pipeline uses — queue_lesson.py).
        # The public index carries it so search pages can show E3+/E4
        # counts instead of composite averages.
        raw_level = meta.get("evidence_level")
        if raw_level is not None:
            evidence_level = evidence_of(meta)
            evidence_source = "frontmatter"
        else:
            from scripts.infer_evidence_level import infer_evidence_level
            evidence_level, _ = infer_evidence_level(content)
            evidence_source = "inferred"
        confidence = meta.get("confidence", 0.5)
        if not isinstance(confidence, (int, float)):
            confidence = 0.5
        entries.append({
            "id": f.stem,
            "title": title,
            "domain": domain,
            "tags": tags,
            "summary": summary,
            "preview": preview,
            # The three optional structured fields (#1783), top-level so the
            # GitHub/KV fallback can serve them. NOTE: singular `trigger` — the
            # plural `triggers` below is a different, older field (the structured
            # intent object from schemas/lesson.json); do not conflate them.
            **plain_fields(meta),
            "url": f"lessons/{rel_path}",
            "created": meta.get("created", ""),
            "updated": meta.get("updated", ""),
            "triggers": meta.get("triggers", None),
            "validity_period_days": 365,
            "environment_version": "",
            "confidence": confidence,
            "status": status,
            "evidence_refs": meta.get("evidence_refs", []),
                "supersedes": meta.get("supersedes", ""),
            "verified": verified,
            "evidence_level": evidence_level,
            "evidence_source": evidence_source,
            # trust = quality(confidence) scaled by evidence (E0 keeps 70%,
            # E4 keeps 100%) — shown on search pages instead of a composite.
            "trust_score": trust_score(confidence, evidence_level),
            "contributor": meta.get("contributor", ""),  # Issue #1342
        })

    atomic_write(OUTPUT, (json.dumps(entries, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(f"OK lessons.json updated: {len(entries)} entries")
    # The count surfaces say "N indexed failure-recovery lessons about `data/lessons.json`". Refreshing
    # them from a run that wrote the index somewhere else would publish a number the published index
    # does not have — and in tests it rewrote 20+ tracked files for a fixture nobody asked for.
    if OUTPUT == PUBLISHED_INDEX:
        refresh_lesson_count_markers(len(entries))
        # Same reasoning one file over: the site copy describes the published index, so a run that
        # wrote the index somewhere else must not touch it (a redirected test run would otherwise
        # rewrite `docs/data/lessons.json` with fixture data and leave the checkout inconsistent).
        mirror_published_index()
        # …and the projection the browser actually searches over, so it cannot drift from the corpus it
        # is a view of (2026-09-30).
        mirror_lite_projection()
    else:
        print(f"count markers not refreshed: this run wrote {OUTPUT}, not {PUBLISHED_INDEX}")
        print(f"site copy not refreshed: this run wrote {OUTPUT}, not {PUBLISHED_INDEX}")
        print(f"browser projection not refreshed: this run wrote {OUTPUT}, not {PUBLISHED_INDEX}")


if __name__ == "__main__":
    main()
