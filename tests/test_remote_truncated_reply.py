#!/usr/bin/env python3
"""A 200 whose body stops early must be named a cut delivery, not a parse failure (#5245).

The report was a `misakanet_search` call whose headers announced 13315 bytes and whose body stopped
at 605. The probe then measured the endpoint (`scripts/probe_mcp_body.py`, 60 samples, zero short
bodies) and cleared it: the worker writes the whole body, something between it and the caller cuts
the stream. So the remaining defect is on this side of the wire — the client could not *say* that:

* a short body the transport handed over anyway reached `parse_mcp_reply` and came back as "could
  not decode reply", which accuses the endpoint of emitting bad JSON. Six intakes were triaged as
  parse failures on the strength of that sentence;
* the real `urllib` path raised `http.client.IncompleteRead`, which no `except` in `remote.call`
  named, so it escaped the package's one MCP client as a traceback — and the CLI, which catches
  only `RemoteError`, could turn it into neither a message nor an exit code;
* a mid-body reset came back as "endpoint unreachable", which is false: the endpoint answered 200.

These pin all three, plus the two things that must *not* change: a complete reply still decodes, and
a body that really is malformed is still reported as malformed. That last distinction is the
deliverable — a cut delivery is worth retrying, a malformed body is not, and a caller that cannot
tell them apart has to guess which.
"""
from __future__ import annotations

import contextlib
import http.client
import io
import json
import socket
import sys
import threading
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from misakanet import remote  # noqa: E402
from misakanet.cli import search as cli  # noqa: E402

# The two numbers from the report: the headers promised this many bytes, and this many arrived.
ANNOUNCED = 13315
ARRIVED = 605


def _envelope(size: int) -> bytes:
    """A complete, decodable `tools/call` reply of exactly `size` bytes.

    Padded to the reported size rather than invented small, because the cut body is a *prefix* of a
    real one: a fixture short enough that slicing it at 605 returns the whole document would pass
    whatever the code did (it did exactly that on this file's first run).
    """
    def built(pad: int) -> bytes:
        return json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"structuredContent": {"results": [
            {"title": "pip install timeout", "score": 0.9, "preview": "x" * pad}]}}}).encode()

    return built(size - len(built(0)))


ENVELOPE = _envelope(ANNOUNCED)
PARTIAL = ENVELOPE[:ARRIVED]


class _Reply:
    """A response double shaped like `http.client.HTTPResponse` as `remote.call` reads it.

    `read` is a callable so a test can make the body stop early *or* raise the way the transport
    does; `headers` is a plain dict because `Content-Length` is the only header this client reads.
    """

    def __init__(self, read, *, declared: int | None = None, status: int = 200):
        self.status = status
        self._read = read
        self.headers = {} if declared is None else {"Content-Length": str(declared)}

    def read(self) -> bytes:
        return self._read()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _answer(monkeypatch, reply: _Reply) -> None:
    monkeypatch.setattr(remote.urllib.request, "urlopen", lambda request, timeout=None: reply)


# ── the three shapes that used to be mis-named ──────────────────────────────────────────────────
def test_a_body_short_of_its_announced_length_is_a_cut_delivery(monkeypatch):
    """The reported shape: the headers promise more than the connection delivers."""
    _answer(monkeypatch, _Reply(lambda: PARTIAL, declared=ANNOUNCED))
    with pytest.raises(remote.TruncatedReply) as caught:
        remote.search("pip install timeout")

    error = caught.value
    assert error.announced == ANNOUNCED and error.received == ARRIVED
    text = str(error)
    assert str(ARRIVED) in text and str(ANNOUNCED) in text, "both numbers are the evidence"
    assert "cut in transit" in text
    assert "could not decode" not in text, "nothing was mis-parsed, so do not accuse the parser"


def test_an_incomplete_read_is_reported_instead_of_escaping_the_client(monkeypatch):
    """What `urllib` actually raises on an unmet length. It used to leave `remote.call` uncaught."""
    def cut():
        raise http.client.IncompleteRead(PARTIAL, ANNOUNCED - ARRIVED)

    _answer(monkeypatch, _Reply(cut, declared=ANNOUNCED))
    with pytest.raises(remote.TruncatedReply) as caught:
        remote.search("pip install timeout")
    assert caught.value.received == ARRIVED and caught.value.announced == ANNOUNCED
    assert "IncompleteRead" in str(caught.value), "keep the transport's own word for the reader"


def test_an_incomplete_read_without_a_declared_length_still_counts_the_bytes(monkeypatch):
    """The chunked path announces no length, so the error itself is the only witness of the size."""
    def cut():
        raise http.client.IncompleteRead(PARTIAL, 712)

    _answer(monkeypatch, _Reply(cut))
    with pytest.raises(remote.TruncatedReply) as caught:
        remote.search("x")
    assert caught.value.received == ARRIVED
    assert caught.value.announced == ARRIVED + 712, "`expected` is what is still owed, not the total"


def test_a_reset_in_the_middle_of_the_body_is_not_reported_as_unreachable(monkeypatch):
    """A 200 arrived. "Unreachable" would be a false statement about an endpoint that answered."""
    def reset():
        raise ConnectionResetError(10054, "An existing connection was forcibly closed")

    _answer(monkeypatch, _Reply(reset, declared=ANNOUNCED))
    with pytest.raises(remote.TruncatedReply) as caught:
        remote.search("x")
    assert "unreachable" not in str(caught.value)
    assert caught.value.announced == ANNOUNCED and caught.value.received == 0


# ── what must keep working ──────────────────────────────────────────────────────────────────────
def test_a_complete_reply_is_unaffected(monkeypatch):
    _answer(monkeypatch, _Reply(lambda: ENVELOPE, declared=ANNOUNCED))
    assert remote.search("x")["results"][0]["title"] == "pip install timeout"


def test_a_reply_that_announces_no_length_is_not_called_short(monkeypatch):
    """`Transfer-Encoding: chunked` carries no `Content-Length`; absence is not a short body."""
    _answer(monkeypatch, _Reply(lambda: ENVELOPE))
    assert remote.search("x")["results"][0]["score"] == 0.9


def test_a_malformed_body_of_the_right_length_is_still_called_malformed(monkeypatch):
    """The other half of the distinction: every byte arrived, so the endpoint *is* the author."""
    junk = b"<html>504 Gateway Time-out</html>"
    _answer(monkeypatch, _Reply(lambda: junk, declared=len(junk)))
    with pytest.raises(remote.RemoteError) as caught:
        remote.search("x")
    assert not isinstance(caught.value, remote.TruncatedReply)
    assert "could not decode reply" in str(caught.value)


def test_the_cli_turns_a_cut_delivery_into_a_message_and_an_exit_code(monkeypatch):
    """`TruncatedReply` subclasses `RemoteError`, so every existing handler keeps catching it."""
    assert issubclass(remote.TruncatedReply, remote.RemoteError)
    _answer(monkeypatch, _Reply(lambda: PARTIAL, declared=ANNOUNCED))
    err = io.StringIO()
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
        assert cli.main(["pip install timeout"]) == cli.EXIT_ERROR
    assert "cut in transit" in err.getvalue()


# ── the end-to-end witness ──────────────────────────────────────────────────────────────────────
def test_a_real_socket_that_announces_more_than_it_sends_is_caught():
    """One pass over a real `urllib` read, so the doubles above cannot drift from the transport.

    The doubles assert what `remote.call` does with a short read; this asserts that a server which
    announces 13315 and sends 605 actually produces one. Localhost only, one connection, no TLS.
    """
    header = b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: %d\r\n\r\n"

    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    port = listener.getsockname()[1]

    def serve() -> None:
        with listener:
            connection, _ = listener.accept()
            with connection:
                # Drain the whole POST before answering, then half-close. Closing a socket that
                # still holds unread bytes sends an RST, and the client then fails in `urlopen`
                # with "connection aborted" before it has parsed any headers — a different defect
                # from the one under test, and one this server would have invented.
                request = b""
                while b"\r\n\r\n" not in request:
                    received = connection.recv(65536)
                    if not received:
                        break
                    request += received
                head, _, rest = request.partition(b"\r\n\r\n")
                owed = int(head.decode("latin-1").lower().split("content-length:")[1].split("\r\n")[0])
                while len(rest) < owed:
                    rest += connection.recv(65536)
                connection.sendall(header % ANNOUNCED + PARTIAL)
                connection.shutdown(socket.SHUT_WR)

    server = threading.Thread(target=serve, daemon=True)
    server.start()
    try:
        with pytest.raises(remote.TruncatedReply) as caught:
            remote.call("misakanet_search", {"query": "x"}, timeout=10,
                        endpoint_url=f"http://127.0.0.1:{port}/mcp")
    finally:
        server.join(timeout=5)
    assert caught.value.announced == ANNOUNCED
    assert f"127.0.0.1:{port}" in str(caught.value), "name the endpoint that cut, not the default"
