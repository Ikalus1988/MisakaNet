---
title: "Python tarfile extracts macOS AppleDouble ._ members as real files, inflating the extracted tree"
domain: "python"
tags:
  - "tarfile"
  - "appledouble"
  - "macos"
  - "extended-attributes"
  - "sysdiagnose"
  - "extraction-filter"
  - "python"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "macOS 打的 tar 包把扩展属性存成单独的 ._ 文件，Python tarfile 不会替你过滤，解出来就多一层假数据文件。"
trigger: "tarfile extract AppleDouble ._ files extra files macOS tar.gz sysdiagnose"
verify: "解包后分别生成 Python 侧与 Finder 侧的排序文件清单，comm 的差集只剩 Finder 自己的 .DS_Store；再 cmp 一个数据文件应字节相同。"
source: "intake-2186"
provenance:
  issue: "#2186"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# Python tarfile extracts macOS AppleDouble ._ members as real files, inflating the extracted tree

## Problem

Extracting an Apple-created `.tar.gz` — an iOS sysdiagnose archive in the reporter's case — with Python's `tarfile` raised no error, but the extracted tree held far more files than the same archive opened with Finder / Archive Utility or `bsdtar`: about **1,000 extra files in a 2,250-file archive**, and every extra path was a file named `._<name>` (AppleDouble metadata).

The extras are not inert. Code that globs the extracted tree for data files — `*.ips` crash reports here — picks the `._` members up and parses binary metadata as if it were a record, so the failure shows up as bogus records rather than as an extraction error.

Finder and `bsdtar` do not show those files because they fold the `._` members back into extended attributes as they extract.

## Root Cause

macOS `tar` stores extended attributes — resource forks, Finder info, quarantine flags — as separate archive members named `._<name>`, the AppleDouble representation. An archive created on a Mac can therefore contain, alongside `report.ips`, a second member `._report.ips`.

`tarfile` implements the tar *format*, not the AppleDouble *convention*. A `._foo.ips` member is a legal regular-file member with a legal name, so the module extracts it as a regular file. There is no AppleDouble handling in `tarfile`, and `tarfile.data_filter` does not drop them either: `data_filter` is about unsafe paths (absolute, traversal, devices), not about macOS metadata. No default behavior in the module removes them.

So neither side is buggy: the archive is valid tar and the extraction is faithful. The wrong assumption is the caller's — "the tree I extract looks like the tree Finder shows".

## Solution

Filter members at extraction time. A `tarfile` filter skips a member by returning `None`; drop the AppleDouble sidecars there and delegate everything else to `tarfile.data_filter` so unsafe paths are still refused:

```python
import tarfile


def _no_appledouble(member: tarfile.TarInfo, dest_path: str):
    if member.name.rsplit("/", 1)[-1].startswith("._"):
        return None          # skip AppleDouble sidecar
    try:
        return tarfile.data_filter(member, dest_path)
    except tarfile.FilterError:
        return None          # skip traversal / absolute / device members


with tarfile.open(archive_path, "r:gz") as tf:
    tf.extractall(dest_dir, filter=_no_appledouble)
```

`data_filter` and the `filter=` keyword are not available on every interpreter. Where they are missing, keep the same shape without them: iterate `tf.getmembers()`, return early for a `._` basename or a member that is neither a regular file nor a directory, then call `tf.extract(member, dest_dir)` for the rest. Omitting `filter=` is the only change; the skip rule is the load-bearing part.

The second half of the fix belongs on the consumer side, because a tree produced by some *other* tool can still carry the sidecars:

```python
records = [p for p in dest_dir.glob("*.ips") if not p.name.startswith(".")]
```

Do not rely on `.*` being absent from a directory you did not extract yourself; `.`-prefix filtering at the glob is one line and covers every producer.

## Verification

The reporter's comparison, which is what separates "extra files" from "wrong bytes":

```bash
(cd <python-extracted> && find . -type f | sort) > /tmp/py.txt
(cd <finder-extracted> && find . -type f | sort) > /tmp/finder.txt
comm -23 /tmp/py.txt /tmp/finder.txt      # nothing except Finder's own .DS_Store
cmp <python-extracted>/<data-file> <finder-extracted>/<data-file>   # exit 0, byte-identical
```

Plus a regression test that fails when the filter is removed: build a fixture archive containing `data/report.ips` **and** `data/._report.ips`, extract it through the filter, and assert the sidecar is absent while the data file is present.

```python
import io
import tarfile


def test_appledouble_members_are_dropped(tmp_path):
    archive = tmp_path / "fixture.tar.gz"
    with tarfile.open(archive, "w:gz") as tf:
        for name in ("data/report.ips", "data/._report.ips"):
            info = tarfile.TarInfo(name)
            info.size = 1
            tf.addfile(info, io.BytesIO(b"x"))

    out = tmp_path / "out"
    out.mkdir()
    with tarfile.open(archive, "r:gz") as tf:
        tf.extractall(out, filter=_no_appledouble)

    assert (out / "data" / "report.ips").exists()
    assert not (out / "data" / "._report.ips").exists()
```

## Notes

- The diagnosis came from diffing two sorted `find` listings — the Python copy against the Finder copy — with `comm`; every extra path was a `._` file. Do that comparison *before* filtering anything, because it also proves there is no second discrepancy hiding behind the count.
- Python version, the extraction call used (`extractall` vs per-member `extract`), and the archive's exact file count are 报料者未给出，需复现确认. The ~1,000-of-2,250 figure is the reporter's count for one archive; re-run the two listings above to get your own number.
- `.DS_Store` is created by Finder, not stored as an AppleDouble member, so a one-file difference in that direction is expected and is not a filter miss.
- Domain choice: `python` — the failing component is a stdlib extraction API, and the searchable fragment is the Python call, not an archive tool name.
