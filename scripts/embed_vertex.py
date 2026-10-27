#!/usr/bin/env python3
"""Embed a JSON array with `gemini-embedding-001` on Vertex AI, one JSONL line per row.

Why this exists (2026-10-27)
----------------------------
The offline retrieval A/B needs both arms on the same corpus: lexical (BM25, already in this repo)
and embedding. That means a vector for every lesson and every query, produced once, cached outside
the repo, and reused by the harness — an A/B whose vectors change between runs measures the harness,
not the retriever.

The shapes are fixed and the environment is not a generic one, so this is a small program with a long
memory:

* **`:predict` is the only endpoint that works.** `publishers/google/models/<model>:countTokens` and
  the model read/list endpoints answer `404` for these models on this endpoint. Do not "clean this
  up" into a discovery-style call: `instances -> predictions` is the only shape that returns vectors.
* **Egress here is proxy-only.** `https_proxy` points at the machine's local proxy, and stdlib
  `urllib` installs the environment proxy handler by default — which is why this uses `urllib` rather
  than `requests`, a raw socket, or a hand-rolled `http.client` connection. The last two would bypass
  the proxy and hang. It also keeps the dependency list at stdlib. That proxy drops a chunked
  response mid-body regularly (observed: one dropped first attempt per batch, `IncompleteRead` or
  `RemoteDisconnected`); both are retried as the network errors they are, not treated as bugs.
* **The access token is a bearer credential.** It comes from `VERTEX_ACCESS_TOKEN` or
  `gcloud auth print-access-token` and is never printed, never put in a URL, and never interpolated
  into an error: the errors this script prints are meant to be pasteable into an issue.
* **A full corpus run is minutes through a consumer proxy**, so progress is durable. Every line is
  flushed as it is produced and a restart reads the output back and skips what is already there: a
  crash costs the current batch, not the run. A torn final line from a crash is repaired rather than
  appended to, because half a JSON object in the middle of an artifact is worse than a slow restart.
* **`--dims` maps to `parameters.outputDimensionality`**, and is omitted at the model default of 3072.
  gemini-embedding-001 is Matryoshka-trained: the smaller sizes are real truncated embeddings, which
  is what makes a cost/latency arm possible — but the default arm should carry the full vector.
* **`autoTruncate` is always on.** Inputs are bounded to 6000 characters upstream, but 6000 CJK
  characters can exceed the model's 2048-token input limit; without truncation those rows would 400
  and drop out of the artifact. The response carries `statistics.truncated`, counted in the summary,
  because a corpus arm embedded from truncated text is a fact the A/B write-up has to state.

Usage
-----
    # the offline A/B artifacts (3072-d, full vectors)
    python3 scripts/embed_vertex.py \\
        --in .cache/embed-ab/corpus.json \\
        --out .cache/embed-ab/vectors-lessons.jsonl --dims 3072
    python3 scripts/embed_vertex.py \\
        --in .cache/embed-ab/queries.json \\
        --out .cache/embed-ab/vectors-queries.jsonl \\
        --field query --id-field lesson_id --dims 3072

    # a smaller arm, and a re-run that only embeds what is missing
    python3 scripts/embed_vertex.py --in ... --out ... --dims 768
    python3 scripts/embed_vertex.py --in ... --out ...       # logs "resume: N ... skipped"

Credentials: `VERTEX_ACCESS_TOKEN` if set, else `gcloud auth print-access-token` (`--gcloud` or
`GCLOUD` picks the binary; `gcloud` on `PATH` by default). `--project` defaults to
`GOOGLE_CLOUD_PROJECT`, then to the project this bench's account uses.

Exit codes: `0` every row is in the output (written now or already present), `1` at least one batch
ultimately failed (the ids are listed at the end), `2` bad arguments or input.
"""

from __future__ import annotations

import argparse
import http.client
import json
import math
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO

DEFAULT_PROJECT = "project-2d6795e4-704d-4a4e-841"
DEFAULT_REGION = "us-central1"
DEFAULT_MODEL = "gemini-embedding-001"
DEFAULT_DIMS = 3072
DEFAULT_BATCH_SIZE = 50
DEFAULT_TIMEOUT = 180.0

# The only output sizes `outputDimensionality` accepts. Anything else is answered with a 400 whose
# text reads like a transient failure, so it is rejected here instead of being retried five times.
ALLOWED_DIMS = (3072, 2048, 1536, 1024, 768, 512, 256)
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
MAX_ATTEMPTS = 6
BASE_DELAY = 1.0
MAX_DELAY = 60.0

EmbedFn = Callable[[Sequence[str]], list["Embedding"]]


@dataclass(frozen=True)
class Embedding:
    """One prediction: the vector, plus what the API said about the text that produced it."""

    values: list[float]
    tokens: int | None = None
    truncated: bool = False


class PredictError(RuntimeError):
    """An embedding call that is over: retrying the same payload cannot make it succeed."""


class TransientResponseError(RuntimeError):
    """A response that arrived unusable (a body cut short); a fresh connection may do better."""


# ── request shape ───────────────────────────────────────────────────────────────────────────────────


def output_parameters(dims: int) -> dict[str, int]:
    """`parameters` entries for a requested size; empty at the model default.

    At 3072 the parameter is omitted rather than sent explicitly: the default path is the one that
    was verified against this endpoint, and an explicit `outputDimensionality: 3072` is a second shape
    nobody has tested.
    """
    if dims not in ALLOWED_DIMS:
        raise ValueError(
            f"dims must be one of {', '.join(str(d) for d in ALLOWED_DIMS)}; got {dims}"
        )
    return {} if dims == DEFAULT_DIMS else {"outputDimensionality": dims}


def build_payload(texts: Sequence[str], dims: int) -> dict[str, Any]:
    """The verified `:predict` body: one `content` instance per text, same order out."""
    return {
        "instances": [{"content": text} for text in texts],
        "parameters": {"autoTruncate": True, **output_parameters(dims)},
    }


def predict_url(project: str, region: str, model: str) -> str:
    return (
        f"https://{region}-aiplatform.googleapis.com/v1/projects/{project}/locations/{region}"
        f"/publishers/google/models/{model}:predict"
    )


def chunked(items: Sequence[Any], size: int) -> Iterator[list[Any]]:
    """Consecutive slices of at most `size`; the API pairs predictions to instances by position."""
    if size < 1:
        raise ValueError(f"batch size must be at least 1; got {size}")
    for start in range(0, len(items), size):
        yield list(items[start : start + size])


def backoff_delay(attempt: int) -> float:
    """1s, 2s, 4s, 8s, 16s, then capped. Deterministic on purpose: a retry log is reproducible."""
    return min(MAX_DELAY, BASE_DELAY * 2 ** (attempt - 1))


# ── credentials ────────────────────────────────────────────────────────────────────────────────────


def access_token(
    *,
    gcloud: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> str:
    """A bearer token from the environment, else from `gcloud`.

    The environment variable is the escape hatch for a caller that already holds a token; it is read,
    never written, and the value never leaves this function's return path into a log line.
    """
    env = os.environ if environ is None else environ
    token = env.get("VERTEX_ACCESS_TOKEN", "").strip()
    if token:
        return token

    binary = gcloud or env.get("GCLOUD") or "gcloud"
    try:
        completed = subprocess.run(
            [binary, "auth", "print-access-token"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        raise SystemExit(
            f"no access token: set VERTEX_ACCESS_TOKEN or install gcloud (tried {binary!r})"
        ) from None

    lines = completed.stdout.strip().splitlines()
    token = lines[-1].strip() if lines else ""
    if completed.returncode != 0 or not token:
        stderr_lines = completed.stderr.strip().splitlines()
        detail = stderr_lines[-1] if stderr_lines else f"exit status {completed.returncode}"
        raise SystemExit(f"`{binary} auth print-access-token` failed: {detail}")
    return token


# ── transport ──────────────────────────────────────────────────────────────────────────────────────


def _error_detail(exc: urllib.error.HTTPError) -> str:
    """The API's own message, truncated. Read from the body only — headers stay out of logs."""
    try:
        body = exc.read()
    except Exception:  # noqa: BLE001 - a body that cannot be read must not mask the status code
        return "<unreadable body>"
    text = body.decode("utf-8", "replace").strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return text[:400] or "<empty body>"
    error = parsed.get("error") if isinstance(parsed, dict) else None
    if isinstance(error, dict):
        return str(error.get("message") or error)[:400]
    return text[:400]


def _post_json(
    url: str,
    payload: Mapping[str, Any],
    *,
    token: str,
    project: str,
    timeout: float,
    urlopen: Callable[..., Any],
) -> Any:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "x-goog-user-project": project,
            "Content-Type": "application/json",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        body = response.read()
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise TransientResponseError(f"response body was not JSON ({exc})") from None


def parse_predictions(payload: Mapping[str, Any], *, expected: int, dims: int) -> list[Embedding]:
    """Vectors in request order, or a `PredictError` — never a silently short list.

    The output is joined to ids by position, so a missing prediction is not a degraded result: it is
    a misalignment where every later vector belongs to the wrong row. Refuse instead.
    """
    predictions = payload.get("predictions")
    if not isinstance(predictions, list):
        raise PredictError("response has no predictions list")
    if len(predictions) != expected:
        raise PredictError(f"expected {expected} predictions, got {len(predictions)}")

    parsed: list[Embedding] = []
    for index, prediction in enumerate(predictions):
        embeddings = prediction.get("embeddings") if isinstance(prediction, Mapping) else None
        values = embeddings.get("values") if isinstance(embeddings, Mapping) else None
        if not isinstance(values, list) or not values:
            raise PredictError(f"prediction {index} has no values")
        try:
            vector = [float(value) for value in values]
        except (TypeError, ValueError):
            raise PredictError(f"prediction {index} has a non-numeric value") from None
        if len(vector) != dims:
            raise PredictError(f"prediction {index} has {len(vector)} dims, expected {dims}")
        if not all(math.isfinite(value) for value in vector):
            raise PredictError(f"prediction {index} contains a non-finite value")
        statistics = embeddings.get("statistics")
        statistics = statistics if isinstance(statistics, Mapping) else {}
        token_count = statistics.get("token_count")
        parsed.append(
            Embedding(
                values=vector,
                tokens=int(token_count) if isinstance(token_count, int) else None,
                truncated=bool(statistics.get("truncated", False)),
            )
        )
    return parsed


def request_embeddings(
    texts: Sequence[str],
    *,
    token: str,
    project: str,
    region: str,
    model: str,
    dims: int,
    timeout: float = DEFAULT_TIMEOUT,
    attempts: int = MAX_ATTEMPTS,
    sleep: Callable[[float], None] | None = None,
    urlopen: Callable[..., Any] | None = None,
    log: TextIO | None = None,
) -> list[Embedding]:
    """One batch, retried on 429/5xx/network errors and truncated bodies; other failures stop.

    `429` is in the retryable set because the per-minute token quota is the likely limit for 50 long
    lessons, and that is a wait, not a bug. A `400` is neither: it is the body saying the payload is
    wrong, and five more copies of a wrong payload only delay the error.
    """
    if not texts:
        return []

    log = sys.stderr if log is None else log
    url = predict_url(project, region, model)
    payload = build_payload(texts, dims)
    sleep = time.sleep if sleep is None else sleep
    opener = urllib.request.urlopen if urlopen is None else urlopen

    detail = "no attempt was made"
    for attempt in range(1, attempts + 1):
        try:
            raw = _post_json(
                url, payload, token=token, project=project, timeout=timeout, urlopen=opener
            )
        except urllib.error.HTTPError as exc:
            status = exc.code
            detail = f"HTTP {status}: {_error_detail(exc)}"
            if status not in RETRYABLE_STATUS:
                raise PredictError(detail) from None
        except (OSError, http.client.HTTPException) as exc:
            # URLError/timeouts/proxy resets (OSError), and a chunked body cut short
            # (IncompleteRead) or a mangled status line (BadStatusLine), which are HTTPException.
            detail = f"network error: {getattr(exc, 'reason', exc)}"
        except TransientResponseError as exc:
            detail = f"bad response: {exc}"
        else:
            return parse_predictions(raw, expected=len(texts), dims=dims)

        if attempt == attempts:
            break
        delay = backoff_delay(attempt)
        print(
            f"  attempt {attempt}/{attempts} failed ({detail}); retrying in {delay:.0f}s",
            file=log,
            flush=True,
        )
        sleep(delay)

    raise PredictError(f"gave up after {attempts} attempts ({detail})")


# ── input and durable output ───────────────────────────────────────────────────────────────────────


def load_rows(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"{path} is not a JSON array (found {type(payload).__name__})")
    return payload


def prepare_rows(
    rows: Sequence[Mapping[str, Any]], *, id_field: str, field: str
) -> list[tuple[str, str]]:
    """`(id, text)` pairs, validated before the first request rather than at batch 7.

    Ids must be unique: the id is the resume key, so a duplicate would be skipped as "already done"
    and silently drop a row from the artifact.
    """
    pairs: list[tuple[str, str]] = []
    seen: dict[str, int] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise ValueError(f"row {index} is not a JSON object")
        if field not in row:
            raise ValueError(f"row {index} has no {field!r} field")
        if id_field not in row:
            raise ValueError(f"row {index} has no {id_field!r} field")
        text = row[field]
        row_id = row[id_field]
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"row {index} has an empty or non-string {field!r}")
        if not isinstance(row_id, str) or not row_id.strip():
            raise ValueError(f"row {index} has an empty or non-string {id_field!r}")
        if row_id in seen:
            raise ValueError(
                f"duplicate id {row_id!r} at rows {seen[row_id]} and {index}: "
                f"{id_field!r} must be unique, it is the resume key"
            )
        seen[row_id] = index
        pairs.append((row_id, text))
    return pairs


def read_done(out_path: Path, *, log: TextIO | None = None) -> set[str]:
    """Ids already in `out_path`, repairing a torn final line left by a crash.

    Each line is written and flushed whole, but a process killed between the write and the flush can
    leave half a JSON object. Appending after that would make the artifact unreadable from the middle
    on, so unreadable lines are dropped and the file is rewritten with the good ones.
    """
    if not out_path.exists():
        return set()

    log = sys.stderr if log is None else log

    done: set[str] = set()
    good_lines: list[str] = []
    dropped = 0
    with out_path.open("r", encoding="utf-8") as handle:
        for raw in handle:
            line = raw.rstrip("\n")
            try:
                record = json.loads(line)
                row_id = record["id"]
                if not isinstance(row_id, str):
                    raise TypeError("id is not a string")
            except (json.JSONDecodeError, KeyError, TypeError):
                if line.strip():
                    dropped += 1
                continue
            done.add(row_id)
            good_lines.append(line)

    if dropped:
        repaired = out_path.with_name(out_path.name + ".repair")
        repaired.write_text("\n".join(good_lines) + ("\n" if good_lines else ""), encoding="utf-8")
        repaired.replace(out_path)
        print(
            f"resume: repaired {out_path.name}, dropped {dropped} unreadable line(s)",
            file=log,
            flush=True,
        )
    return done


@dataclass
class RunStats:
    total: int
    skipped: int
    written: int
    failed_ids: list[str]
    tokens: int
    truncated: int


def embed_file(
    *,
    rows: Sequence[Mapping[str, Any]],
    out_path: Path,
    id_field: str,
    field: str,
    dims: int,
    batch_size: int,
    embed: EmbedFn,
    log: TextIO | None = None,
) -> RunStats:
    """Embed every row whose id is not in `out_path` yet, flushing one line at a time.

    A failed batch is skipped, not fatal: the other twelve batches are still valid work, and the
    missing ids are reported at the end so a re-run picks up exactly those.
    """
    log = sys.stderr if log is None else log
    pairs = prepare_rows(rows, id_field=id_field, field=field)
    done = read_done(out_path, log=log)
    pending = [(row_id, text) for row_id, text in pairs if row_id not in done]
    skipped = len(pairs) - len(pending)
    print(
        f"resume: {skipped} of {len(pairs)} ids already in {out_path}; {len(pending)} to embed",
        file=log,
        flush=True,
    )

    stats = RunStats(
        total=len(pairs), skipped=skipped, written=0, failed_ids=[], tokens=0, truncated=0
    )
    if not pending:
        return stats

    batches = list(chunked(pending, batch_size))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("a", encoding="utf-8") as handle:
        for index, batch in enumerate(batches, start=1):
            # The count is rows covered, cumulative, so a line is enough to see where a run is.
            covered = min(index * batch_size, len(pending))
            print(f"batch {index}/{len(batches)} {covered} ids", file=log, flush=True)
            try:
                embeddings = embed([text for _, text in batch])
            except PredictError as exc:
                print(f"  FAILED batch {index}/{len(batches)}: {exc}", file=log, flush=True)
                stats.failed_ids.extend(row_id for row_id, _ in batch)
                continue
            if len(embeddings) != len(batch):
                print(
                    f"  FAILED batch {index}/{len(batches)}: "
                    f"{len(embeddings)} vectors for {len(batch)} rows",
                    file=log,
                    flush=True,
                )
                stats.failed_ids.extend(row_id for row_id, _ in batch)
                continue

            for (row_id, _), embedding in zip(batch, embeddings):
                if len(embedding.values) != dims:
                    raise ValueError(
                        f"embed() returned {len(embedding.values)} dims for {row_id!r}, "
                        f"expected {dims}"
                    )
                record: dict[str, Any] = {"id": row_id, "vector": embedding.values}
                if embedding.tokens is not None:
                    record["tokens"] = embedding.tokens
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                handle.flush()
                stats.written += 1
                stats.tokens += embedding.tokens or 0
                stats.truncated += 1 if embedding.truncated else 0
    return stats


# ── CLI ────────────────────────────────────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="embed_vertex.py",
        description=(
            "Embed a JSON array with gemini-embedding-001 on Vertex AI. Writes one "
            '{"id", "vector"[, "tokens"]} JSON object per line, resumable via that id.'
        ),
    )
    parser.add_argument(
        "--in",
        dest="input_path",
        required=True,
        type=Path,
        help="JSON array of objects (the corpus or the query set)",
    )
    parser.add_argument(
        "--out",
        dest="out_path",
        required=True,
        type=Path,
        help="JSONL destination; existing ids there are skipped",
    )
    parser.add_argument(
        "--field", default="text", help="object field holding the text to embed (default: text)"
    )
    parser.add_argument(
        "--id-field", default="id", help="object field holding the output id (default: id)"
    )
    parser.add_argument(
        "--dims",
        type=int,
        default=DEFAULT_DIMS,
        help=f"outputDimensionality, one of {ALLOWED_DIMS} (default: {DEFAULT_DIMS})",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"instances per request (default: {DEFAULT_BATCH_SIZE})",
    )
    parser.add_argument(
        "--model", default=DEFAULT_MODEL, help=f"embedding model (default: {DEFAULT_MODEL})"
    )
    parser.add_argument(
        "--project",
        default=os.environ.get("GOOGLE_CLOUD_PROJECT", DEFAULT_PROJECT),
        help="GCP project (default: $GOOGLE_CLOUD_PROJECT, then the bench project)",
    )
    parser.add_argument(
        "--region", default=DEFAULT_REGION, help=f"Vertex region (default: {DEFAULT_REGION})"
    )
    parser.add_argument(
        "--gcloud",
        default=None,
        help="gcloud binary used for auth (default: $GCLOUD, then 'gcloud')",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"per-request timeout in seconds (default: {DEFAULT_TIMEOUT:.0f})",
    )
    parser.add_argument(
        "--attempts",
        type=int,
        default=MAX_ATTEMPTS,
        help=f"attempts per batch before it is reported missing (default: {MAX_ATTEMPTS})",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.batch_size < 1:
        parser.error("--batch-size must be at least 1")
    if args.attempts < 1:
        parser.error("--attempts must be at least 1")
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    try:
        output_parameters(args.dims)
    except ValueError as exc:
        parser.error(str(exc))

    try:
        rows = load_rows(args.input_path)
        prepare_rows(rows, id_field=args.id_field, field=args.field)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    # The token is fetched on the first batch, not up front: a fully resumed run has nothing to
    # request and must not need credentials at all.
    token_holder: dict[str, str] = {}

    def embed(texts: Sequence[str]) -> list[Embedding]:
        if "token" not in token_holder:
            token_holder["token"] = access_token(gcloud=args.gcloud)
        return request_embeddings(
            texts,
            token=token_holder["token"],
            project=args.project,
            region=args.region,
            model=args.model,
            dims=args.dims,
            timeout=args.timeout,
            attempts=args.attempts,
        )

    started = time.monotonic()
    try:
        stats = embed_file(
            rows=rows,
            out_path=args.out_path,
            id_field=args.id_field,
            field=args.field,
            dims=args.dims,
            batch_size=args.batch_size,
            embed=embed,
        )
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    elapsed = time.monotonic() - started

    detail = f"wrote {stats.written} vectors, skipped {stats.skipped}"
    if stats.tokens:
        detail += f", {stats.tokens} input tokens"
    if stats.truncated:
        detail += f", {stats.truncated} truncated to the input limit"
    print(f"done in {elapsed:.1f}s: {detail}; {args.out_path}", file=sys.stderr, flush=True)

    if stats.failed_ids:
        print(f"missing ids ({len(stats.failed_ids)}):", file=sys.stderr)
        for row_id in stats.failed_ids:
            print(f"  {row_id}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
