"""Error-signature normalizer — stable recall of "same class of failures" (#1654).

Same function for lesson-side extraction (index build) and query-side extraction
(search time). Volatile artifacts (paths, timestamps, PIDs, addresses, ports,
instance ids) are replaced with placeholders; semantic tokens (exception classes,
errno, HTTP/exit codes) are preserved.

VERSIONED: bump SIGNATURE_NORM_VERSION when rules change so the index rebuilds.
"""
from __future__ import annotations

import hashlib
import re
from typing import Optional

# ── version gate ─────────────────────────────────────────────────────────────
SIGNATURE_NORM_VERSION = 1

# ── Phase 0: error-line extraction ──────────────────────────────────────────
# Prefer specific exception class; fall back to ERROR/FATAL; then exit code.
_TRACEBACK_EXC = re.compile(
    r"\b([A-Z]\w*(?:Error|Exception|Failure|Fault))\b"
)
_ERROR_FATAL = re.compile(r"\b(?:ERROR|FATAL|CRITICAL)\b[:\s]*(.+)", re.IGNORECASE)
_EXIT_CODE = re.compile(r"\bexit(?:ed)?\s+(?:with\s+)?code\s+(\d+)\b", re.IGNORECASE)
_HTTP_STATUS = re.compile(r"\b[45]\d{2}\b")
_ERRNO = re.compile(
    r"\b(?:EACCES|ECONNRESET|ECONNREFUSED|ETIMEDOUT|ENOSPC|EPERM|ENOENT|"
    r"EADDRINUSE|EADDRNOTAVAIL|EPIPE|EHOSTUNREACH|ENETUNREACH|EAGAIN|"
    r"EINTR|EFAULT|EBADF|EINVAL|EMFILE|ENFILE|ENOMEM|EIO|EBUSY|"
    r"ENOTDIR|EISDIR|EEXIST|ENOTEMPTY|ESPIPE|EROFS|EXDEV|ENODEV|EOVERFLOW|"
    r"EBROKENPIPE)\b",
    re.IGNORECASE,
)

# ── Phase 1: volatile-artifact strippers (ordered) ──────────────────────────
# Each: (compiled_regex, placeholder)
_STRIP_RULES: list[tuple[re.Pattern, str]] = []

def _add(pattern: str, placeholder: str, flags: int = 0) -> None:
    _STRIP_RULES.append((re.compile(pattern, flags), placeholder))

# URLs (must precede paths to avoid partial match)
_add(r"https?://\S+", "<URL>")
_add(r"git@[\w.-]+:[\w./-]+", "<URL>")

# ISO timestamps (must precede date-only and clock)
_add(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?", "<TS>")
_add(r"\d{4}[-/]\d{2}[-/]\d{2}", "<DATE>")

# Absolute paths (Windows C:\ and Unix /foo/bar)
_add(r"[A-Za-z]:\\[\w.\\/-]+", "<PATH>")
_add(r"(?:/[\w.-]+){2,}/?", "<PATH>")

# Home-dir segments (before general path catches them)
_add(r"/Users/[\w.-]+/", "<HOME>/")
_add(r"/home/[\w.-]+/", "<HOME>/")

# Emails
_add(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b", "<EMAIL>")

# IPv4
_add(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "<IP>")

# Ports after host-like token (colon + 2-5 digits)
_add(r"(?<=[:\w]):(\d{2,5})\b", "<PORT>")

# PIDs
_add(r"\bpid[=: ]\d+\b", "<PID>", re.IGNORECASE)
_add(r"^\[\d+\]", "<PID>", re.MULTILINE)

# UUIDs (must precede hex to avoid partial match)
_add(r"\b[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}\b", "<UUID>")

# Hex addresses / SHA hashes (7-40 hex chars, not pure dictionary words)
_add(r"\b0x[0-9a-fA-F]+\b", "<HEX>")
_add(r"\b[0-9a-f]{8,40}\b", "<HEX>")

# Clock times (after timestamps/dates already stripped)
_add(r"\b\d{1,2}:\d{2}(?::\d{2})?\b", "<TIME>")

# Durations / sizes
_add(r"\b\d+(?:\.\d+)?\s*(?:ms|s|sec|secs|seconds?|min|mins|minutes?|hr|hrs|h|d|days?)\b", "<DUR>", re.IGNORECASE)
_add(r"\b\d+(?:\.\d+)?\s*(?:kb|mb|gb|tb|b)\b", "<SIZE>", re.IGNORECASE)

# Line:col references
_add(r"\bline\s+\d+", "<LINE>", re.IGNORECASE)
_add(r"\b\d+:\d+(?::\d+)?\b", "<LINE>")

# Base64 / long random strings (32+ chars)
_add(r"\b[A-Za-z0-9+/]{32,}={0,2}\b", "<B64>")

# Long numbers (4+ digits — instance IDs, timestamps in seconds, etc.)
_add(r"\b\d{4,}\b", "<NUM>")

# ── Phase 2: semantic token preservation ─────────────────────────────────────
# Canonical lowercase tokens to keep after stripping.
_KNOWN_TOKENS = frozenset({
    # Exception classes
    "modulenotfounderror", "importerror", "nameerror", "typeerror",
    "attributeerror", "indexerror", "keyerror", "valueerror",
    "syntaxerror", "runtimeerror", "stopiteration", "unicodeerror",
    "filenotfounderror", "permissionerror", "isadirectoryerror",
    "timeouterror", "connectionerror", "connectionrefusederror",
    "connectionreseterror", "brokenpipeerror", "eoferror",
    "oserror", "ioerror", "recursionerror", "memoryerror",
    "notimplementederror", "assertionerror", "unboundlocalerror",
    "httperror", "requestexception", "readtimeouterror",
    "connecttimeouterror", "sslerror", "jsondecodeerror",
    "yamlparsererror", "scannererror",
    # Errno
    "eacces", "eperm", "enoent", "enospc", "econnreset",
    "econnrefused", "etimedout", "eaddrinuse", "eaddrnotavail",
    "epipe", "ehostunreach", "enetworkunreach", "eagain",
    "eintr", "efault", "ebadf", "einval", "emfile", "enfile",
    "enomem", "eio", "ebusy", "enotdir", "eisdir", "eexist",
    "enotempty", "espipe", "erofs", "exdev", "enodev", "eoverflow",
    "ebrokenpipe",
    # Exit codes
    "exit code 1", "exit code 2", "exit code 126", "exit code 127",
    "exit code 137", "exit code 139", "exit code 143",
    # Signals
    "oomkilled", "killed", "segfault", "sigkill", "sigsegv", "sigabrt",
    # Common error phrases
    "permission denied", "no space left on device", "certificate verify failed",
    "context deadline exceeded", "no such file", "connection refused",
    "connection reset", "address already in use", "name or service not known",
    "out of memory", "stack overflow", "null pointer", "segfault",
    # HTTP status
    "400", "401", "403", "404", "405", "408", "409", "410", "422", "429",
    "500", "502", "503", "504",
    # Git
    "merge conflict", "detached head", "non-fast-forward",
    "refusing to merge", "untracked working tree",
    # Docker/K8s
    "imagepullbackoff", "crashloopbackoff", "pending", "evicted",
    "pod initializing", "init container", "liveness probe",
    # Python packaging
    "no module named", "distributionnotfound", "version conflict",
    "incompatible", "dependency resolution",
    # Node
    "err_module_not_found", "err_require_esm", "err_unknown_file_extension",
    # CI
    "exit code 1", "process completed with exit code",
    "the operation was canceled",
})

# Noise tokens to drop when sufficient informative tokens remain.
_NOISE = frozenset({
    "the", "a", "an", "in", "on", "at", "for", "to", "of", "by", "with",
    "from", "is", "are", "was", "were", "be", "been", "being",
    "has", "have", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "must", "can", "shall",
    "failed", "error", "exception", "during", "while", "attempting",
    "cannot", "unable", "not", "no", "but", "and", "or", "if", "then",
    "else", "when", "where", "how", "what", "which", "that", "this",
    "it", "its", "they", "them", "their", "we", "us", "our",
    "you", "your", "he", "him", "his", "she", "her",
})

# Tech stack detection (reuse failure_harvest._detect_stack style).
_STACK_PATTERNS = {
    "python": re.compile(r"\b(?:python|pip|conda|virtualenv|pyproject|setup\.py|\.py)\b", re.I),
    "node": re.compile(r"\b(?:node|npm|npx|yarn|pnpm|package\.json|node_modules|\.js|\.ts)\b", re.I),
    "git": re.compile(r"\b(?:git|github|gitlab|bitbucket|git@\w+)\b", re.I),
    "docker": re.compile(r"\b(?:docker|dockerfile|compose|podman|containerd)\b", re.I),
    "k8s": re.compile(r"\b(?:k8s|kubernetes|kubectl|pod|deployment|service|ingress|helm)\b", re.I),
    "swift": re.compile(r"\b(?:swift|xcode|swiftformat|swiftlint|spm|cocoapods|carthage)\b", re.I),
    "rust": re.compile(r"\b(?:rust|cargo|rustc|crate|\.rs)\b", re.I),
    "go": re.compile(r"\b(?:golang|go\s+mod|go\s+build|\.go)\b", re.I),
    "java": re.compile(r"\b(?:java|gradle|maven|spring|\.java|\.jar)\b", re.I),
    "ci": re.compile(r"\b(?:github.actions|gitlab.ci|jenkins|circleci|travis|azure\.pipelines)\b", re.I),
}


def extract_error_line(text: str) -> str:
    """Phase 0: extract the most informative error line from text.

    Priority: last traceback exception > ERROR/FATAL line > exit code > HTTP status > errno > first 400 chars.
    """
    lines = text.strip().splitlines()

    # 1. Last traceback exception class
    for line in reversed(lines):
        m = _TRACEBACK_EXC.search(line)
        if m:
            return line.strip()[:400]

    # 2. ERROR/FATAL/CRITICAL line
    for line in reversed(lines):
        m = _ERROR_FATAL.search(line)
        if m:
            return line.strip()[:400]

    # 3. Exit code
    for line in lines:
        m = _EXIT_CODE.search(line)
        if m:
            return line.strip()[:200]

    # 4. HTTP status code (standalone, not in a URL)
    for line in lines:
        stripped = re.sub(r"https?://\S+", "", line)
        if _HTTP_STATUS.search(stripped):
            return line.strip()[:200]

    # 5. Errno
    for line in lines:
        if _ERRNO.search(line):
            return line.strip()[:200]

    # 6. Fallback: first 400 chars
    return text.strip()[:400]


def strip_volatile(text: str) -> str:
    """Phase 1: replace volatile artifacts with stable placeholders."""
    for pattern, placeholder in _STRIP_RULES:
        text = pattern.sub(placeholder, text)
    return text


def normalize_tokens(text: str) -> list[str]:
    """Phase 2: lowercase, strip punctuation, drop noise, keep semantic tokens.

    Placeholders (<PATH>, <PID>, etc.) are lowercased too — the hash must be
    case-insensitive. The _KNOWN_TOKENS set is already lowercase.
    """
    # Extract placeholders before lowercasing (they have a canonical form)
    placeholders = set(re.findall(r"<[A-Z]+>", text))

    text = text.lower()
    # Collapse whitespace and strip punctuation (keep < > for placeholders)
    text = re.sub(r"[^\w\s<>-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    tokens = text.split()
    result = []
    seen = set()
    for tok in tokens:
        # Keep placeholder tokens (now lowercase like <path>)
        if tok.startswith("<") and tok.endswith(">"):
            if tok not in seen:
                seen.add(tok)
                result.append(tok)
            continue
        # Keep known semantic tokens
        if tok in _KNOWN_TOKENS:
            if tok not in seen:
                seen.add(tok)
                result.append(tok)
            continue
        # Keep tokens that look like exception classes or error codes
        if re.match(r"^[a-z]\w*(?:error|exception|fault)$", tok):
            if tok not in seen:
                seen.add(tok)
                result.append(tok)
            continue
        # Drop noise
        if tok in _NOISE:
            continue
        # Keep everything else (partial error messages, etc.)
        if len(tok) >= 2 and tok not in seen:
            seen.add(tok)
            result.append(tok)

    return result


def detect_stack(text: str) -> list[str]:
    """Detect tech stacks from text."""
    stacks = []
    for stack, pattern in _STACK_PATTERNS.items():
        if pattern.search(text):
            stacks.append(stack)
    return stacks


def classify(text: str) -> str:
    """Classify error text into a kind label (mirrors failure_harvest.classify)."""
    # Specific exception class
    m = _TRACEBACK_EXC.search(text)
    if m:
        return m.group(1)

    # HTTP status
    stripped = re.sub(r"https?://\S+", "", text)
    m = _HTTP_STATUS.search(stripped)
    if m:
        return f"http-{m.group()}"

    # Errno
    m = _ERRNO.search(text)
    if m:
        return m.group().lower()

    # Exit code
    m = _EXIT_CODE.search(text)
    if m:
        return f"exit-{m.group(1)}"

    # Generic with stack
    stacks = detect_stack(text)
    if stacks:
        return f"generic-failure|{','.join(stacks)}"

    return "generic-failure"


def compute_signature(text: str) -> dict:
    """Full pipeline: extract → strip → normalize → compose canonical signature.

    Returns dict with:
        raw: original extracted error line
        stripped: after volatile removal
        tokens: all canonical tokens (for display/ranking)
        semantic_tokens: stable semantic tokens only (for hash)
        kind: classification label
        hash: stable 16-char hex hash (from kind + semantic_tokens only)
        display: human-readable signature
        stack: detected tech stacks
        norm_version: SIGNATURE_NORM_VERSION
    """
    raw = extract_error_line(text)
    stripped = strip_volatile(raw)
    tokens = normalize_tokens(stripped)
    kind = classify(raw)
    stack = detect_stack(raw)

    # Semantic tokens = kind + known tokens that appear in the normalized list.
    # These are stable across different instances of the same failure class.
    # Placeholders (<path>, <pid>, etc.) and generic words are excluded from the hash.
    semantic = []
    seen = set()
    # kind is always the primary semantic signal
    kind_lower = kind.lower()
    if kind_lower not in seen:
        seen.add(kind_lower)
        semantic.append(kind_lower)
    for tok in tokens:
        if tok.startswith("<") and tok.endswith(">"):
            continue  # placeholder — volatile
        if tok in _KNOWN_TOKENS and tok not in seen:
            seen.add(tok)
            semantic.append(tok)
        # Also keep exception class names detected from the raw text
        elif re.match(r"^[a-z]\w*(?:error|exception|fault)$", tok) and tok not in seen:
            seen.add(tok)
            semantic.append(tok)

    # Hash = kind + stack only. This is the most stable signal — "same failure class"
    # is determined by the classification, not by which context words appear.
    # Context tokens (known tokens, error phrases) are for display/ranking, not hashing.
    # Exception: if kind is generic-failure, include the strongest known tokens too
    # (otherwise all generic failures collide).
    hash_tokens = [kind_lower]
    if kind_lower.startswith("generic"):
        # For generic failures, include known semantic tokens to differentiate
        for tok in sorted(semantic):
            if tok != kind_lower and tok in _KNOWN_TOKENS:
                hash_tokens.append(tok)
    # Always include stack for differentiation
    for s in sorted(stack):
        hash_tokens.append(f"stack:{s}")

    # Compose hash from sorted unique tokens (order-independent)
    sig_input = "|".join(sorted(set(hash_tokens)))
    sig_hash = hashlib.sha1(sig_input.encode()).hexdigest()[:16]

    # Display: kind + first 12 tokens
    display = f"{kind} :: {' '.join(tokens[:12])}"

    return {
        "raw": raw,
        "stripped": stripped,
        "tokens": tokens,
        "semantic_tokens": sorted(semantic),
        "kind": kind,
        "hash": sig_hash,
        "display": display,
        "stack": stack,
        "norm_version": SIGNATURE_NORM_VERSION,
    }


def compute_dedup_hash(kind: str, text: str, domain: Optional[str] = None) -> str:
    """Compute a dedup hash for intake (replaces raw text hash)."""
    sig = compute_signature(text)
    source = f"{kind}:{sig['hash']}"
    if domain:
        source += f":{domain}"
    return hashlib.sha1(source.encode()).hexdigest()[:16]


# ── CLI entry point ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) < 2:
        print("Usage: python error_signature.py <error_text_or_file>", file=sys.stderr)
        sys.exit(1)

    arg = sys.argv[1]
    # If it's a file, read it; otherwise treat as text
    try:
        from pathlib import Path
        p = Path(arg)
        if p.is_file():
            text = p.read_text(encoding="utf-8")
        else:
            text = arg
    except (OSError, ValueError):
        text = arg

    result = compute_signature(text)
    print(json.dumps(result, indent=2, ensure_ascii=False))