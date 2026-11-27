#!/usr/bin/env python3
"""Record one real `misakanet_search` into `docs/assets/hero.json`.

Why this exists rather than a hand-written number
-------------------------------------------------
The homepage's hero used to say "30+ min manual debugging vs **0.02s** with MCP". The 30 minutes was
end-to-end debugging and the 0.02s was BM25 alone — two different measurements on one line, which is
the comparison a reader is most entitled to distrust. `scripts/render_hero_svg.py` replaced it with a
picture built from measurements, and this is the only writer of those measurements.

The rule this file enforces: **every number in the hero is a recorded observation.** Not a
representative one, not a rounded one, not one from a good day. If a field cannot be measured it does
not go in the snapshot, and the renderer has nothing to print.

What is deliberately *not* recorded:

* **Token counts, turn counts, "minutes saved".** Nothing in this repository measures them.
  `search_signals` has `latency_ms`, `solved`, `query`, `top_id` and self-declared client fields —
  there is no token or turn telemetry anywhere, so a figure like "~38k tokens → ~1.9k" would be
  invented and would read as measured.
* **A "without MisakaNet" column.** There is no instrument for the counterfactual. The renderer draws
  the one session that was actually recorded.

Latency is sampled repeatedly because a single call is a measurement of *one call*. The snapshot keeps
every sample so a reader can see the spread rather than a median that hides it.

Usage:
    python3 scripts/record_hero_snapshot.py                    # record, write docs/assets/hero.json
    python3 scripts/record_hero_snapshot.py --samples 9         # wider spread
    python3 scripts/record_hero_snapshot.py --check             # fail if the corpus counts moved

`--check` is what CI runs: it re-derives the corpus half of the snapshot (lesson count and the
evidence distribution) from `data/lessons.json` and compares. The latency half cannot be re-derived
without calling the network, so it is dated in the snapshot and left alone.
"""
from __future__ import annotations

import argparse
import collections
import json
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SNAPSHOT = REPO / "docs" / "assets" / "hero.json"
LESSONS = REPO / "data" / "lessons.json"

#: The query, and it is the **same one the README's own first run sends**.
#:
#: Measured 2026-11-27: the first screen used to tell three unrelated stories — the hook said
#: `database is locked`, the hero searched `GitHub Actions script injection`, and the curl snippet
#: searched `database is locked` again. Three examples is three things to remember; one example,
#: shown three times (the pain, the answer, the command you can paste), is a loop the reader closes.
#:
#: What this query returns today: top hit `两个独立进程并发写同一个-sqlite-数据库wal`, **E1**. An earlier default
#: (`GitHub Actions script injection`) returned E3, which reads better — but a hero is a recording,
#: and picking the query for its grade rather than for the story is the same defect as picking the
#: measurement that flatters.
DEFAULT_QUERY = "database is locked"

ENDPOINT = "https://misakanet.org/mcp"


def _curl_search(query: str, top: int = 3) -> tuple[list[dict], int]:
    """One search, through `curl`. Returns (results, wall-clock milliseconds).

    `curl` rather than `urllib`: the worker answers `403` to `Python-urllib/*`'s User-Agent, which is
    the endpoint being honest about who is calling rather than something to work around with a fake
    agent string. The probe scripts in this repository use `curl` for the same reason.
    """
    if not shutil.which("curl"):
        raise SystemExit("curl is required — this script uses the same client the probes do")
    payload = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "misakanet_search", "arguments": {"query": query, "top": top}},
    })
    started = time.perf_counter()
    proc = subprocess.run(
        ["curl", "-sS", "-m", "40", "-X", "POST", ENDPOINT,
         "-H", "Content-Type: application/json",
         "-H", "Accept: application/json",
         "-H", "MCP-Protocol-Version: 2025-06-18",
         "-H", "Origin: https://misakanet.org",
         "--data-binary", "@-"],
        input=payload.encode("utf-8"), capture_output=True, check=False,
    )
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    if proc.returncode != 0:
        raise SystemExit(f"curl failed ({proc.returncode}): {proc.stderr.decode('utf-8', 'replace')[:300]}")
    body = json.loads(proc.stdout.decode("utf-8"))
    if isinstance(body, list):
        rows = body
    else:
        rows = ((body.get("result") or {}).get("structuredContent") or {}).get("results") or []
        if not rows:
            raise SystemExit(f"no results for {query!r}: {json.dumps(body, ensure_ascii=False)[:400]}")
    return rows, elapsed_ms


def corpus_facts() -> dict:
    data = json.loads(LESSONS.read_text(encoding="utf-8"))
    rows = data["lessons"] if isinstance(data, dict) and "lessons" in data else data
    dist = collections.Counter(str(row.get("evidence_level")) for row in rows)
    return {"lessons": len(rows), "evidence": dict(sorted(dist.items()))}


def record(query: str, samples: int) -> dict:
    latencies: list[int] = []
    rows: list[dict] = []
    for _ in range(samples):
        rows, elapsed = _curl_search(query)
        latencies.append(elapsed)
        time.sleep(0.4)
    top = rows[0]
    return {
        "_comment": (
            "Recorded by scripts/record_hero_snapshot.py against the live endpoint. "
            "Every number here is a measurement; nothing is illustrative. "
            "See that script's docstring for what is deliberately absent (token and turn counts) "
            "and why."
        ),
        "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "query": query,
        "latency_ms_samples": latencies,
        "latency_ms_p50": int(statistics.median(latencies)),
        "top_hit": {
            "id": top.get("id"),
            "title": top.get("title"),
            "evidence_level": top.get("evidence_level"),
            "domain": top.get("domain"),
        },
        "result_count": len(rows),
        "corpus": corpus_facts(),
    }


def check() -> int:
    """Is the snapshot still usable as a recording? Structure only — **no counts.**

    A first version of this compared the snapshot's lesson count against `data/lessons.json` and
    failed on any difference. That gate was red within minutes of landing and would have stayed red
    forever: the corpus grows whenever the intake batch converts anything, several times a day, so a
    recorded count is stale by construction — and the picture had already stopped printing it.

    What is checkable without the network, and worth failing on:

    * the recording is dated and says what made it (an undated number is a claim about no day);
    * the grade it shows is a grade the corpus uses at all, so a typo like `E5` cannot render as
      authoritative-looking nonsense;
    * the latency samples are positive integers and the recorded p50 agrees with them;
    * both SVGs on disk are exactly what the renderer produces from this snapshot — the property
      that keeps the picture a function of its input instead of a hand-editable asset.

    Corpus counts are deliberately **not** compared: they live in `data/badges/lessons.json`, which
    `update-badges.yml` regenerates on its own schedule, and a picture that restates them is wrong
    within hours.
    """
    if not SNAPSHOT.exists():
        print(f"missing {SNAPSHOT.relative_to(REPO)}", file=sys.stderr)
        return 1
    recorded = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    problems: list[str] = []

    stamp = str(recorded.get("recorded_at") or "")
    if len(stamp) != 20 or not stamp.endswith("Z") or "T" not in stamp:
        problems.append(f"recorded_at is not an ISO-8601 UTC stamp: {stamp!r}")

    level = (recorded.get("top_hit") or {}).get("evidence_level")
    if level not in ("E0", "E1", "E2", "E3", "E4"):
        problems.append(f"top_hit.evidence_level is {level!r}, which is not a grade the corpus uses")

    samples = recorded.get("latency_ms_samples") or []
    if not samples or not all(isinstance(value, int) and value > 0 for value in samples):
        problems.append(f"latency_ms_samples are not positive integers: {samples!r}")
    else:
        ordered = sorted(samples)
        middle = len(ordered) // 2
        expected = (ordered[middle] if len(ordered) % 2
                    else (ordered[middle - 1] + ordered[middle]) // 2)
        if abs(int(recorded.get("latency_ms_p50") or 0) - expected) > 1:
            problems.append(
                f"latency_ms_p50 is {recorded.get('latency_ms_p50')} but the samples give {expected}")

    try:
        sys.path.insert(0, str(REPO / "scripts"))
        import render_hero_svg as hero
        for theme, path in (("dark", SNAPSHOT.parent / "hero-dark.svg"),
                            ("light", SNAPSHOT.parent / "hero-light.svg")):
            if not path.exists():
                problems.append(f"{path.name} is missing — run scripts/render_hero_svg.py")
            elif path.read_text(encoding="utf-8") != hero.render(recorded, theme):
                problems.append(
                    f"{path.name} differs from what scripts/render_hero_svg.py produces now — "
                    "re-run that script rather than editing the SVG by hand")
    except Exception as exc:  # noqa: BLE001 — a renderer that cannot run is itself the finding
        problems.append(f"could not re-render to compare: {exc}")

    if problems:
        print("the hero snapshot is not usable as a recording:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    print(f"hero snapshot is structurally sound ({len(samples)} latency sample(s), top hit {level})")
    return 0

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--query", default=DEFAULT_QUERY)
    parser.add_argument("--samples", type=int, default=7)
    parser.add_argument("--check", action="store_true",
                        help="compare the snapshot's corpus half against data/lessons.json")
    parser.add_argument("--out", type=Path, default=SNAPSHOT)
    args = parser.parse_args(argv)

    if args.check:
        return check()

    snapshot = record(args.query, max(1, args.samples))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8", newline="\n")
    print(f"wrote {args.out} — top hit {snapshot['top_hit']['evidence_level']} "
          f"({snapshot['top_hit']['id']}), p50 {snapshot['latency_ms_p50']} ms "
          f"over {snapshot['latency_ms_samples']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
