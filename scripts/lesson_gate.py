#!/usr/bin/env python3
"""Lesson Quality Gate — structural validation for new lesson contributions (issue #889).

Validates lesson Markdown files against the quality gate checklist:
  - Required frontmatter fields: title, domain, tags, status, evidence_level
  - Minimum content length: 100 chars (excluding frontmatter)
  - No duplicate titles (against all existing lessons)
  - Domain must be in the allowed list (docs/domains/ + lessons/core|contrib|en)
  - Tags validated for format (1-10 unique strings, min 2 chars)
  - status ∈ {published, draft, archived}; evidence_level ∈ {E0..E4}

Usage:
    python3 scripts/lesson_gate.py lessons/contrib/foo.md          # validate one
    python3 scripts/lesson_gate.py lessons/a.md lessons/b.md       # validate many
    python3 scripts/lesson_gate.py --all                           # validate all lessons
    python3 scripts/lesson_gate.py --json <file>                   # JSON report

Exit code: 0 = all pass, 1 = any file failed.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LESSONS_DIR = REPO / "lessons"
DOCS_DOMAINS = REPO / "docs" / "domains"

VALID_STATUS = {"published", "draft", "archived"}
VALID_EVIDENCE = {"E0", "E1", "E2", "E3", "E4"}
MIN_CONTENT_CHARS = 100
MIN_TITLE_CHARS = 4
MAX_TITLE_CHARS = 120
MIN_TAG_CHARS = 2
MAX_TAGS = 10

# Lesson directories that count as real contributions (not templates/archive).
ACTIVE_LESSON_SUBDIRS = {"core", "contrib", "en"}

FM_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)


# ── Parsing ─────────────────────────────────────────────────────────
def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Return (frontmatter_dict, content_without_frontmatter).

    Supports JSON (legacy) and YAML (2026-08+ convention) frontmatter, plus
    the JSON+provenance legacy quirk via raw_decode.
    """
    m = FM_RE.match(text)
    if not m:
        return {}, text
    raw = m.group(1).strip()
    try:
        fm = json.JSONDecoder().raw_decode(raw)[0]
        if isinstance(fm, dict):
            return fm, text[m.end():]
    except json.JSONDecodeError:
        pass
    try:
        import yaml
        fm = yaml.safe_load(raw)
        if isinstance(fm, dict):
            return fm, text[m.end():]
    except Exception:
        pass
    return {}, text[m.end():]


# ── Field validators ────────────────────────────────────────────────
def validate_required(fm: dict) -> list[str]:
    errors = []
    for field in ("title", "domain", "tags", "status"):
        if field not in fm or fm[field] in (None, ""):
            errors.append(f"missing required field: {field}")
    # Accept either top-level evidence_level or provenance.evidence
    has_evidence = (
        fm.get("evidence_level") not in (None, "")
        or (isinstance(fm.get("provenance"), dict) and fm["provenance"].get("evidence") not in (None, ""))
    )
    if not has_evidence:
        errors.append("missing required field: evidence_level (or provenance.evidence)")
    return errors


def validate_title(title) -> list[str]:
    if not isinstance(title, str):
        return ["title must be a string"]
    errors = []
    if len(title) < MIN_TITLE_CHARS:
        errors.append(f"title too short ({len(title)} < {MIN_TITLE_CHARS} chars)")
    if len(title) > MAX_TITLE_CHARS:
        errors.append(f"title too long ({len(title)} > {MAX_TITLE_CHARS} chars)")
    return errors


def validate_tags(tags) -> list[str]:
    if not isinstance(tags, list):
        return ["tags must be a list"]
    if len(tags) < 1:
        return ["tags must have at least 1 tag"]
    if len(tags) > MAX_TAGS:
        return [f"tags exceed {MAX_TAGS} tags"]
    if len(set(tags)) != len(tags):
        return ["tags must be unique"]
    short = [t for t in tags if not (isinstance(t, str) and len(t) >= MIN_TAG_CHARS)]
    if short:
        return [f"tags must be strings of >= {MIN_TAG_CHARS} chars: {short[:3]}"]
    return []


def validate_status(status) -> list[str]:
    if status not in VALID_STATUS:
        return [f"status must be one of {sorted(VALID_STATUS)}, got {status!r}"]
    return []


def validate_evidence(evidence_level) -> list[str]:
    if evidence_level not in VALID_EVIDENCE:
        return [f"evidence_level must be one of {sorted(VALID_EVIDENCE)}, got {evidence_level!r}"]
    return []


def validate_content_len(content: str) -> bool:
    return len(content.strip()) >= MIN_CONTENT_CHARS


# ── Repo-level checks ───────────────────────────────────────────────
def allowed_domains(repo: Path = REPO) -> set[str]:
    """Allowed domains = docs/domains/* + domains used in active lesson dirs."""
    domains = set()
    if DOCS_DOMAINS.is_dir():
        for f in DOCS_DOMAINS.glob("*.md"):
            domains.add(f.stem.lower())
    for sub in ACTIVE_LESSON_SUBDIRS:
        d = repo / "lessons" / sub
        if not d.is_dir():
            continue
        for f in d.rglob("*.md"):
            try:
                fm, _ = parse_frontmatter(f.read_text(encoding="utf-8", errors="ignore"))
            except Exception:
                continue
            dom = fm.get("domain")
            if isinstance(dom, str) and dom:
                domains.add(dom.lower())
    return domains


def _iter_active_lessons(repo: Path = REPO):
    for sub in ACTIVE_LESSON_SUBDIRS:
        d = repo / "lessons" / sub
        if d.is_dir():
            yield from d.rglob("*.md")


def _iter_lessons_from(repo: Path, dirs: tuple[str, ...] | None = None):
    """Yield lesson files. `dirs` overrides ACTIVE_LESSON_SUBDIRS; repo is
    always the root that contains a lessons/ directory (tests build a
    tmp_path/lessons tree and pass tmp_path as repo)."""
    subs = dirs if dirs is not None else ACTIVE_LESSON_SUBDIRS
    base = repo / "lessons"
    for sub in subs:
        d = base / sub
        if d.is_dir():
            yield from d.rglob("*.md")


def find_duplicate_title(title: str, repo: Path = REPO, exclude_file: Path | None = None) -> bool:
    if not title:
        return False
    norm = title.strip().lower()
    # Determine which lesson subdirectory the file being checked belongs to,
    # so translations (en/) don't flag originals (core/contrib) as duplicates.
    exclude_dir = None
    if exclude_file is not None:
        try:
            rel = Path(exclude_file).resolve().relative_to(repo / "lessons")
            exclude_dir = rel.parts[0]  # e.g. "core", "contrib", "en"
        except (ValueError, IndexError):
            pass
    for f in _iter_active_lessons(repo):
        if exclude_file is not None and f.resolve() == Path(exclude_file).resolve():
            continue
        # Skip files in a different lesson subdirectory (avoids cross-language
        # false positives between core/contrib and en translations).
        if exclude_dir is not None:
            try:
                f_rel = f.resolve().relative_to(repo / "lessons")
                if f_rel.parts[0] != exclude_dir:
                    continue
            except (ValueError, IndexError):
                pass
        try:
            fm, _ = parse_frontmatter(f.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            continue
        if isinstance(fm.get("title"), str) and fm["title"].strip().lower() == norm:
            return True
    return False


# ── Content-similarity & fake-verification detection (2026-08-30) ──
# Near-duplicate lessons (same problem, copy-pasted sections) slip past the
# exact-title check. We tokenize the body (after frontmatter) and report
# Jaccard similarity against every other active lesson. Translations are
# excluded by comparing the `language` frontmatter field.
FAKE_VERIFICATION_RE = re.compile(
    r"grep\s+-[a-z]*i?[a-z]*\s+.*\|\s*wc\s+-l"      # grep ... | wc -l
    r"|echo\s+[^\n]*\|\s*wc\s+-l"                    # echo ... | wc -l
    r"|echo\s+[^\n]*verified"                        # echo ... verified
    r"|\bwc\s+-l\s+[^\n]*"                           # bare wc -l <file>
    r"|grep\s+-[a-z]*\s+[^\n]*\s*>\s*/dev/null",     # grep ... > /dev/null
    re.IGNORECASE,
)
# A Verification section that only runs shell-fragment grep/echo/counts and
# never references the fix itself is a placeholder (review finding P1/2026-08-28).
# NOTE: bare `grep -i "Signed-off-by"` IS a legitimate check — only grep piped
# to wc/count or echo-verified stubs are placeholders.
FAKE_VERIFICATION_HINTS = ("echo Lesson", "echo Feishu", "echo Verified",
                           "wc -l", "grep -c", "git status --short")


def _content_words(text: str) -> set[str]:
    """Tokenize lesson body (after frontmatter) into a word set."""
    _, content = parse_frontmatter(text)
    words = set(re.findall(r"[a-zA-Z]{3,}|[\u4e00-\u9fff]{2,}", content.lower()))
    return words


def _section_signature(text: str) -> list[str]:
    """Structural fingerprint: sequence of headings + code-block fence
    markers. Catches 'same skeleton, rewritten wording' duplicates that
    word-level Jaccard misses (e.g. git-push-without-shell-agent vs
    git-push-yolo-task-codewhale)."""
    _, content = parse_frontmatter(text)
    sig = []
    for line in content.splitlines():
        s = line.strip()
        if s.startswith("##") or s.startswith("###"):
            sig.append("h:" + re.sub(r"[^a-z\u4e00-\u9fff]", "", s.lower()))
        elif s.startswith("```"):
            sig.append("fence")
    return sig


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _sequence_sim(a: list[str], b: list[str]) -> float:
    """Longest-common-subsequence ratio over section signatures."""
    if not a or not b:
        return 0.0
    n, m = len(a), len(b)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if a[i - 1] == b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    lcs = dp[n][m]
    return lcs / max(n, m)


_LESSON_INDEX_CACHE: dict[Path, tuple[dict, set[str], list[str]]] = {}


def _index_lesson(path: Path) -> tuple[dict, set[str], list[str]]:
    """Cached (frontmatter, word-set, section-signature) for a lesson file."""
    key = path.resolve()
    if key not in _LESSON_INDEX_CACHE:
        text = path.read_text(encoding="utf-8", errors="ignore")
        fm, _ = parse_frontmatter(text)
        _LESSON_INDEX_CACHE[key] = (fm, _content_words(text), _section_signature(text))
    return _LESSON_INDEX_CACHE[key]


def similarity_to_existing(
    path: Path,
    repo: Path = REPO,
    threshold: float = 0.55,
    dirs: tuple[str, ...] | None = None,
) -> list[tuple[str, str, float]]:
    """Find active lessons whose body is near-duplicate of `path`.

    Returns [(other_path_str, other_language, similarity)] sorted by
    similarity desc. Similarity = max(word-Jaccard, section-sequence sim).
    Translations (both files explicitly declare different languages) and the
    file itself are excluded. `dirs` overrides the scanned subdirectories
    (used by tests with custom layouts).
    """
    try:
        fm, my_words, my_sig = _index_lesson(path)
    except OSError:
        return []
    if len(my_words) < 20:  # too short to judge similarity reliably
        return []

    out = []
    for f in _iter_lessons_from(repo, dirs):
        if f.resolve() == Path(path).resolve():
            continue
        try:
            ofm, other_words, other_sig = _index_lesson(f)
        except Exception:
            continue
        # Only skip when BOTH files explicitly declare different languages.
        # An unset language defaults to the content itself (many legacy
        # lessons omit `language`), so it must still be compared.
        other_lang = (ofm.get("language") or "").lower()
        my_lang_decl = (fm.get("language") or "").lower()
        if my_lang_decl and other_lang and my_lang_decl != other_lang:
            continue  # genuine translation pair
        word_sim = _jaccard(my_words, other_words)
        # Fast path: structure LCS is O(n*m) — only compute it when word
        # similarity is already non-trivial (avoids O(n²) blowup on --all).
        sim = word_sim
        if word_sim >= 0.35:
            seq_sim = _sequence_sim(my_sig, other_sig)
            sim = max(word_sim, seq_sim)
        if sim >= threshold:
            out.append((str(f), other_lang or my_lang_decl or "en", sim))
    out.sort(key=lambda x: x[2], reverse=True)
    return out[:5]  # cap at 5 suggestions


def detect_fake_verification(text: str) -> str | None:
    """Return a short reason if the Verification section looks like a
    placeholder (does not actually verify the documented fix)."""
    _, content = parse_frontmatter(text)
    m = re.search(r"^##\s*(?:Verification|验证)", content, re.M | re.I)
    if not m:
        return None
    section = content[m.end():]
    section = section.split("\n## ")[0]  # up to next heading
    if not section.strip():
        return None
    if FAKE_VERIFICATION_RE.search(section):
        return "Verification uses grep/echo/wc placeholder, not a real fix check"
    for hint in FAKE_VERIFICATION_HINTS:
        if hint.lower() in section.lower():
            return f"Verification looks like a placeholder (contains {hint!r})"
    return None


# ── File validation ─────────────────────────────────────────────────
def validate_file(path: Path, repo: Path = REPO, dirs: tuple[str, ...] | None = None) -> list[str]:
    """Return error strings. Warnings are prefixed with '[warn]' and do not
    fail the gate (they surface for maintainer review only). `dirs` overrides
    the scanned subdirectories (used by tests with custom layouts)."""
    errors = []
    try:
        text = Path(path).read_text(encoding="utf-8", errors="ignore")
    except OSError as e:
        return [f"cannot read {path}: {e}"]

    fm, content = parse_frontmatter(text)
    errors += validate_required(fm)
    if fm:
        errors += validate_title(fm.get("title"))
        errors += validate_tags(fm.get("tags")) if "tags" in fm else []
        errors += validate_status(fm.get("status")) if "status" in fm else []
        errors += validate_evidence(fm.get("evidence_level")) if "evidence_level" in fm else []

    if not validate_content_len(content):
        errors.append(f"content too short (< {MIN_CONTENT_CHARS} chars excluding frontmatter)")

    if fm and fm.get("title"):
        domain = fm.get("domain")
        if isinstance(domain, str) and domain:
            if domain.lower() not in allowed_domains(repo):
                errors.append(f"domain {domain!r} not in allowed list (docs/domains/ or existing lessons)")
        if find_duplicate_title(fm["title"], repo, exclude_file=path):
            errors.append(f"duplicate title: {fm['title']!r}")

    # Near-duplicate content (same language, Jaccard >= 0.55): real duplicates
    # that a title check misses. Reported as a gate error so PRs don't merge
    # copy-pasted lessons (2026-08-30).
    if fm and fm.get("title"):
        for other, _lang, sim in similarity_to_existing(path, repo, dirs=dirs):
            errors.append(
                f"near-duplicate content: {sim:.0%} similar to {other}"
                f" (merge or differentiate; translations are auto-excluded)"
            )

    # Fake verification placeholder: [warn] so existing legacy lessons don't
    # break the gate, but new contributions get flagged for maintainer review.
    if fm and fm.get("title"):
        fake = detect_fake_verification(text)
        if fake:
            errors.append(f"[warn] {fake}")

    return errors


# ── CLI ─────────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv or "--help" in argv or "-h" in argv:
        print(__doc__)
        return 0

    json_mode = "--json" in argv
    argv = [a for a in argv if a != "--json"]

    if "--all" in argv:
        files = sorted(_iter_active_lessons())
    else:
        files = [Path(a) for a in argv]

    failures = 0
    warnings = 0
    report = {}
    for f in files:
        all_issues = validate_file(f)
        errors = [e for e in all_issues if not e.startswith("[warn]")]
        warns = [e for e in all_issues if e.startswith("[warn]")]
        report[str(f)] = all_issues
        if errors:
            failures += 1
        elif warns:
            warnings += 1

    if json_mode:
        print(json.dumps({"files": report, "failures": failures, "warnings": warnings}, indent=2))
    else:
        for f, issues in report.items():
            if issues:
                for e in issues:
                    tag = "WARN" if e.startswith("[warn]") else "FAIL"
                    print(f"{tag} {f}")
                    print(f"  - {e.removeprefix('[warn] ')}")
        if failures or warnings:
            print(f"\n{len(files)} file(s) checked, {failures} failed, {warnings} with warnings.")
        else:
            print(f"OK: {len(files)} file(s) passed the lesson quality gate.")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
