#!/usr/bin/env python3
"""Embed a JSON array with Workers AI `bge-m3` — the model production already serves.

Why this exists (2026-10-27)
----------------------------
`docs/benchmarks/embedding-ab-2026-10-27.md` compared retrieval by pure cosine over
`gemini-embedding-001` against the live path, and had to state a hole it could not fill: the
`bge-m3` arm — the vectors the worker actually uses — was "not reachable from outside the worker",
so the comparison was "a new model vs the system as delivered", not "new model vs current model".
Without that arm the report could rank a ceiling but not choose a lever.

It is reachable. Workers AI exposes `bge-m3` over the REST API, and this is the run that filled the
hole: 651 lessons + 267 queries, 1024 dimensions, the same corpus and query set as the other arms.

What it changed: `bge-m3` pure cosine scores **R@1 0.689** overall and **0.636** on the cross-lingual
bucket, against the live path's **0.455** on the same queries. The gate that keeps the vector path
from running is worth ~18 points; swapping to a stronger embedding is worth ~9. That is the finding
this script exists to keep reproducible.

Usage
-----
    python3 scripts/embed_workers_ai.py --in corpus.json --out vectors.jsonl
    python3 scripts/embed_workers_ai.py --in queries.json --out q.jsonl --field query --id-field lesson_id

Resumable, batched, and it retries the transport failures this endpoint and a home proxy produce.
The token is read from `CLOUDFLARE_API_TOKEN` or `--token-file`, and is never printed.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

MODEL = "@cf/baai/bge-m3"
DEFAULT_ACCOUNT = "6b92325b505f2b76aec49e9fe4195d31"
DEFAULT_TOKEN_FILE = Path("/mnt/c/Users/Eric Jia/MisakaNet/.cache/cf_api_token")
# 10 texts of up to 6000 characters is what this endpoint accepts; 50 x 6000 is a 400 (measured
# 2026-10-27). The cap is on the request, not the model, so batching is the only lever.
BATCH = 10
# Direct, not through the environment proxy: api.cloudflare.com is reachable from here while the
# local https_proxy is up and down (measured: 400 without a proxy hop, SSL_ERROR_SYSCALL through it).
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def load_token(path: Path) -> str:
    value = (Path(path).read_text(encoding="utf-8").strip() if Path(path).exists() else "")
    if not value:
        raise SystemExit(f"error: no token at {path} (or set it in the file)")
    return value


def embed_batch(account: str, token: str, texts: list[str], timeout: float) -> list[list[float]]:
    request = urllib.request.Request(
        f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{MODEL}",
        data=json.dumps({"text": texts}).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    with OPENER.open(request, timeout=timeout) as response:
        body = json.loads(response.read().decode("utf-8"))
    vectors = body["result"]["data"]
    if len(vectors) != len(texts):
        raise ValueError(f"asked for {len(texts)} embeddings, got {len(vectors)}")
    return vectors


def embed_with_retry(account: str, token: str, texts: list[str], timeout: float,
                     attempts: int = 5) -> list[list[float]]:
    last: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return embed_batch(account, token, texts, timeout)
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError, KeyError) as exc:
            last = exc
            if attempt < attempts:
                time.sleep(2 ** (attempt - 1))
    raise RuntimeError(f"embed failed after {attempts} attempts: {last}") from last


def already_done(path: Path) -> set[str]:
    if not path.exists():
        return set()
    done: set[str] = set()
    for line in path.open(encoding="utf-8"):
        line = line.strip()
        if line:
            try:
                done.add(json.loads(line)["id"])
            except (ValueError, KeyError):
                continue  # a torn last line from an interrupted run is re-embedded, not trusted
    return done


def run(items: list[dict], out_path: Path, id_field: str, text_field: str, account: str, token: str,
        batch: int, timeout: float, log=sys.stderr) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    done = already_done(out_path)
    todo = [item for item in items if item[id_field] not in done]
    print(f"{out_path.name}: {len(done)} already embedded, {len(todo)} to go", file=log)
    written = 0
    with out_path.open("a", encoding="utf-8") as fh:
        for start in range(0, len(todo), batch):
            chunk = todo[start:start + batch]
            vectors = embed_with_retry(account, token, [c[text_field] for c in chunk], timeout)
            # The count is checked here as well as in `embed_batch`, because `zip` below would
            # silently truncate a short response into a short vector file — and a short vector file
            # scores as a recall regression, not as an error.
            if len(vectors) != len(chunk):
                raise RuntimeError(f"{len(vectors)} embeddings for {len(chunk)} texts")
            for item, vector in zip(chunk, vectors):
                fh.write(json.dumps({"id": item[id_field], "vector": vector}) + "\n")
                written += 1
            fh.flush()
            print(f"  {start // batch + 1}/{(len(todo) + batch - 1) // batch}: {len(chunk)} ids",
                  file=log)
    return written


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--in", dest="input_path", required=True, help="JSON array of objects")
    ap.add_argument("--out", dest="output_path", required=True, help="JSONL of {id, vector}")
    ap.add_argument("--field", default="text", help="field holding the text to embed")
    ap.add_argument("--id-field", default="id")
    ap.add_argument("--batch", type=int, default=BATCH)
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument("--account", default=DEFAULT_ACCOUNT)
    ap.add_argument("--token-file", default=str(DEFAULT_TOKEN_FILE))
    args = ap.parse_args(argv)

    items = json.loads(Path(args.input_path).read_text(encoding="utf-8"))
    written = run(items, Path(args.output_path), args.id_field, args.field, args.account,
                  load_token(Path(args.token_file)), args.batch, args.timeout)
    print(f"wrote {written} vectors to {args.output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
