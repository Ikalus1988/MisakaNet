#!/usr/bin/env python3
"""Publish the install-smoke result as a shields badge (`data` branch `badges/install.json`).

The decision this implements (owner D3 = A, 2026-09-30): make "install verified" a **measured, dated
fact**, not a claim. Two forms are probed daily by `.github/workflows/install-smoke.yml` and this script
turns their per-form JSON artifacts into one badge a human can read without opening a log:

    {"schemaVersion":1,"label":"install verified","message":"verified 2026-09-30","color":"brightgreen"}

Why it is a *date* and not "passing"
------------------------------------
The badge is a photograph of the last successful run, not a live status. Saying "verified" with no date
would recreate the exact confusion intake #2486 reported ("automatic check passed" read as "it works").
With the date, a stale green is visibly stale.

The "a failed fetch publishes nothing" rule is inherited from `scripts/update_retrieval_badge.py`, and it
has two halves here, which are deliberately different:

* **no result file at all** → publish nothing and exit 0. That is *absence of a measurement* (a job
  crashed before probing, a runner died), and overwriting yesterday's badge with "no data" would trade a
  dated fact for an undated non-fact. The red workflow run is the signal for that case.
* **a result file that says `"ok": false`** → publish **red**, naming the failing form. That *is* a
  measurement: the probe installed the thing, called it, and it answered wrongly. Keeping yesterday's
  green here would be the lie this whole change exists to prevent.

A single form's success is not a clean run: green requires both forms to be present and ok. Half the
evidence is not evidence.

Usage:
    python3 scripts/update_install_badge.py --results-dir /tmp/install-results --out /tmp/badges/install.json
    python3 scripts/update_install_badge.py --results-dir /tmp/install-results --print
"""
from __future__ import annotations

import argparse
import datetime as _datetime
import json
import sys
from pathlib import Path

# The artifact files the workflow uploads, keyed by the form name that goes into the result JSON. Bound to
# filenames rather than globbing so a renamed artifact is a visible "missing form", not a silent one.
FORM_FILES = {"npm": "install-npm.json", "git": "install-git.json"}
LABEL = "install verified"
DEFAULT_OUT = Path("badges/install.json")


def _today() -> str:
    return _datetime.datetime.now(_datetime.timezone.utc).strftime("%Y-%m-%d")


def load_results(results_dir: Path) -> dict[str, dict]:
    """Read every per-form artifact that exists, keyed by form.

    A file that exists but cannot be read is an error, not "missing": the probe wrote it, so an
    unreadable one is a shape change worth failing on (the same distinction `update_retrieval_badge.py`
    draws). A file that does not exist is simply not a measurement and is skipped.
    """
    results: dict[str, dict] = {}
    for form, name in FORM_FILES.items():
        path = results_dir / name
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise SystemExit(f"{path} exists but cannot be read ({type(error).__name__}: {error}) — "
                             "refusing to publish a badge from evidence this script cannot interpret")
        if not isinstance(payload, dict) or "ok" not in payload:
            raise SystemExit(f"{path} has no `ok` field (keys: "
                             f"{sorted(payload) if isinstance(payload, dict) else type(payload).__name__}) "
                             "— the badge would publish a verdict that means nothing")
        results[form] = payload
    return results


def badge_for(results: dict[str, dict], today: str) -> dict | None:
    """The shields payload, or None when there is not enough evidence to publish anything.

    None is returned for **absent** evidence only. Measured failure returns a red badge naming the form.
    """
    if not results:
        return None
    failed = sorted(form for form, payload in results.items() if not payload.get("ok"))
    if failed:
        return {"schemaVersion": 1, "label": LABEL, "message": f"{'+'.join(failed)} failed {today}",
                "color": "red"}
    missing = sorted(set(FORM_FILES) - set(results))
    if missing:
        # Publishing green off one form would be the "green from metadata" mistake in miniature.
        return None
    return {"schemaVersion": 1, "label": LABEL, "message": f"verified {today}", "color": "brightgreen"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--results-dir", type=Path, default=Path("/tmp/install-results"))
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--print", action="store_true", dest="print_badge",
                        help="print the badge instead of writing it")
    args = parser.parse_args(argv)

    results = load_results(args.results_dir)
    for form, payload in sorted(results.items()):
        print(f"install badge: {form} → ok={payload.get('ok')} "
              f"result_count={payload.get('result_count')} tools={payload.get('tool_count')} "
              f"at {payload.get('timestamp')}")
    for failure in [f for payload in results.values() for f in payload.get("failures") or []]:
        print(f"install badge: probe failure: {failure}", file=sys.stderr)

    badge = badge_for(results, _today())
    if badge is None:
        print(f"install badge: not enough evidence to publish (forms present: {sorted(results)} of "
              f"{sorted(FORM_FILES)}) — nothing written, yesterday's badge stays until a real run "
              "replaces it")
        return 0
    if args.print_badge:
        print(json.dumps(badge, ensure_ascii=False))
        return 0
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(badge, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"install badge → {args.out}: {json.dumps(badge, ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
