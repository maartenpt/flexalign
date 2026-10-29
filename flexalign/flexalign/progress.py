"""Progress of the long loops on stderr: done / total, elapsed time, and an estimate of the time left.

On a terminal the line is rewritten in place; elsewhere (a log file, `| tee`) a line at most every 30 seconds.
Every run ends with one line saying how many and how long. Shown on a terminal, or with FLEXI_PROGRESS=1 (a caller
passing stderr through); never otherwise, so callers that read the output (the TEITOK module) see none of it.
(opus-teitok keeps a copy of its own.)
"""

from __future__ import annotations

import os
import shutil
import sys
import time
from typing import Callable, Iterable, Iterator, Optional, TypeVar

T = TypeVar("T")
enabled = sys.stderr.isatty() or os.environ.get("FLEXI_PROGRESS") == "1"


def duration(seconds: float) -> str:
    s = int(seconds)
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m{s % 60:02d}s"
    return f"{s // 3600}h{s % 3600 // 60:02d}m"


def size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return ""


class Progress:
    """`with Progress("convert", total=n) as p: … p.step(item="en/a.xml")`; `bytes=True` counts sizes. Without
    `total` and steps it just says the step has started and how long it took (`with Progress("write"):`)."""

    def __init__(self, label: str, total: Optional[int] = None, *, bytes: bool = False, indent: str = "  ") -> None:
        self.label, self.total, self.bytes, self.indent = label, total, bytes, indent
        self.done = 0
        self.start = self.last = time.time()
        self.tty = sys.stderr.isatty()
        self.every = 0.5 if self.tty else 30.0
        self.width = 0
        self.current = ""   # the item worked on, shown on a terminal
        if enabled and self.tty:
            self._write(self.line())   # at once: the first item may take a while

    def _count(self, n: float) -> str:
        return size(n) if self.bytes else str(n)

    def _counted(self) -> bool:
        return bool(self.total or self.done)

    def line(self) -> str:
        elapsed = time.time() - self.start
        text = f"{self.indent}{self.label}" + (f" {self._count(self.done)}" if self._counted() else "")
        if self.total:
            text += f"/{self._count(self.total)} ({100 * self.done / self.total:.0f}%)"
        text += f", {duration(elapsed)}" if self._counted() else " …"
        if self.total and self.done >= self.total / 100 and elapsed > 5:   # less: too early to tell
            text += f", ~{duration(elapsed * (self.total - self.done) / self.done)} left"
        return text + (f"  {self.current}" if self.current and self.tty else "")

    def step(self, n: int = 1, item: str = "") -> None:
        self.done += n
        if item:
            self.current = item
        now = time.time()
        if not enabled or now - self.last < self.every:
            return
        self.last = now
        self._write(self.line())

    def _write(self, text: str, end: bool = False) -> None:
        if self.tty:
            text = text[:shutil.get_terminal_size((200, 24)).columns - 1]
            sys.stderr.write("\r" + text.ljust(self.width) + ("\n" if end else ""))
            self.width = 0 if end else len(text)
        else:
            sys.stderr.write(text + "\n")
        sys.stderr.flush()

    def finish(self, note: str = "") -> None:
        if not enabled:
            return
        count = f" {self._count(self.done)}" if self._counted() else ""
        text = f"{self.indent}{self.label}{count} in {duration(time.time() - self.start)}"
        self._write(text + (f" ({note})" if note else ""), end=True)

    def __enter__(self) -> "Progress":
        return self

    def __exit__(self, exc_type, *_) -> None:
        if exc_type is None:
            self.finish()
        elif self.tty and self.width:
            sys.stderr.write("\n")   # an error message starts on a line of its own


def track(items: Iterable[T], label: str, total: Optional[int] = None,
          name: Optional[Callable[[T], str]] = None) -> Iterator[T]:
    """The items, counted as they are done (`total`: len(items) when it has one); `name`: the item shown while it
    is worked on (on a terminal)."""
    if total is None and hasattr(items, "__len__"):
        total = len(items)   # type: ignore[arg-type]
    with Progress(label, total) as p:
        for x in items:
            p.current = name(x) if name else ""
            yield x
            p.step()
