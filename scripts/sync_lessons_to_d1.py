#!/usr/bin/env python3
"""
Sync MisakaNet lessons (repo source-of-truth) into Cloudflare D1 (PRD ④).

Pipeline: lessons/*.md  →  parse  →  upsert SQL  →  wrangler d1 execute

Design:
  - The Git repo stays the authoritative source (history/review/contribution);
    D1 is the serving layer (HTTP/MCP direct query, no clone required).
  - Idempotent: upsert by lesson id; re-runs never duplicate.
  - Emits `INSERT ... ON CONFLICT(id) DO UPDATE` statements so it works with
    `wrangler d1 execute <db> --remote --file=-`.

Usage:
    # 1. Create the database once:
    #    wrangler d1 create misakanet-db
    #    (then put database_id into workers/wrangler.toml)

    # 2. Apply schema once:
    #    wrangler d1 execute misakanet-db --remote --file=workers/d1/schema.sql

    # 3. Sync lessons (dry run first, then execute):
    #    python3 scripts/sync_lessons_to_d1.py --db misakanet-db --dry-run
    #    python3 scripts/sync_lessons_to_d1.py --db misakanet-db --execute
    #    # or pipe: python3 scripts/sync_lessons_to_d1.py --sql | wrangler d1 execute misakanet-db --remote --file=-

    # 4. Reconcile (verify repo == D1 via checksums):
    #    python3 scripts/sync_lessons_to_d1.py --db misakanet-db --reconcile

Auth: CLOUDFLARE_API_TOKEN + CLOUDFLARE_ACCOUNT_ID env (CI), or wrangler login (local).
"""
import argparse
import hashlib
import json
import os
import random
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))  # audit T2.5: import misakanet.lesson_index
LESSONS_DIR = REPO / "lessons"
INDEXED_DIRS = ("core", "contrib")
EXCLUDED = {"README.md", "index.md", "TEMPLATE.md", "CONTRIBUTING.md"}
CF_ACCOUNT = "6b92325b505f2b76aec49e9fe4195d31"
MC = str(REPO / ".tools" / "bin" / "mcporter")
CFG = str(REPO / ".tools" / "mcporter.json")

SECTION_ALIASES = {
    "problem": [
        "problem", "问题", "描述",
        "problema", "समस्या", "masalah", "проблема", "sorun", "vấn đề",
    ],
    "root_cause": [
        "root cause", "根因", "原因", "根因分析",
        "causa", "causa raíz", "causa raiz", "коренная причина", "первопричина", "причина",
        "मूल कारण", "akar penyebab", "penyebab", "kök neden", "neden",
        "nguyên nhân gốc rễ", "nguyên nhân",
    ],
    "solution": [
        "solution", "fix", "修复", "解法", "方案", "正确做法", "修复方案",
        "solução", "solucao", "solución", "solucion", "решение", "समाधान", "solusi",
        "çözüm", "cozum", "giải pháp",
    ],
    "verification": [
        "verification", "verify", "验证", "验证方式",
        "verificação", "verificacao", "verificación", "verificacion",
        "проверка", "सत्यापन", "verifikasi", "doğrulama", "dogrulama", "xác minh",
    ],
}


#: Import failures that are worth a second attempt — signs the import died **in transit** rather than
#: being rejected. Deliberately an allowlist, because every attempt re-uploads the corpus and re-opens
#: the window where D1 is unavailable to serve queries: retrying a deterministic failure (a bad
#: credential, a SQL syntax error, an etag mismatch) triples the damage *and* delays the red light.
#: Anything not matched here fails the job on the first attempt, with the tool's own output.
#:
#: The first entry is the string from the incident this list exists for: run 36950668957, 2026-10-02
#: 01:26:42, where `automation` went red on an import whose data had already landed. Why the D1 side
#: answered `success: false` is not observable from outside Cloudflare, so this treats it as the
#: transient control-plane failure the rest of the evidence says it was.
TRANSIENT_IMPORT_MARKERS = (
    "Not currently importing anything.",
    "D1 reset before execute completed!",
    "fetch failed",
    "ECONNRESET",
    "ETIMEDOUT",
    # The three upload errors wrangler raises while sending the SQL literally say "Please retry" — the
    # most obviously retryable class there is, since the corpus is re-uploaded on every attempt.
    "Please retry",
    # cfetch renders a non-envelope failure as `Failed to fetch <resource> - <status>: <statusText>;`,
    # so the status and its phrase are separated by a colon. The first version of this list spelled them
    # "502 Bad Gateway" (with a space), which matches nothing wrangler prints — three dead entries, and
    # 500 missing entirely. An independent review measured the attempt counts against these strings.
    " - 500: ",
    " - 502: ",
    " - 503: ",
    " - 504: ",
    # A 5xx carried inside the Cloudflare error *envelope* is a **documented residual gap**: wrangler
    # renders it as `A request to the Cloudflare API (<resource>) failed.` plus the envelope text, and
    # that sentence is identical for deterministic 4xx (403/400/404), so matching it would retry
    # credentials and validation failures too — the opposite of what this allowlist is for. (The first
    # version of this comment claimed wrangler retries 5xx/429 itself on this path; an independent review
    # read the whole D1 chain and showed it does not: `retryOnAPIFailure`, the only consumer of
    # `isRetryable()`, is never called from the D1 execute module.) The cost of the gap is an occasional
    # red run on an envelope 5xx, not a wrong write.
)


#: Three attempts at this bound, plus ~52s of backoff, is ~13 minutes — comfortably inside the
#: job's `timeout-minutes: 45`.
IMPORT_TIMEOUT_SECONDS = 240


def parse_frontmatter(text: str) -> dict:
    """Parse lesson frontmatter: JSON first, then YAML fallback.

    Some lessons append a YAML-ish `provenance:` block after the JSON object
    inside the same frontmatter delimiters; raw_decode extracts only the
    leading JSON object. Newer lessons use plain YAML frontmatter — fall back
    to yaml.safe_load for those (mirrors update_lessons_json.py).

    A non-JSON frontmatter block with no PyYAML available is a hard error, not
    a fallback: returning {} here silently wrote every YAML lesson to D1 with
    its file stem as the title, the parent directory name as the domain and
    empty tags (CI installed no dependencies, so `import yaml` raised
    ImportError and `except Exception: pass` swallowed it).
    """
    if not text.startswith("---"):
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


def split_sections(body: str) -> dict:
    """Extract named sections from a lesson body by heading aliases."""
    out = {k: "" for k in SECTION_ALIASES}
    # Split on any ## heading, keep heading text for matching.
    parts = re.split(r"^##\s+(.+?)\s*$", body, flags=re.M)
    # parts[0] = preamble; then heading, content pairs.
    for i in range(1, len(parts) - 1, 2):
        heading = parts[i].strip().lower()
        content = parts[i + 1].strip()
        for key, aliases in SECTION_ALIASES.items():
            if any(a in heading for a in aliases) and not out[key]:
                out[key] = content[:2000]
    return out


def lesson_checksum(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def parse_lesson(path: Path) -> dict | None:
    text = path.read_text(encoding="utf-8", errors="replace")
    if not text.strip():
        return None
    fm = parse_frontmatter(text)
    # YAML frontmatter may yield non-JSON types (date, etc.) — normalize
    fm = {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in fm.items()}
    # Body = everything after the closing --- of the frontmatter block
    end = text.find("\n---", 4)
    body = text[end + 4:] if end != -1 else text
    sections = split_sections(body)
    title = fm.get("title") or path.stem
    domain = fm.get("domain") or path.parent.name
    if isinstance(domain, list):
        domain = domain[0] if domain else path.parent.name
    tags = fm.get("tags", [])
    if not isinstance(tags, list):
        tags = [tags] if tags else []
    summary = fm.get("summary", "") or re.sub(r"\s+", " ", body).strip()[:200]
    # `evidence_level` (#2080): the served field must carry the same value the published corpus
    # carries, and that value is *derived* — most lessons do not declare it, they earn it from their
    # content (`update_lessons_json.py` does this for `data/lessons.json`, and the API promises the
    # field to every client). Storing the raw frontmatter alone kept nothing for those rows,
    # so the D1 path answered `""` on every hit while the GitHub-snapshot path answered correctly:
    # the trust field looked *provided and blank*, worse than missing. Reuses the same two helpers;
    # there must not be a second implementation of "what level is this lesson".
    from misakanet.evidence import evidence_of  # one derivation of the level, never a second

    if fm.get("evidence_level") is not None:
        evidence_level = evidence_of(fm)
    else:
        from scripts.infer_evidence_level import infer_evidence_level

        evidence_level, _ = infer_evidence_level(body)
    return {
        "id": path.stem,
        "title": title,
        "domain": domain,
        "status": fm.get("status", "published"),
        "language": fm.get("language", "en"),
        "tags": json.dumps(tags, ensure_ascii=False),
        "path": path.relative_to(REPO).as_posix(),
        "problem": sections["problem"],
        "root_cause": sections["root_cause"],
        "solution": sections["solution"],
        "verification": sections["verification"],
        "content_md": body.strip()[:30000],
        "frontmatter": json.dumps({**fm, "evidence_level": evidence_level}, ensure_ascii=False),
        "summary": summary,
        "created": fm.get("created", ""),
        "updated": fm.get("updated", ""),
        "checksum": lesson_checksum(text),
    }


def collect_lessons() -> list[dict]:
    # Audit T2.5: sync the same canonical (deduped) set the local search and
    # public index use, so D1 matches the repo (core + contrib + unique en +
    # user-rescue …), mirrors/translations excluded.
    from misakanet.lesson_index import canonical_lessons

    lessons = []
    for f in canonical_lessons(LESSONS_DIR):
        if f.name.startswith(".") or f.name in EXCLUDED:
            continue
        lesson = parse_lesson(f)
        if lesson:
            lessons.append(lesson)
    return lessons


def upsert_sql(lessons: list[dict]) -> str:
    cols = ["id", "title", "domain", "status", "language", "tags", "path",
            "problem", "root_cause", "solution", "verification", "content_md",
            "frontmatter", "summary", "created", "updated", "checksum", "synced_at"]
    now = "datetime('now')"
    # Both notes in this function go to stderr, never into the SQL. `wrangler d1 execute --file`
    # reports whatever bytes follow the last complete statement as a "leftover buffer", and a trailing
    # comment is exactly that shape — but the warning is *not* what failed run 36950668957 (a successful
    # import 26 seconds earlier printed the same warning; the real error was a poll response, see the
    # retry in the `--execute` branch). They moved out because a generated file with no comments is one
    # less thing to argue about, not because the comment was the bug.
    print(f"{len(lessons)} lessons parsed at {now}", file=sys.stderr)
    stmts: list[str] = []
    for l in lessons:
        vals = []
        for c in cols:
            if c == "synced_at":
                vals.append(now)
                continue
            v = l.get(c, "")
            if v is None:
                v = ""
            vals.append("'" + str(v).replace("'", "''") + "'")
        stmts.append(
            "INSERT INTO lessons (" + ", ".join(cols) + ") VALUES ("
            + ", ".join(vals) + ") "
            + "ON CONFLICT(id) DO UPDATE SET "
            + ", ".join(f"{c}=excluded.{c}" for c in cols if c != "id")
            + ";"
        )
    stmts.append(f"INSERT INTO lesson_sync_log (run_at, source_commit, total, upserted) "
                 f"VALUES ({now}, '{git_head()}', {len(lessons)}, {len(lessons)});")
    # The FTS5 rebuild (`lessons_fts`, PRD ④ #1356) left with the second search
    # implementation (issue #2121): ranked search is the worker's single BM25 index
    # (`worker_search_index`), which the worker cron builds from these same rows.
    return "\n".join(stmts) + "\n"


def git_head() -> str:
    try:
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                           capture_output=True, text=True, cwd=REPO, timeout=10)
        return r.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


# D1 REST query helper: returns {id: checksum} or None on failure.
# Uses the Cloudflare API (account token env or mcporter OAuth) so --reconcile
# works both in CI and locally without parsing wrangler output.
def _fetch_d1_checksums(db_name: str) -> dict | None:
    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID") or CF_ACCOUNT
    token = os.environ.get("CLOUDFLARE_API_TOKEN") or ""
    db_id = os.environ.get("MISAKANET_D1_ID") or ""
    if not db_id:
        # Resolve database_id by name via the D1 list API.
        try:
            if token:
                req = urllib.request.Request(
                    f"https://api.cloudflare.com/client/v4/accounts/{account}/d1/database?per_page=50",
                    headers={"Authorization": f"Bearer {token}", "User-Agent": "misakanet-sync"},
                )
                with urllib.request.urlopen(req, timeout=30) as r:
                    d = json.loads(r.read())
            else:
                # mcporter OAuth path
                code = (f"async () => {{ const r = await cloudflare.request({{ method: 'GET', "
                        f"path: '/accounts/{account}/d1/database' }}); return r.result || []; }}")
                r = subprocess.run(
                    [MC, "call", "cloudflare.execute", "code=" + code, "--config", CFG],
                    capture_output=True, text=True, timeout=60,
                )
                d = {"result": json.loads(r.stdout.strip()) if r.stdout.strip() else []}
            for entry in (d.get("result") or []):
                if entry.get("name") == db_name:
                    db_id = entry.get("uuid") or entry.get("id") or ""
                    break
        except Exception as e:
            print(f"Reconcile: cannot resolve D1 '{db_name}': {e}", file=sys.stderr)
            return None
    if not db_id:
        print(f"Reconcile: D1 database '{db_name}' not found", file=sys.stderr)
        return None
    # Query checksums.
    sql = "SELECT id, checksum FROM lessons"
    try:
        if token:
            req = urllib.request.Request(
                f"https://api.cloudflare.com/client/v4/accounts/{account}/d1/database/{db_id}/query",
                data=json.dumps({"sql": sql}).encode(),
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                         "User-Agent": "misakanet-sync"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=60) as r:
                d = json.loads(r.read())
            rows = (d.get("result") or [{}])[0].get("results") or []
        else:
            code = (
                "async () => { const r = await cloudflare.request({ method: 'POST', "
                f"path: '/accounts/{account}/d1/database/{db_id}/query', "
                f"body: {{ sql: '{sql}' }} }}); "
                "const rows = (r.result && r.result[0] && r.result[0].results) || []; "
                "const map = {}; for (const row of rows) map[row.id] = row.checksum; "
                "return map; }"
            )
            r = subprocess.run(
                [MC, "call", "cloudflare.execute", "code=" + code, "--config", CFG],
                capture_output=True, text=True, timeout=90,
            )
            return json.loads(r.stdout.strip()) if r.stdout.strip() else {}
        return {row["id"]: row["checksum"] for row in rows if row.get("id")}
    except Exception as e:
        print(f"Reconcile: D1 query failed: {e}", file=sys.stderr)
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Sync lessons to Cloudflare D1")
    ap.add_argument("--db", default="misakanet-db", help="D1 database name")
    ap.add_argument("--sql", action="store_true", help="only emit SQL to stdout")
    ap.add_argument("--dry-run", action="store_true", help="parse + print summary, no execute")
    ap.add_argument("--execute", action="store_true", help="run wrangler d1 execute --remote")
    ap.add_argument("--prune", action="store_true", help="delete D1 rows whose id no longer exists in the repo")
    ap.add_argument("--reconcile", action="store_true", help="compare repo checksums vs D1")
    ap.add_argument("--output", help="write SQL to this file instead of stdout")
    args = ap.parse_args()

    lessons = collect_lessons()
    print(f"Parsed {len(lessons)} lessons from {LESSONS_DIR}", file=sys.stderr)
    repo_ids = {l["id"] for l in lessons}

    if args.reconcile:
        repo = {l["id"]: l["checksum"] for l in lessons}
        # Pull D1 checksums — prefer mcporter (local OAuth) REST query, else
        # wrangler --remote. Both hit the same D1.
        d1 = _fetch_d1_checksums(args.db)
        if d1 is None:
            print("Reconcile: could not fetch D1 checksums", file=sys.stderr)
            return 2
        repo_only = sorted(repo.keys() - d1.keys())
        d1_only = sorted(d1.keys() - repo.keys())
        changed = sorted(k for k in repo.keys() & d1.keys() if repo[k] != d1[k])
        print(f"Reconcile: repo={len(repo)} D1={len(d1)}")
        print(f"  missing in D1: {len(repo_only)} {repo_only[:5]}")
        print(f"  extra in D1 (stale): {len(d1_only)} {d1_only[:5]}")
        print(f"  checksum changed: {len(changed)} {changed[:5]}")
        return 0 if not (repo_only or d1_only or changed) else 1

    sql = upsert_sql(lessons)

    if args.prune:
        # Emit deletes for ids present in D1 but absent from the repo, then the upserts.
        prune_sql = ("DELETE FROM lessons WHERE id NOT IN ("
                     + ",".join(f"'{i}'" for i in sorted(repo_ids)) + ");\n")
        sql = prune_sql + sql
        print(f"Prune: will delete lessons no longer in repo (keep {len(repo_ids)})",
              file=sys.stderr)

    if args.sql or args.output or not (args.execute or args.dry_run):
        if args.output:
            Path(args.output).write_text(sql, encoding="utf-8")
            print(f"SQL written to {args.output}", file=sys.stderr)
        else:
            sys.stdout.write(sql)
        return 0

    if args.dry_run:
        print(f"[dry-run] {len(lessons)} upserts would be executed against D1 "
              f"'{args.db}' (remote)", file=sys.stderr)
        return 0

    if args.execute:
        # 32KB argv limit (execve MAX_ARG_STRLEN) — pass SQL via a temp file
        # instead of --command so large syncs (314 lessons) work in CI.
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".sql", delete=False) as f:
            f.write(sql)
            tmp_path = f.name
        try:
            cmd = ["wrangler", "d1", "execute", args.db, "--remote", "--file", tmp_path]
            # What actually failed run 36950668957 (2026-10-02 01:26:42, `automation` red):
            # `✘ [ERROR] Not currently importing anything.` — a **server-side** `response.error` that
            # wrangler's `pollUntilComplete` throws when an import-status poll answers `success: false`.
            # The data had already landed: that run's own `INSERT INTO lesson_sync_log` is what
            # `/api/search-index` still reports as `syncStamp 2026-10-02 01:26:37`, and the FTS rows
            # sampled through the served endpoint were complete. So this is a transient status-poll
            # failure, not a rejected import, and the thing to do about it is try again.
            #
            # 3 attempts at most, ~10s then ~30s with jitter. This is a *mitigation*, not a fix: the
            # failure it covers is a control-plane hiccup, and an unattended push/cron job going red for
            # one is the kind of noise that erodes the signal. Retrying is safe because the SQL
            # converges — every lesson is an upsert by id, `--prune` deletes only ids the repository no
            # longer has, and the FTS index is deleted and rebuilt whole — and because the workflow sets
            # `concurrency: cancel-in-progress: false`, so no other sync can be importing at the same
            # time.
            backoffs = (10.0, 30.0)
            attempts = len(backoffs) + 1
            for attempt in range(1, attempts + 1):
                print(f"Executing (attempt {attempt}/{attempts}): {' '.join(cmd[:4])} --file=<tmp> ...",
                      file=sys.stderr)
                # 240s, not 600s: the successful import in the incident log took 1.26s, so this is ~190x
                # headroom, and three attempts of it fit inside the job's timeout instead of filling it.
                try:
                    r = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO,
                                       timeout=IMPORT_TIMEOUT_SECONDS)
                    out, err, rc = r.stdout or "", r.stderr or "", r.returncode
                except subprocess.TimeoutExpired as exc:
                    # Deliberately **not** retried, unlike every other entry below. The timeout kills the
                    # wrangler *client*, but a D1 import runs **server-side** and asynchronously (the
                    # init/ingest/poll phases are what the client is polling) — so killing it does not
                    # cancel the import it started. A second attempt could therefore begin while the
                    # first is still writing, which is the concurrent-import hazard the workflow's
                    # `concurrency` group exists to prevent; that group serializes *runs*, not attempts
                    # inside one run. The first version let the exception escape as a traceback; this
                    # reports it and fails, which a human can act on.
                    def _text(value):
                        return value.decode("utf-8", "replace") if isinstance(value, bytes) else (value or "")
                    out, err, rc = _text(exc.stdout), _text(exc.stderr), 1
                    err += (f"\nthe wrangler process did not finish within "
                            f"{IMPORT_TIMEOUT_SECONDS}s; not retrying, because the server-side import it "
                            f"started may still be running\n")
                    print(err, file=sys.stderr)
                    return rc
                # Every attempt's output is printed as it arrives, so a failure that is given up on
                # still carries the evidence of all three.
                sys.stdout.write(out)
                sys.stderr.write(err)
                if rc == 0:
                    return 0
                output = out + err
                transient = next((m for m in TRANSIENT_IMPORT_MARKERS if m in output), None)
                if transient is None:
                    print(f"attempt {attempt}/{attempts} failed with rc={rc} and no transient marker; "
                          f"not retrying (only in-transit failures are)", file=sys.stderr)
                    return rc
                if attempt == attempts:
                    break
                delay = backoffs[attempt - 1] * (1 + random.uniform(-0.3, 0.3))
                print(f"attempt {attempt}/{attempts} failed with rc={rc} on {transient!r}; "
                      f"retrying in {delay:.0f}s", file=sys.stderr)
                time.sleep(delay)
            return rc
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())

