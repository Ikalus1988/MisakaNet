#!/usr/bin/env python3
"""Every `fetchFromGitHub` call must name a ref, and that ref must carry that path (#1820).

The worker's last-resort reads go through `fetchFromGitHub(token, path, ref)`. That function used to
default `ref` to `"data"` — a branch `update-badges.yml` maintains for badges and a compact index — and
two callers relied on the default:

    return fetchFromGitHub(token, "data/counter.json");          // /api/counter, last resort
    return fetchFromGitHub(token, "data/pr-genius-stats.json");  // PR Genius stats, token branch

Neither path exists on `data`, measured 2026-09-25 (`contents/data/counter.json?ref=data` → 404), so
both asked for a file that is not there, got a 404, and surfaced as `502` at exactly the moment the
fallback was the only thing left. The counter's maintained copy is on `main`
(`data/counter.json`, rewritten daily by `sync-node-counter.yml`, with its own `updated` date); the
pr-genius handler's *no-token* branch had always read `main`, so one handler disagreed with itself.

The counter case has a second edge worth recording: the `data` branch does carry a `counter.json`, at
its **root**, frozen on **2026-06-01** (`{"current": 10047, "updated": "2026-06-01T02:25:00Z"}`) — that
is the stale number issue #1820 was filed about. It is not a fallback; reading it again would restore the
original defect in a different shape. Hence: no default ref, and every named (path, ref) pair is checked.

Two rules, both derived from the source rather than remembered:

1. the signature takes no default, so a call that forgets the ref is a lint-level mistake, not a silent
   read of the wrong branch;
2. every call names a ref explicitly, and a path under `main` must exist in this checkout.

A non-`main` ref cannot be verified offline (the branch is not in the working tree), so the few that
exist are listed with a reason — and the list is checked for dead entries.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
WORKER = REPO / "workers" / "register-proxy-sw.js"

# (path, ref) pairs other than `main` that are legitimate, each with the reason it is legitimate.
OTHER_REFS: dict[tuple[str, str], str] = {
    ("lessons.json", "data"): (
        "the `data` branch keeps a compact lesson index at its root (81 KB against main's 1.26 MB "
        "`data/lessons.json` — a different artifact by design), written by update-badges.yml"
    ),
}

# `fetchFromGitHub(<anything>, "<path>"[, "<ref>"])` — the call, not the definition, and not a mention
# inside a comment: this test's own explanation quotes the broken calls, and a whole-file search would
# match those instead of the code.
CALL_RE = re.compile(
    r"fetchFromGitHub\(\s*[^,()]+,\s*\"([^\"]+)\"\s*(?:,\s*\"([^\"]+)\")?\s*\)"
)
DEF_RE = re.compile(r"async\s+function\s+fetchFromGitHub\s*\(([^)]*)\)")


def _code_lines(path: Path = WORKER) -> list[str]:
    """The file's lines with comments removed — the same trap that has cost this repo four tests."""
    out = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if stripped.startswith(("//", "*", "/*")):
            continue
        out.append(re.sub(r"//.*$", "", raw))
    return out


def calls() -> list[tuple[str, str | None]]:
    return CALL_RE.findall("\n".join(_code_lines()))


def test_the_scanner_sees_the_calls_it_is_about():
    """A regex that matched nothing would make every assertion below vacuous."""
    found = calls()
    assert len(found) >= 3, found
    assert any(path == "data/counter.json" for path, _ in found), found


def test_the_reader_has_no_default_ref():
    """A default is what made two callers read the wrong branch without saying so."""
    signature = DEF_RE.search("\n".join(_code_lines()))
    assert signature, "fetchFromGitHub is gone or renamed"
    params = signature.group(1)
    assert "ref" in params, params
    assert "=" not in params.split("ref")[1][:6], (
        f"the signature gives `ref` a default again ({params!r}) — a caller can then read a branch it "
        "never named, which is exactly #1820"
    )


def test_every_call_names_its_ref():
    unnamed = [path for path, ref in calls() if not ref]
    assert unnamed == [], (
        f"these calls do not name a ref: {unnamed}. Say which copy is meant — `main` for the files "
        "mirrored there, and the entry in OTHER_REFS with a reason for anything else."
    )


@pytest.mark.parametrize("path", ["data/counter.json", "data/pr-genius-stats.json"])
def test_the_main_backed_reads_name_main(path):
    """The two that were broken: their files live on `main` and nowhere else."""
    refs = {ref for p, ref in calls() if p == path}
    assert refs == {"main"}, (
        f"{path} is read from {refs or 'nowhere'}; the maintained copy is on `main` "
        f"(and `data/counter.json` is 404 on the `data` branch — measured 2026-09-25)"
    )


def test_a_main_path_exists_in_this_checkout():
    for path, ref in calls():
        if ref != "main":
            continue
        assert (REPO / path).is_file(), (
            f"{path} is read from `main` but is not in the tree — the fallback would 404 into a 502"
        )


def test_every_other_ref_is_declared_with_a_reason():
    undeclared = [(path, ref) for path, ref in calls() if ref and ref != "main"
                  and (path, ref) not in OTHER_REFS]
    assert undeclared == [], (
        f"these reads use a ref this test cannot verify offline: {undeclared}. Add each to OTHER_REFS "
        "with the reason it is the right copy — an undeclared one is how #1820 happened."
    )


def test_no_declared_other_ref_is_dead():
    """A stale exemption is a hole: if the call is gone, the entry has to go with it."""
    live = {(path, ref) for path, ref in calls()}
    for key, reason in OTHER_REFS.items():
        assert key in live, f"OTHER_REFS lists {key}, which no call uses any more"
        assert len(reason) > 40, f"{key} is exempted without a real reason: {reason!r}"


def test_there_is_only_one_reader_named_fetchfromgithub():
    """A second copy is how the `ref = "data"` default comes back.

    `workers/lib/handlers.js` — the module "extracted from register-proxy-sw.js for maintainability" —
    carried its own `async function fetchFromGitHub(token, path, ref = "data")` until 2026-09-25. It was
    worse than a duplicate: it interpolated `PUBLIC_DATA_BASE` and never read `ref` at all, so its
    default named a branch the function did not fetch, and it held the very default this file exists to
    keep out of the worker. Nothing imported it — the worker takes only
    `GITHUB_API`/`REPO`/`PUBLIC_DATA_BASE` from that module — which is precisely why it survived: a copy
    no caller uses cannot be caught by a test of the callers, and the next one to import it would have
    inherited both the signature and the lie.
    """
    definitions = sorted(
        path.relative_to(REPO).as_posix()
        for path in (REPO / "workers").rglob("*.js")
        if DEF_RE.search("\n".join(_code_lines(path)))
    )
    assert definitions == ["workers/register-proxy-sw.js"], (
        f"`fetchFromGitHub` is defined in {definitions}. Keep one reader, in the worker: that is the copy "
        "with no default, the deadline, and the (path, ref) checks in this file — a second one starts "
        "from a clean slate and a default"
    )


LIB = REPO / "workers" / "lib" / "handlers.js"
FUNCTION_RE = re.compile(r"^\s*(?:async\s+)?function\s+\w+|^\s*(?:const|let)\s+\w+\s*=\s*(?:async\s*)?\(", re.M)


def test_the_shared_module_keeps_no_function_of_its_own():
    """The copies in `workers/lib/handlers.js` were live code's forks, and they drifted the moment they
    were written — so the module keeps constants and nothing else.

    Read the file rather than trusting this docstring: every implementation it carried (`searchLessons`,
    `tokenize`, `fetchLessonContent`, `fetchFromGitHub`, `fetchPublicJson`, `getWithCache`) was
    unreachable from any test, because nothing imported it except the worker's destructuring of three
    constants. The drift is on the record: its `fetchLessonContent` never got the B35 guard, and its
    `fetchFromGitHub` kept the `ref = "data"` default #1820 removed. A "keep them in sync" rule would
    need a test per function per change; the rule that no copy exists needs one test, this one.
    """
    code = "\n".join(_code_lines(LIB))
    found = FUNCTION_RE.findall(code)
    assert not found, (
        f"{LIB.relative_to(REPO)} defines functions again ({[f.strip() for f in found]}). Implementations "
        "belong in workers/register-proxy-sw.js, where the tests and the live callers are; a helper in "
        "this module is a fork nothing exercises"
    )
    assert code.count("export") == 1, "one export block with the constants"


def test_the_shared_constants_are_the_ones_the_worker_destructures():
    """The module's entire contract — asserted against the consumer, not against a list here."""
    from_name = re.findall(r"const\s*\{([^}]*)\}\s*=\s*_handlers", (REPO / "workers" / "register-proxy-sw.js")
                           .read_text(encoding="utf-8"))
    assert from_name, "the worker no longer destructures anything from lib/handlers.js"
    wanted = {name.strip() for name in from_name[0].split(",") if name.strip()}
    exported = set(re.findall(r"^\s*([A-Z_]+),\s*$", LIB.read_text(encoding="utf-8"), re.M))
    assert wanted == exported == {"GITHUB_API", "REPO", "PUBLIC_DATA_BASE"}, (
        f"worker imports {sorted(wanted)}, module exports {sorted(exported)}"
    )
