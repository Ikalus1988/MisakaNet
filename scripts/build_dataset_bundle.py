#!/usr/bin/env python3
"""Build the publishable dataset bundle: the corpus, the benchmarks, and a manifest that says what
they are.

Why this exists (2026-10-27)
----------------------------
The repository has produced a citable artifact for weeks without ever making it citable. 651 lessons
live in `lessons/`, `data/okf/lessons.jsonl` is regenerated daily, and four benchmark reports sit in
`docs/benchmarks/` — all of it reachable only by cloning a git repository and knowing which file to
look for. A dataset nobody can link to is not a dataset; it is a directory.

So this turns the repository's own outputs into three files with stable names and a manifest that
carries the two things a consumer cannot infer: **the license of each file** and **how to cite it**.

The licensing decision is in the manifest on purpose (2026-10-27):

* the **corpus** is Apache-2.0, because that is what the repository is and what contributors
  submitted under. Relicensing it to something data-native would be a grant the project cannot make;
* the **benchmark artifacts** are CC0-1.0, because they are the project's own generated data and the
  point of publishing them is that someone else runs them. Attribution-required would add friction
  to the one thing this project needs more of.

Determinism: two runs over the same tree produce byte-identical files and a manifest that differs
only in `generated_at`/`source_commit`. The R2 publisher relies on that — it compares the manifest
hash and skips a re-upload when nothing changed.

Usage
-----
    python3 scripts/build_dataset_bundle.py                 # -> dist/dataset/
    python3 scripts/build_dataset_bundle.py --out /tmp/ds   # elsewhere
    python3 scripts/build_dataset_bundle.py --check         # print the manifest, write nothing
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_OUT = REPO / "dist" / "dataset"

DATASET_NAME = "misakanet-lessons"
HOMEPAGE = "https://misakanet.org"

# (source path in the repo, name in the bundle, license id, content type)
# The corpus first, then the benchmark set, in a fixed order so the manifest is stable.
FILES: tuple[tuple[str, str, str, str], ...] = (
    ("data/okf/lessons.jsonl", "lessons.jsonl", "Apache-2.0", "application/x-ndjson"),
    ("data/lessons.json", "lessons.json", "Apache-2.0", "application/json"),
    ("docs/benchmarks/retrieval-l1-267-queries.jsonl", "benchmarks/retrieval-l1-267-queries.jsonl",
     "CC0-1.0", "application/x-ndjson"),
    ("docs/benchmarks/retrieval-l1-267-2026-10-27.json", "benchmarks/retrieval-l1-267-2026-10-27.json",
     "CC0-1.0", "application/json"),
    ("docs/benchmarks/retrieval-zh-crosslingual-2026-10-27.json",
     "benchmarks/retrieval-zh-crosslingual-2026-10-27.json", "CC0-1.0", "application/json"),
    ("docs/benchmarks/embedding-ab-2026-10-27.json", "benchmarks/embedding-ab-2026-10-27.json",
     "CC0-1.0", "application/json"),
)

LICENSES = {
    "Apache-2.0": {
        "id": "Apache-2.0",
        "name": "Apache License 2.0",
        "url": "https://www.apache.org/licenses/LICENSE-2.0",
        "applies_to": ["lessons.jsonl", "lessons.json"],
        "why": "The repository is Apache-2.0 and lesson text was contributed under it. The project "
               "cannot relicense contributed text, so the corpus ships under the license it was "
               "submitted under.",
    },
    "CC0-1.0": {
        "id": "CC0-1.0",
        "name": "CC0 1.0 Universal (public domain dedication)",
        "url": "https://creativecommons.org/publicdomain/zero/1.0/",
        "applies_to": ["benchmarks/"],
        "why": "The query sets and evaluation results are produced by this project. A dedication "
               "removes every reason for another benchmarker to hesitate, which is the point of "
               "publishing them.",
    },
}

CITATION = (
    "MisakaNet contributors (2026). MisakaNet — a corpus of agent failure lessons and retrieval "
    "benchmarks. " + HOMEPAGE + "/dataset"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_commit() -> str:
    """The commit the bundle was built from, or `unknown` outside a git checkout.

    `unknown` rather than a guess: a bundle that claims a commit it cannot verify is worse than one
    that admits it was built from a tarball.
    """
    try:
        out = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"],
                             capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    value = (out.stdout or "").strip()
    return value if out.returncode == 0 and value else "unknown"


def count_jsonl(path: Path) -> int:
    with path.open(encoding="utf-8") as fh:
        return sum(1 for line in fh if line.strip())


def build(out_dir: Path, version: str | None = None, copy: bool = True) -> dict:
    """Copy the published files into `out_dir` and return the manifest.

    A missing source file is a hard error, not a skipped entry: a bundle that silently ships five of
    six files is exactly the kind of quiet gap this repository keeps writing lessons about.
    """
    missing = [src for src, _, _, _ in FILES if not (REPO / src).exists()]
    if missing:
        raise SystemExit("error: missing source file(s):\n  " + "\n  ".join(missing))

    version = version or datetime.now(UTC).strftime("%Y-%m-%d")
    entries: list[dict] = []
    if copy:
        out_dir.mkdir(parents=True, exist_ok=True)

    for src, name, license_id, content_type in FILES:
        source = REPO / src
        target = out_dir / name
        if copy:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        entries.append({
            "path": name,
            "bytes": source.stat().st_size,
            "sha256": sha256(source),
            "license": license_id,
            "content_type": content_type,
        })

    # License texts travel with the data. `LICENSE` is the repository's own Apache-2.0 copy;
    # CC0 is a short dedication because the full legal code is a URL away and a 1.2 KB legal
    # document duplicated in a download adds bytes without adding consent.
    if copy:
        apache = REPO / "LICENSE"
        if apache.exists():
            shutil.copyfile(apache, out_dir / "LICENSE")
        (out_dir / "LICENSE-CC0").write_text(
            "CC0 1.0 Universal (public domain dedication)\n\n"
            "To the extent possible under law, the authors have waived all copyright and related\n"
            "or neighboring rights to the files under benchmarks/ in this directory.\n\n"
            "Full text: https://creativecommons.org/publicdomain/zero/1.0/legalcode\n",
            encoding="utf-8",
        )

    counts = {
        "lessons": count_jsonl(REPO / "data/okf/lessons.jsonl"),
        "queries": count_jsonl(REPO / "docs/benchmarks/retrieval-l1-267-queries.jsonl"),
        "benchmarks": sum(1 for e in entries if e["path"].startswith("benchmarks/")),
    }

    manifest = {
        "dataset": DATASET_NAME,
        "version": version,
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_commit": source_commit(),
        "homepage": HOMEPAGE,
        "counts": counts,
        "licenses": LICENSES,
        "citation": CITATION,
        "files": entries,
        # The shape a consumer needs to parse `lessons.jsonl` without reading this script.
        "schema": {
            "lessons.jsonl": {
                "format": "JSON Lines, one lesson per line",
                "fields": ["type", "title", "description", "tags", "domain", "evidence_level",
                           "url", "summary", "trigger", "verify"],
                "note": "`url` is the lesson's path inside the repository, not a URL on the site.",
            },
            "lessons.json": {
                "format": "JSON array",
                "fields": ["id", "title", "domain", "tags", "summary", "evidence_level", "url"],
            },
            "benchmarks/*": {
                "format": "the published run artifacts, unchanged",
                "note": "Each file carries its own method and limitations section.",
            },
        },
    }

    if copy:
        (out_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--version", default=None, help="version label (default: today, YYYY-MM-DD)")
    ap.add_argument("--check", action="store_true", help="print the manifest and write nothing")
    args = ap.parse_args(argv)

    manifest = build(Path(args.out), version=args.version, copy=not args.check)
    total = sum(e["bytes"] for e in manifest["files"])
    print(f"{manifest['dataset']} {manifest['version']} — "
          f"{manifest['counts']['lessons']} lessons, {manifest['counts']['queries']} queries, "
          f"{manifest['counts']['benchmarks']} benchmark files, {total / 1024:.0f} KiB")
    if args.check:
        print(json.dumps(manifest, ensure_ascii=False, indent=1))
    else:
        print(f"wrote {args.out}/manifest.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
