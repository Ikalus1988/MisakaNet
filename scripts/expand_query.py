#!/usr/bin/env python3
"""Query alias / near-synonym expansion for MisakaNet retrieval (stdlib only).

Table: data/query-aliases.json — sibling of data/domains.json, hand-maintained.
Design + measurements: docs/maintainer/query-alias-design-2026-09-16.md

    --query "如何切换识图模型"  expand a query   --check   CI gate (exit != 0)
    --list-kinds               kinds + counts   --json    machine output
    --emit-worker-table        the Worker's inlined copy of this table (issue #1780)

This module is the *single* expansion implementation for the local CLI
(`search_knowledge.py`, `misakanet.search.engine._expand_query`) and it is ported 1:1
to JavaScript in `workers/register-proxy-sw.js`; both read data/query-aliases.json, and
workers/query-alias-expansion.test.mjs fails if the JS port ever disagrees with this
file. Runtime callers use `expand_query_text()` and the shared off-switch
`query_aliases_enabled()` (`MISAKANET_QUERY_ALIASES=0`).

Does not import the misakanet package: `tokenize` mirrors engine._tokenize (Latin
run = 1 token, CJK char = 1 token) and `worker_tokens` mirrors the Worker's
`bm25Tokenize`, the tokenizer that drops CJK and swallows Chinese queries today.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from itertools import groupby, zip_longest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_TABLE = REPO / "data" / "query-aliases.json"
LESSONS = REPO / "lessons"
MAX_EXPANSIONS = 4      # default cap; sweep in the design doc (2..6 all within noise)
REQUIRED_KINDS = {"zh-en", "error-variant", "tool-variant", "product-variant", "abbrev", "typo",
                  # #1780: the migrated Feature #532 word list. It is a *degradation* layer —
                  # see `related` in the table's `kinds` — so it must be documented like the rest.
                  "related"}
RELATED_KIND = "related"

# Rollback switch (issue #1780). Default ON; `MISAKANET_QUERY_ALIASES=0`, or
# false/off/no, restores the pre-#1780 behaviour everywhere (Worker, CLI, engine)
# without a redeploy. Keep this set in sync with `queryAliasEnabled` in
# workers/register-proxy-sw.js.
QUERY_ALIASES_ENV = "MISAKANET_QUERY_ALIASES"
_OFF_VALUES = ("0", "false", "off", "no")
_TOKEN_RE = re.compile(r"[a-zA-Z\u00c0-\u024f0-9_]+|[\u4e00-\u9fff]")
# Same set as the worker's BM25_STOPWORDS; used only to reject useless expansions.
_STOP_EN = set((
    "the be to of and a in that have i it for not on with he as you do at this but his by from "
    "they we say her she or an will my one all would there their what so up out if about who get "
    "which go me when make can like time no just him know take people into year your good some "
    "could them see other than then").split())


class TableError(Exception):
    """The alias table is malformed, or an entry cannot be justified."""


def tokenize(text: str) -> list[str]:
    """Mirror engine._tokenize: one token per Latin run, one per CJK char."""
    spaced = re.sub(r"([\u4e00-\u9fff])", r" \1 ", text.lower())
    return [t.strip("_") for t in _TOKEN_RE.findall(spaced) if t.strip("_")]


def worker_tokens(text: str) -> list[str]:
    """Port of workers/register-proxy-sw.js `bm25Tokenize`: drops CJK (every
    non-[a-z0-9] is a separator) and stopwords, so a Chinese query reaches
    searchLessonsBM25 with zero terms and returns [] before scoring. An expansion
    that tokenizes to [] here is worth nothing in production, which is why
    `check` rejects it.
    """
    low = text.lower()
    base = [t for t in re.split(r"[^a-z0-9]+", low) if len(t) >= 2 and t not in _STOP_EN]
    joins = [c.replace("-", "") for c in re.findall(r"[a-z0-9]+-[a-z0-9]+", low)]
    return list(dict.fromkeys(base + [j for j in joins if len(j) >= 2]))


def load_table(path=DEFAULT_TABLE) -> dict:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise TableError(f"alias table not found: {path}")
    except json.JSONDecodeError as exc:
        raise TableError(f"alias table is not valid JSON: {exc}")
    if not (isinstance(data, dict) and "schema" in data and isinstance(data.get("aliases"), list)):
        raise TableError("alias table must be an object with `schema` and a list `aliases`")
    return data


def entry_defaults(table: dict, entry: dict) -> dict:
    """Fill direction/weight/replace from `kinds`; an entry may override any of them."""
    spec = table.get("kinds", {}).get(entry.get("kind"))
    if not isinstance(spec, dict):
        raise TableError(f"alias {entry.get('alias')!r}: unknown kind {entry.get('kind')!r}")
    out = dict(entry)
    for field in ("direction", "weight", "replace"):
        out.setdefault(field, spec.get(field))
    return out


def build_lookup(table: dict, only_related: bool | None = None) -> list[tuple[str, dict]]:
    """(needle, entry) pairs, longest first. Matching is raw text, not tokens: a CJK
    term has no token boundary either tokenizer can see.

    `only_related` selects the layer: None → every entry (the whole word list, what a
    caller asking for "the table" expects), False → the translating kinds only, True →
    only `related` entries (the degradation layer, see `expand`).
    """
    pairs = []
    for raw in table["aliases"]:
        e = entry_defaults(table, raw)
        if only_related is not None and (e["kind"] == RELATED_KIND) != only_related:
            continue
        pairs += [(e["alias"], e)] + ([(e["canonical"], e)] if e["direction"] == "two-way" else [])
    return sorted(pairs, key=lambda p: (-len(p[0]), p[0]))


# A "word character" for boundary purposes: the same alphabet the Worker's bm25Tokenize
# splits on, so an alias edge that is Latin must not sit inside a longer token.
_WORD_CHAR_RE = re.compile(r"[a-z0-9]")


def _on_word_boundaries(text: str, start: int, needle: str) -> bool:
    """True when a match of `needle` at `start` in the lower-cased `text` sits on word
    boundaries at both ends — or when the needle's edge is not Latin at all.

    CJK, `-`, `/` and spaces have no word boundary for either tokenizer, so those keep
    substring matching (`识图模型` must still beat the bare `模型`, `tools/list` must still
    match). Without this check `pat` matched inside `path`, `pr` inside `proxy` and `sse`
    inside `assets`, each injecting an unrelated expansion.
    """
    end = start + len(needle)
    def latin_edge(ch: str) -> bool:
        return bool(_WORD_CHAR_RE.match(ch.lower()))
    if latin_edge(needle[0]) and start > 0 and _WORD_CHAR_RE.match(text[start - 1].lower()):
        return False
    if latin_edge(needle[-1]) and end < len(text) and _WORD_CHAR_RE.match(text[end].lower()):
        return False
    return True


def _match(query: str, lookup: list[tuple[str, dict]], query_tokens: set[str]) -> tuple[list[dict], list]:
    """Entries of `lookup` that occur in `query`, plus the character spans they claimed."""
    matched: list[dict] = []
    spans: list[tuple[int, int]] = []
    target = query.lower()
    for needle, e in lookup:
        low = needle.lower()
        start = 0
        # A two-way entry matches from either side; inject the *other* side, so
        # `node` adds `nodejs` instead of repeating the word it already has.
        add_from = e["alias"] if low == e["canonical"].lower() else e["canonical"]
        new_terms = [t for t in tokenize(add_from) if t not in query_tokens]
        while True:
            i = target.find(low, start)
            if i < 0:
                break
            if not _on_word_boundaries(target, i, needle):
                # `pat` inside `path`, `pr` inside `proxy`, `sse` inside `assets`,
                # `rag` inside `storage`: raw substring matching injected a completely
                # unrelated expansion into those queries (found while wiring #1780 —
                # `path traversal` added `personal access token`). CJK is exempt below
                # because neither tokenizer has a word boundary to offer there.
                start = i + 1
                continue
            span = (i, i + len(needle))
            # A `replace` match that injects nothing new only deletes text: the typo
            # `powershel` sits inside the correct `powershell`.
            if e["replace"] and not new_terms:
                start = i + len(needle)
                continue
            if not any(a < span[1] and span[0] < b for a, b in spans):
                spans.append(span)
                fields = ("alias", "canonical", "kind", "weight", "replace")
                matched.append(dict({k: e[k] for k in fields}, span=span, add_from=add_from))
            start = i + len(needle)
    return matched, spans


def expand(query: str, table: dict, max_expansions: int = MAX_EXPANSIONS,
           keep_original: bool = False) -> dict:
    """Expand `query`; `expanded` is the string to hand to a BM25 search.

    Two layers, in this order (#1780 unification):
      1. the translating kinds (zh-en / error-variant / tool-variant / product-variant /
         abbrev / typo) — each entry claims "the query writes X, the corpus writes Y for
         the same thing", and each carries per-entry evidence;
      2. `related` — the migrated Feature #532 word list, which claims only co-occurrence
         ("questions about pip are usually answered by lessons mentioning ssl/proxy").
    Layer 2 runs **only when layer 1 matches nothing**. Unconditionally combining them
    measurably costs precision (engine top-1 14/20 → 12/20 on the eval set: broad
    co-occurring terms outrank the lesson the precise alias had already located), while
    as a fallback it adds behaviour where the alias table is silent and removes none.
    """
    # Match BEFORE removing stopwords: aliases may contain a stopword themselves
    # (`握手失败` contains `失败`), and stripping first destroys the phrase.
    query_tokens = set(tokenize(query))
    matched, spans = _match(query, build_lookup(table, only_related=False), query_tokens)
    related_fallback = False
    if not matched:
        matched, spans = _match(query, build_lookup(table, only_related=True), query_tokens)
        related_fallback = bool(matched)
    stopped = sorted(table.get("stopwords", {}).get("zh", []), key=len, reverse=True)
    action = ["free"] * len(query)             # free | keep (alias matched) | drop
    for m in matched:
        act = "drop" if (m["replace"] and not keep_original) else "keep"
        action[m["span"][0]:m["span"][1]] = [act] * (m["span"][1] - m["span"][0])
    removed, pieces = [], []
    for act, group in groupby(zip(action, query), key=lambda p: p[0]):
        segment = "".join(ch for _, ch in group)
        if act == "free":                      # intent words only leave the free text
            for word in stopped:
                if word in segment:
                    segment = segment.replace(word, " ")
                    removed.append(word)
        pieces.append("" if act == "drop" else segment)
    kept = "".join(pieces)
    # Round-robin across the matched aliases (heaviest first) so one long canonical
    # cannot eat the budget: `识图模型 切换` keeps both `vision` and `switch`.
    present, queues, origin = set(tokenize(kept)), [], {}
    for m in sorted(matched, key=lambda m: (-m["weight"], -len(m["canonical"]))):
        terms = [t for t in tokenize(m["add_from"])
                 if t not in present and t not in _STOP_EN and len(t) >= 2]
        for t in terms:
            origin.setdefault(t, m)
        if terms:
            queues.append(terms)
    interleaved = dict.fromkeys(t for group in zip_longest(*queues) for t in group if t)
    added = [{"term": t, "from": origin[t]["alias"], "kind": origin[t]["kind"],
              "weight": origin[t]["weight"]} for t in list(interleaved)[:max_expansions]]
    total = sum(1 for m in matched for t in tokenize(m["add_from"])
                if t not in _STOP_EN and len(t) >= 2)
    dropped = sorted({m["alias"] for m in matched if m["replace"] and not keep_original})
    expanded = (" ".join(tokenize(kept)) + " " + " ".join(t["term"] for t in added)).strip()
    for m in matched:
        m.pop("span")
        m.pop("add_from")
    return {"query": query, "stopwords_removed": removed, "matched": matched,
            "related_fallback": related_fallback,
            "dropped_terms": [] if keep_original else dropped, "added_terms": added,
            "added_terms_suppressed": max(0, total - len(added)), "expanded": expanded,
            "worker_tokens": worker_tokens(expanded),
            "changed": expanded != " ".join(tokenize(query))}


def query_aliases_enabled(value: str | None = None) -> bool:
    """Is query-side alias expansion on? Default ON (#1780).

    `MISAKANET_QUERY_ALIASES=0` (also `false` / `off` / `no`) turns it off — the same
    switch name and the same accepted values as `queryAliasEnabled` in
    workers/register-proxy-sw.js, so one variable rolls back both paths. Anything else
    (unset, empty, `1`, garbage) leaves expansion on: the switch exists for an
    incident, not as a configuration surface.
    """
    raw = os.environ.get(QUERY_ALIASES_ENV) if value is None else value
    if raw is None or not str(raw).strip():
        return True
    return str(raw).strip().lower() not in _OFF_VALUES


_TABLE_CACHE: dict = {"key": None, "table": None}


def cached_table(path: Path | str = DEFAULT_TABLE) -> dict:
    """`load_table`, memoised on (path, mtime, size). The table is read on every search
    (`engine._expand_query`), and re-parsing ~130 KB per query is not free; any edit to
    the file changes mtime and is picked up on the next call, so there is no restart
    window where the word list is stale."""
    p = Path(path)
    try:
        st = p.stat()
    except OSError as exc:
        raise TableError(f"alias table not found: {path}") from exc
    key = (str(p.resolve()), st.st_mtime_ns, st.st_size)
    if _TABLE_CACHE["key"] != key:
        _TABLE_CACHE.update(key=key, table=load_table(p))
    return _TABLE_CACHE["table"]


def expand_query_text(query: str, table: dict | None = None,
                      max_expansions: int = MAX_EXPANSIONS,
                      keep_original: bool = False) -> str:
    """The string to score: `expand(...)["expanded"]`, or `query` unchanged.

    This is the entry point runtime callers use (the local CLI and
    `engine._expand_query`), and it never raises: a missing or unreadable table means
    "no expansion", because a search must not fail over a word list. A malformed table
    is caught in CI by `--check`, not at query time.
    """
    if not query:
        return query
    try:
        t = cached_table() if table is None else table
        return expand(query, t, max_expansions=max_expansions,
                      keep_original=keep_original)["expanded"]
    except (TableError, OSError):
        return query


def worker_table(table: dict) -> dict:
    """The projection workers/register-proxy-sw.js inlines (`QUERY_ALIAS_TABLE`).

    A Worker cannot read a file at runtime, so the shared word list travels as a
    generated constant. `--emit-worker-table` prints exactly this object, and
    workers/query-alias-expansion.test.mjs recomputes it from data/query-aliases.json
    and fails if the inlined copy has drifted — the file stays the single source.
    Evidence blocks and prose are dropped: the Worker needs matching behaviour, not the
    review trail.
    """
    aliases = []
    for raw in table["aliases"]:
        e = entry_defaults(table, raw)
        aliases.append({"alias": e["alias"], "canonical": e["canonical"], "kind": e["kind"],
                        "direction": e["direction"], "weight": e["weight"],
                        "replace": e["replace"]})
    return {"version": table.get("schema", {}).get("version"),
            "stopwords_zh": list(table.get("stopwords", {}).get("zh", [])),
            "kinds": {k: {f: spec.get(f) for f in ("direction", "weight", "replace")}
                      for k, spec in table["kinds"].items()},
            "aliases": aliases}


def check(table_path=DEFAULT_TABLE) -> list[str]:
    """Validate schema + invariants. Returns problems; an empty list means OK.

    Invariants checked here: well-formed JSON and schema, known kind, unique alias,
    no self-map, no token-level no-op, canonical resolvable in lessons/ and surviving
    the worker tokenizer, and a terminating canonical chain. Every evidence citation is
    re-verified by tests/test_query_aliases.py, which CI runs together with this gate.
    """
    try:
        table = load_table(table_path)
    except TableError as exc:
        return [str(exc)]
    kinds = table.get("kinds")
    if not isinstance(kinds, dict) or not kinds:
        return ["`kinds` must be a non-empty object documenting every kind"]
    bad = [f"kind {k!r} is required but missing from `kinds`"
           for k in sorted(REQUIRED_KINDS - set(kinds))]
    seen, entries = {}, []
    for raw in table["aliases"]:
        if not isinstance(raw, dict):
            bad.append(f"alias entry is not an object: {raw!r}")
            continue
        alias, canonical = raw.get("alias"), raw.get("canonical")
        if not isinstance(alias, str) or not alias.strip():
            bad.append(f"entry without a usable `alias`: {raw!r}")
            continue
        if not isinstance(canonical, str) or not canonical.strip():
            bad.append(f"alias {alias!r}: missing `canonical`")
            continue
        key = alias.strip().lower()
        for cond, msg in (
                (key != canonical.strip().lower(), f"alias {alias!r} maps to itself"),
                (key not in seen, f"duplicate alias {alias!r} (also maps to {seen.get(key)!r})"),
                (raw.get("kind") in kinds, f"alias {alias!r}: unknown kind {raw.get('kind')!r}"),
                (isinstance(raw.get("justification"), dict),
                 f"alias {alias!r}: missing `justification` evidence block"),
                (raw.get("direction") in (None, "one-way", "two-way"),
                 f"alias {alias!r}: direction must be one-way or two-way")):
            if not cond:
                bad.append(msg)
        seen[key] = canonical
        try:
            entries.append(entry_defaults(table, raw))
        except TableError as exc:
            bad.append(str(exc))
    corpus = set(tokenize("\n".join(p.read_text(encoding="utf-8", errors="replace")
                                    for p in sorted(LESSONS.rglob("*.md")))))
    by_alias = {e["alias"].strip().lower(): e["canonical"].strip().lower() for e in entries}
    for e in entries:
        alias, canonical = e["alias"], e["canonical"]
        toks = tokenize(canonical)
        if not toks:
            bad.append(f"alias {alias!r}: canonical {canonical!r} has no tokens")
        bad += [f"alias {alias!r}: canonical token {t!r} is not in lessons/ "
                "(maps to a nonexistent canonical form)" for t in toks if t not in corpus]
        if not worker_tokens(canonical):
            bad.append(f"alias {alias!r}: canonical {canonical!r} has no token left after the "
                       "worker tokenizer — the expansion would never reach the index")
        chain, cur = [alias.strip().lower()], canonical.strip().lower()
        while cur in by_alias and cur not in chain:   # a canonical chain must terminate
            chain.append(cur)
            cur = by_alias[cur]
        if cur in by_alias:
            bad.append(f"alias {alias!r}: canonical chain loops at {cur!r}")
    return bad


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="MisakaNet query alias expansion")
    ap.add_argument("--query", "-q", help="query to expand")
    ap.add_argument("--check", action="store_true", help="validate the alias table")
    ap.add_argument("--list-kinds", action="store_true", help="list alias kinds")
    ap.add_argument("--emit-worker-table", action="store_true",
                    help="print the projection workers/register-proxy-sw.js inlines "
                         "(QUERY_ALIAS_TABLE); --pretty for a human-readable dump")
    ap.add_argument("--table", default=str(DEFAULT_TABLE), help="alias table path")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--pretty", action="store_true", help="indent --emit-worker-table")
    ap.add_argument("--max-expansions", type=int, default=MAX_EXPANSIONS)
    ap.add_argument("--keep-original", action="store_true",
                    help="keep tokens that `replace` kinds would drop")
    args = ap.parse_args(argv)
    try:
        table = load_table(Path(args.table))
    except TableError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.emit_worker_table:
        # No trailing newline surprises: this is pasted into a JS constant.
        print(json.dumps(worker_table(table), ensure_ascii=False,
                         indent=2 if args.pretty else None,
                         separators=None if args.pretty else (",", ":")))
        return 0
    if args.list_kinds:
        counts: dict[str, int] = {}
        for e in table["aliases"]:
            counts[e.get("kind")] = counts.get(e.get("kind"), 0) + 1
        for kind, spec in table["kinds"].items():
            print(f"{kind:16s} n={counts.get(kind, 0):<4d} {spec.get('direction')}"
                  f"/w{spec.get('weight')}/replace={spec.get('replace')}\n"
                  f"                 {spec.get('desc', '')}")
        print(f"{'TOTAL':16s} {len(table['aliases'])} entries")
        return 0
    if args.check:
        bad = check(Path(args.table))
        if bad:
            print(f"❌ {args.table}: {len(bad)} problem(s)")
            print("\n".join(f"  - {b}" for b in bad))
            return 1
        print(f"✅ {args.table}: {len(table['aliases'])} aliases, {len(table['kinds'])} kinds, "
              f"schema v{table['schema'].get('version')}")
        return 0
    if not args.query:
        ap.print_help()
        return 2
    rep = expand(args.query, table, max_expansions=args.max_expansions,
                 keep_original=args.keep_original)
    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        return 0
    rows = [("original", [rep["query"]]),
            ("stopwords", rep["stopwords_removed"]),
            ("expanded", [rep["expanded"] or "(empty)"]),
            ("dropped", rep["dropped_terms"]),
            ("matched", [f"{m['alias']} -> {m['canonical']} [{m['kind']}, "
                         f"{'replace' if m['replace'] else 'append'}, w={m['weight']}]"
                         for m in rep["matched"]]),
            ("added", [f"{t['term']} (from {t['from']}, w={t['weight']})"
                       for t in rep["added_terms"]])]
    if rep["added_terms_suppressed"]:
        rows.append(("capped", [f"{rep['added_terms_suppressed']} term(s) suppressed"]))
    for label, values in rows:
        if values:
            print(f"  {label:9s}: " + ", ".join(values))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
