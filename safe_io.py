"""Make stdout/stderr unable to raise.

The makcu library prints inside its button handler before it fires the callback. If stdout
is broken (terminal hung up, pipe closed, EIO) that print raises, the library swallows the
error, and every button event is silently lost. A stream that ignores write errors removes
that whole class of failure for the library and for Helix's own log lines.
"""
import sys


class _SafeStream:
    def __init__(self, stream):
        self._stream = stream

    def write(self, data):
        try:
            return self._stream.write(data)
        except Exception:
            return len(data)

    def flush(self):
        try:
            self._stream.flush()
        except Exception:
            pass

    def __getattr__(self, name):
        return getattr(self._stream, name)


def install():
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name)
        if stream is not None and not isinstance(stream, _SafeStream):
            setattr(sys, name, _SafeStream(stream))
