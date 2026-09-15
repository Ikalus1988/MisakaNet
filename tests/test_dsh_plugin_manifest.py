#!/usr/bin/env python3
"""The root package must stay a *discoverable* DSH plugin (issue #1677).

Background — the install that failed
------------------------------------
A DSH user ran the plugin-hub install for `ikalus1988/misakanet` and got:

    [packaging] @misaka-net/misakanet-setup: entry file missing: index.js
    (git distribution lacks build output — install the npm version or report to the author)

Nothing was missing from the plugin. The hub resolved the *repository* to a
package with `npm search repository:ikalus1988/misakanet`, and the only package
that advertised the repository was `@misaka-net/misakanet-setup` — the setup CLI,
which has no `main` and no entry file. The package that *is* the plugin
(`misakanet`, with `main: index.js` and the `dsh.bundle.patch` row) declared no
`repository` at all, so it never appeared as a candidate:

    misakanet@2.30.0                 repository: None
    @misaka-net/misakanet-setup@0.4.0 repository: git+…/Ikalus1988/MisakaNet.git   (no main)

So an agent-visible bug ("entry file missing") had a metadata cause, and the only
thing that would have caught it is a test that pins the *discoverability* facts
rather than the file contents — the file contents were always correct, which is
why the failure looked inexplicable from the repo side.

What is pinned here
-------------------
1. the plugin package advertises this repository (the field the resolution needs);
2. `main` and `dsh.bundle.patch` exist *and* ship (a declared file that is not in
   `files` is exactly what "entry file missing" describes, from the packer's side);
3. no other package in the repo can be mistaken for the plugin.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PKG = REPO / "package.json"
REPO_SLUG = "ikalus1988/misakanet"


def _pkg() -> dict:
    return json.loads(PKG.read_text(encoding="utf-8"))


def _norm_repo(url: str) -> str:
    """`git+https://github.com/O/R.git` → `o/r` (GitHub URLs are case-insensitive)."""
    value = url.strip()
    for prefix in ("git+", "git://", "https://", "http://", "ssh://git@"):
        if value.startswith(prefix):
            value = value[len(prefix):]
    value = value.removesuffix(".git").rstrip("/")
    if value.startswith("github.com/"):
        value = value[len("github.com/"):]
    if value.startswith("github.com:"):
        value = value[len("github.com:"):]
    return value.lower()


def test_plugin_package_advertises_this_repository():
    """Without `repository`, npm's repository search cannot find the plugin.

    This is the whole cause of #1677: the hub searched by repository, got the
    setup CLI (the only package linked to the repo), and reported the CLI's
    missing entry file as a plugin packaging error.
    """
    repo = _pkg().get("repository")
    assert repo, (
        "package.json declares no `repository`, so `npm search repository:"
        f"{REPO_SLUG}` cannot return the plugin — that is what made the plugin hub "
        "resolve this repo to @misaka-net/misakanet-setup (#1677)"
    )
    url = repo if isinstance(repo, str) else repo.get("url", "")
    assert _norm_repo(url) == REPO_SLUG.lower(), f"repository.url is {url!r}, not this repo"


def test_declared_entry_and_bundle_patch_exist_and_ship():
    """A declared entry file must exist *and* be in `files` (or it is not packed)."""
    pkg = _pkg()
    files = pkg.get("files") or []

    main = pkg.get("main")
    assert main, "package.json declares no `main`, which DSH plugin installers expect"
    assert (REPO / main).is_file(), f"main {main!r} does not exist"
    assert main in files or any(
        f.rstrip("/") == main for f in files
    ), f"main {main!r} is not in `files`, so the packed tarball omits it"

    patch = (pkg.get("dsh") or {}).get("bundle", {}).get("patch")
    assert patch, "package.json declares no dsh.bundle.patch, so the bundle mounts nothing"
    rel = patch.removeprefix("./")
    assert (REPO / rel).is_file(), f"dsh.bundle.patch {patch!r} does not exist"
    assert rel in files, f"dsh.bundle.patch {patch!r} is not in `files`, so it is not packed"


def test_every_declared_file_entry_exists():
    """A `files` entry that matches nothing silently shrinks the distribution."""
    missing = []
    for entry in _pkg().get("files") or []:
        rel = entry.removeprefix("./")
        if rel.endswith("/**") or rel.endswith("/*"):
            if not (REPO / rel.split("/*")[0]).exists():
                missing.append(entry)
        elif not (REPO / rel.rstrip("/")).exists():
            missing.append(entry)
    assert missing == [], f"declared in `files` but absent from the tree: {missing}"


def test_only_one_package_in_the_repo_claims_to_be_the_plugin():
    """Ambiguity is the failure mode: exactly one package may carry a `dsh` field.

    `packages/*` are CLIs that legitimately link to this repository. If one of
    them ever grew a `dsh` field, a plugin-resolution search would have a second
    candidate that cannot actually mount anything.
    """
    claimants = []
    for manifest in [PKG, *sorted(REPO.glob("packages/*/package.json"))]:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        if not data.get("dsh"):
            continue
        rel = manifest.relative_to(REPO).as_posix()
        has_main = bool(data.get("main")) and (manifest.parent / data["main"]).is_file()
        claimants.append((rel, bool(data["dsh"].get("bundle", {}).get("patch")), has_main))

    assert len(claimants) == 1, f"multiple DSH plugin claimants: {claimants}"
    rel, has_patch, has_main = claimants[0]
    assert rel == "package.json", f"the plugin package should be the repo root, got {rel}"
    assert has_patch and has_main, f"{rel} claims to be a DSH bundle but cannot mount: {claimants[0]}"


def test_setup_cli_is_not_shipped_as_a_plugin():
    """The package the hub mis-picked must stay a CLI (no main, no `dsh` field)."""
    setup = REPO / "packages" / "misakanet-setup" / "package.json"
    if not setup.is_file():
        return
    data = json.loads(setup.read_text(encoding="utf-8"))
    assert "dsh" not in data or not data["dsh"], (
        "packages/misakanet-setup declares a `dsh` field; it is the CLI the hub "
        "already mistakes for the plugin (#1677), so this would make the mis-pick permanent"
    )
    assert data.get("bin", {}).get("misakanet-setup"), "the setup package must stay a CLI"
