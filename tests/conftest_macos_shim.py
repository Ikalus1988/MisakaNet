import builtins, pytest
_real = builtins.open
def _open(file, *a, **k):
    if isinstance(file, bytes) and b"\xff" in file:
        raise OSError(92, "Illegal byte sequence")
    return _real(file, *a, **k)
builtins.open = _open
